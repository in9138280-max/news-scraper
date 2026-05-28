import os
import re
import io
import zipfile
import streamlit as st
import pandas as pd
from datetime import datetime

# 1. 페이지 레이아웃 기본 설정 (가장 최상단 필수)
st.set_page_config(page_title="탄소중립 뉴스 스크랩 에이전트", layout="wide")

# 라이브러리 정상 임포트 체크
try:
    import requests
    from bs4 import BeautifulSoup
    from openai import OpenAI
    from playwright.sync_api import sync_playwright
except ImportError:
    st.error("필수 라이브러리가 로드되지 않았습니다. GitHub의 requirements.txt 세팅을 확인해주세요.")

# 타이틀 및 인프라 소개
st.title("🌿 뉴스 스크랩 자동화 에이전트")
st.caption("네이버 API와 OpenAI, Playwright를 활용해 기사 수집, 하이브리드 분류, 요약 및 레이아웃 유지 PDF 다운로드를 수행합니다.")

# 2. 세션 상태 초기화 (새로고침 시 데이터 휘발 방지)
if "scraped_data" not in st.session_state:
    st.session_state.scraped_data = []

# 고정 카테고리 및 검색 키워드 정의
LARGE_CATEGORIES = ["배출권", "탄소시장", "탄소세", "ESG", "전기차", "탄소중립", "CBAM", "IAA"]
SMALL_CATEGORIES = ["자발적 탄소시장", "국제감출", "탄소제거", "기후공시", "전환금융", "녹색금융", "재생에너지", "기후테크"]
SEARCH_KEYWORDS = ["탈탄소", "탄소중립", "CBAM", "IIA", "녹색금융", "ESG", "탄소배출권"]

# 3. API 키 안전하게 로드 (Streamlit Secrets 연동 + 사이드바 예비용)
st.sidebar.header("🔑 API 자격 증명 설정")
secrets_id = st.secrets.get("NAVER_CLIENT_ID", "")
secrets_secret = st.secrets.get("NAVER_CLIENT_SECRET", "")
secrets_openai = st.secrets.get("OPENAI_API_KEY", "")

naver_client_id = st.sidebar.text_input("네이버 Client ID", value=secrets_id, type="password")
naver_client_secret = st.sidebar.text_input("네이버 Client Secret", value=secrets_secret, type="password")
openai_api_key = st.sidebar.text_input("OpenAI API Key", value=secrets_openai, type="password")

# 4. 파일명 안전화 전처리 함수
def clean_filename(filename):
    # OS에서 허용하지 않는 \ / : * ? " < > | 특수문자를 언더바(_)로 치환
    return re.sub(r'[\s\\/:*?"<>|]+', '_', filename)

# 5. 대분류/소분류 하이브리드 분류 로직 (빈도수 + LLM Fallback)
def classify_category(title, content, openai_client=None):
    text = f"{title} {content}"
    
    # 1차: 단순 빈도수 체크
    large_counts = {cat: text.count(cat) for cat in LARGE_CATEGORIES}
    small_counts = {cat: text.count(cat) for cat in SMALL_CATEGORIES}
    
    max_large_val = max(large_counts.values())
    max_small_val = max(small_counts.values())
    
    best_large = max(large_counts, key=large_counts.get) if max_large_val > 0 else None
    best_small = max(small_counts, key=small_counts.get) if max_small_val > 0 else None
    
    # 동률이거나 키워드가 아예 없는 경우 2차 OpenAI LLM 작동
    if (not best_large or not best_small or list(large_counts.values()).count(max_large_val) > 1 or list(small_counts.values()).count(max_small_val) > 1) and openai_client:
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system", 
                        "content": f"너는 기후에너지 정책 뉴스 분류 전문가야. 제공된 뉴스 정보를 분석해서 가장 적합한 대분류와 소분류를 후보군 중에서 각각 딱 '하나씩만' 매칭해줘. 다른 설명은 배제하고 반드시 두 카테고리를 컴마(,)로만 구분해서 출력해.\n\n대분류 후보: {LARGE_CATEGORIES}\n소분류 후보: {SMALL_CATEGORIES}\n\n출력 예시: 탄소중립,기후테크"
                    },
                    {"role": "user", "content": f"제목: {title}\n본문 미리보기: {content[:400]}"}
                ],
                temperature=0.0
            )
            res_text = response.choices[0].message.content.strip()
            if "," in res_text:
                llm_large, llm_small = res_text.split(',', 1)
                best_large = best_large or llm_large.strip()
                best_small = best_small or llm_small.strip()
        except Exception:
            pass # 에러 발생 시 1차 빈도수 결과 유지 혹은 기본값 처리
            
    return best_large or "기타", best_small or "기타"

# 6. OpenAI 기반 5줄 이내 핵심 요약 함수
def summarize_content(title, content, openai_client):
    if not openai_client:
        return "⚠️ OpenAI API Key가 제공되지 않아 요약을 생성할 수 없습니다."
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "너는 뉴스 기사 분석 에이전트야. 제공된 뉴스 본문을 정독하고 핵심 내용만 추려서 '반드시 5줄 이내의 문장'으로 정교하게 요약해줘. 마크다운 마커(-) 형태의 리스트 포맷을 사용해줘."},
                {"role": "user", "content": f"제목: {title}\n본문: {content}"}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ 요약 실패 (에러 원인: {str(e)})"

# 7. 네이버 뉴스 API 데이터 요청 함수
def fetch_news(keyword, client_id, client_secret):
    url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display=5&sort=sim"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json().get('items', [])
    except Exception as e:
        st.sidebar.error(f"API 요청 실패 ({keyword}): {str(e)}")
    return []

# 네이버 뉴스 본문 텍스트 추출 백업 로직
def crawl_naver_news_article(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        article_body = soup.find("article", id="dic_area") or soup.find("div", id="articleBodyContents")
        if article_body:
            return article_body.get_text(strip=True)
    except Exception:
        pass
    return "본문 크롤링이 불가능하거나 외보고 기사입니다. 원문 PDF 저장을 이용해 확인하세요."

# 8. Playwright 활용 레이아웃/이미지 보존 PDF 굽기 함수
def convert_url_to_pdf(url):
    try:
        with sync_playwright() as p:
            # 크로미움 헤드리스 브라우저 실행
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
            page = context.new_page()
            
            # 네트워크가 안정화될 때까지 대기하여 이미지 로드 확보
            page.goto(url, wait_until="networkidle", timeout=30000)
            
            # A4 규격, 백그라운드 그래픽/이미지 포함 인쇄 플래그 설정
            pdf_bytes = page.pdf(format="A4", print_background=True)
            browser.close()
            return pdf_bytes
    except Exception as e:
        st.error(f"Playwright PDF 생성 실패 ({url}): {str(e)}")
        return None

# --- 메인 컨트롤러 및 UI 가동 ---

if st.button("🔄 지금 스크랩 시작하기", type="primary"):
    if not (naver_client_id and naver_client_secret):
        st.error("❌ 네이버 API Client ID 및 Secret을 설정해야 뉴스 수집이 가능합니다.")
    else:
        openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None
        
        all_scraped = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 키워드 루프 순회
        for idx, keyword in enumerate(SEARCH_KEYWORDS):
            status_text.text(f"🔍 키워드 스캔 중: [{keyword}] ({idx+1}/{len(SEARCH_KEYWORDS)})")
            items = fetch_news(keyword, naver_client_id, naver_client_secret)
            
            for item in items:
                # HTML 태그 제거 및 특수 인코딩 전처리
                title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", '"').replace("&apos;", "'")
                link = item['link']
                press = item['originallink'].split('//')[-1].split('/')[0] if 'originallink' in item else "언론사"
                
                # 인링크 본문 데이터 처리
                if "news.naver.com" in link:
                    content = crawl_naver_news_article(link)
                else:
                    content = item['description'].replace("<b>", "").replace("</b>", "")
                
                # 하이브리드 카테고리 분류 및 요약
                large_cat, small_cat = classify_category(title, content, openai_client)
                summary = summarize_content(title, content, openai_client)
                
                # 요구사항 맞춤 파일명 전처리 반영
                raw_filename = f"({large_cat})({small_cat}){title}_{press}.pdf"
                safe_filename = clean_filename(raw_filename)
                
                all_scraped.append({
                    "대분류": large_cat,
                    "소분류": small_cat,
                    "기사제목": title,
                    "언론사": press,
                    "URL": link,
                    "파일명": safe_filename,
                    "5줄요약": summary
                })
            progress_bar.progress((idx + 1) / len(SEARCH_KEYWORDS))
            
        status_text.text("✅ 모든 키워드 분석 및 분류가 완료되었습니다.")
        st.session_state.scraped_data = all_scraped
        st.success(f"총 {len(all_scraped)}건의 맞춤 기사가 로드되었습니다.")

# 데이터 연동 테이블 시각화 핸들러
if st.session_state.scraped_data:
    df = pd.DataFrame(st.session_state.scraped_data)
    
    st.subheader("📋 스크랩 결과 보고서 대시보드")
    st.caption("왼쪽 체크박스를 선택하여 원하는 기사만 부분 요약 확인 및 일괄 ZIP PDF 다운로드를 수행할 수 있습니다.")
    
    # 사용자 상호작용 테이블 구성
    df.insert(0, "선택", False)
    edited_df = st.data_editor(
        df[["선택", "대분류", "소분류", "기사제목", "언론사", "파일명"]], 
        hide_index=True, 
        use_container_width=True
    )
    
    # 실시간 다중 선택 인덱스 파싱
    selected_indices = edited_df[edited_df["선택"] == True].index.tolist()
    
    # 동적 하단 핵심 요약 컴포넌트 출력
    if selected_indices:
        st.write("---")
        st.subheader("🔍 선택 기사 실시간 OpenAI 5줄 핵심 요약")
        for idx in selected_indices:
            row = st.session_state.scraped_data[idx]
            with st.expander(f"📌 [{row['대분류']}/{row['소분류']}] {row['기사제목']} - {row['언론사']}"):
                st.markdown(row['5줄요약'])
                st.caption(f"기사 원문 주소: {row['URL']}")
    
    # 일괄 ZIP 압축 다운로드 인프라
    st.write("---")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📥 선택한 기사만 고화질 PDF ZIP 다운로드"):
            if not selected_indices:
                st.warning("테이블 왼쪽 체크박스에서 다운로드할 기사를 선택해 주세요.")
            else:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    with st.spinner("선택 기사의 이미지와 레이아웃을 포함해 PDF 생성 중... (약 수십 초 소요)"):
                        for idx in selected_indices:
                            item = st.session_state.scraped_data[idx]
                            pdf_bytes = convert_url_to_pdf(item['URL'])
                            if pdf_bytes:
                                zip_file.writestr(item['파일명'], pdf_bytes)
                
                st.download_button(
                    label="💾 선택 파일 다운로드 하기 (클릭)",
                    data=zip_buffer.getvalue(),
                    file_name=f"선택뉴스_PDF_스크랩_{datetime.now().strftime('%Y%m%d%H%M')}.zip",
                    mime="application/zip"
                )
                
    with col2:
        if st.button("🗂️ 수집된 전체 기사 고화질 PDF 일괄 ZIP 다운로드"):
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                with st.spinner("모든 기사 웹페이지의 레이아웃을 유지한 채 일괄 PDF 파일 굽는 중..."):
                    for item in st.session_state.scraped_data:
                        pdf_bytes = convert_url_to_pdf(item['URL'])
                        if pdf_bytes:
                            zip_file.writestr(item['파일명'], pdf_bytes)
            
            st.download_button(
                label="💾 전체 파일 다운로드 하기 (클릭)",
                data=zip_buffer.getvalue(),
                file_name=f"전체뉴스_PDF_스크랩_{datetime.now().strftime('%Y%m%d%H%M')}.zip",
                mime="application/zip"
            )
else:
    st.info("💡 사이드바에 API 키 정보들을 할당한 뒤 상단의 [지금 스크랩 시작하기] 버튼을 기동해 주세요.")
