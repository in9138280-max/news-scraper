import os
import re
import io
import zipfile
import streamlit as st
import pandas as pd
from datetime import datetime

# 1. 페이지 레이아웃 및 테마 기본 설정 (가장 최상단 필수)
st.set_page_config(page_title="탄소중립 뉴스 인텔리전스", layout="wide", initial_sidebar_state="expanded")

# 라이브러리 정상 임포트 체크
try:
    import requests
    from bs4 import BeautifulSoup
    from openai import OpenAI
    from playwright.sync_api import sync_playwright
except ImportError:
    st.error("필수 라이브러리가 부족합니다. GitHub의 requirements.txt 세팅을 확인해주세요.")

# 커스텀 CSS 스타일 주입 (디자인 고도화)
st.markdown("""
    <style>
    .main-title { font-size: 2.5rem ; font-weight: 800; color: #1E3A8A; margin-bottom: 0.5rem; }
    .sub-title { font-size: 1.1rem; color: #4B5563; margin-bottom: 2rem; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
    .report-card { background-color: #F3F4F6; padding: 1.5rem; border-radius: 10px; border-left: 5px solid #10B981; margin-bottom: 1rem; }
    </style>
""", unsafe_allow_html=True)

# 메인 타이틀 배너
st.markdown('<div class="main-title">🌿 탄소중립 뉴스 스크랩 인텔리전스 시스템</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">AI 기반 실시간 뉴스 수집, 하이브리드 카테고리 분류 및 이미지 포함 레이아웃 보존 PDF 리포팅 에이전트</div>', unsafe_allow_html=True)

# 2. 세션 상태 데이터 유지 보장
if "scraped_data" not in st.session_state:
    st.session_state.scraped_data = []

# 고정 카테고리 정의
LARGE_CATEGORIES = ["배출권", "탄소시장", "탄소세", "ESG", "전기차", "탄소중립", "CBAM", "IAA"]
SMALL_CATEGORIES = ["자발적 탄소시장", "국제감출", "탄소제거", "기후공시", "전환금융", "녹색금융", "재생에너지", "기후테크"]

# 3. 사이드바 제어 패널 설계
st.sidebar.markdown("### 🔑 API 자격 증명")
secrets_id = st.secrets.get("NAVER_CLIENT_ID", "")
secrets_secret = st.secrets.get("NAVER_CLIENT_SECRET", "")
secrets_openai = st.secrets.get("OPENAI_API_KEY", "")

naver_client_id = st.sidebar.text_input("네이버 Client ID", value=secrets_id, type="password")
naver_client_secret = st.sidebar.text_input("네이버 Client Secret", value=secrets_secret, type="password")
openai_api_key = st.sidebar.text_input("OpenAI API Key", value=secrets_openai, type="password")

st.sidebar.write("---")
st.sidebar.markdown("### 🎯 타겟 타겟 키워드 설정")
# 사용자가 화면에서 기사 검색 키워드를 자유롭게 수정할 수 있는 인프라 구축
default_keywords = ["탈탄소", "탄소중립", "CBAM", "IIA", "녹색금융", "ESG", "탄소배출권"]
target_keywords = st.sidebar.multiselect("수집할 키워드를 선택/입력하세요", options=default_keywords, default=default_keywords)

# 4. 파일네임 특수문자 예외 처리 전처리 함수
def clean_filename(filename):
    return re.sub(r'[\s\\/:*?"<>|]+', '_', filename)

# 5. 대분류/소분류 하이브리드 매칭 엔진 (1차 빈도수 분석 -> 2차 모호할 시 LLM 추론)
def classify_category(title, content, openai_client=None):
    text = f"{title} {content}"
    large_counts = {cat: text.count(cat) for cat in LARGE_CATEGORIES}
    small_counts = {cat: text.count(cat) for cat in SMALL_CATEGORIES}
    
    max_large_val = max(large_counts.values())
    max_small_val = max(small_counts.values())
    
    best_large = max(large_counts, key=large_counts.get) if max_large_val > 0 else None
    best_small = max(small_counts, key=small_counts.get) if max_small_val > 0 else None
    
    # 빈도가 동률이거나 0건 매칭되어 카테고리가 모호할 때 OpenAI 가동
    if (not best_large or not best_small or list(large_counts.values()).count(max_large_val) > 1 or list(small_counts.values()).count(max_small_val) > 1) and openai_client:
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": f"뉴스 정보를 분석해 대분류와 소분류를 후보군 중 딱 하나씩만 매핑해줘. 설명 없이 반드시 두 단어를 컴마(,)로만 구분해 출력해.\n\n대분류 후보: {LARGE_CATEGORIES}\n소분류 후보: {SMALL_CATEGORIES}\n\n출력 예시: 탄소중립,기후테크"},
                    {"role": "user", "content": f"제목: {title}\n본문 일부: {content[:300]}"}
                ],
                temperature=0.0
            )
            res_text = response.choices[0].message.content.strip()
            if "," in res_text:
                llm_large, llm_small = res_text.split(',', 1)
                best_large = best_large or llm_large.strip()
                best_small = best_small or llm_small.strip()
        except Exception:
            pass
            
    return best_large or "기타", best_small or "기타"

# 6. OpenAI 기반 5줄 이내 핵심 요약 함수 (try-except 설계)
def summarize_content(title, content, openai_client):
    if not openai_client:
        return "💡 OpenAI API Key가 입력되지 않아 요약을 제공하지 않습니다. (사이드바 입력을 확인하세요)"
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "너는 기후경제 뉴스 전문 브리핑 에이전트야. 제공된 뉴스 본문을 정독하고 핵심 요점만 간추려서 '반드시 5줄 이내의 문장'으로 가독성 좋게 요약해줘. 마크다운 글머리기호(-) 포맷을 적용해줘."},
                {"role": "user", "content": f"제목: {title}\n본문: {content}"}
            ],
            temperature=0.2
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ 요약 데이터 생성 실패: {str(e)}"

# 7. 사내 방화벽 대비용 하이브리드 수집 로직 (API 실패 시 크롤링으로 자동 우회)
def fetch_news_hybrid(keyword, client_id, client_secret):
    if client_id and client_secret:
        url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display=5&sort=sim"
        headers = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret}
        try:
            response = requests.get(url, headers=headers, timeout=3)
            if response.status_code == 200:
                return response.json().get('items', [])
        except Exception:
            pass # 타임아웃 발생 시 아래 일반 검색 크롤링 백업 모드로 패스
            
    # 백업 크롤링 파트 (사내 네트워크 보안 차단 우회)
    scraped_items = []
    try:
        search_url = f"https://search.naver.com/search.naver?where=news&query={keyword}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(search_url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        
        articles = soup.select("ul.list_news > li")
        for art in articles[:4]:
            title_el = art.select_one("a.news_tit")
            if title_el:
                title = title_el.get_text()
                link = title_el['href']
                desc_el = art.select_one("div.news_dsc")
                desc = desc_el.get_text() if desc_el else ""
                
                info_links = art.select("div.news_info > div.info_group > a")
                for il in info_links:
                    if "news.naver.com" in il.get('href', ''):
                        link = il['href']
                        break
                        
                scraped_items.append({"title": title, "link": link, "description": desc})
    except Exception as e:
        st.sidebar.error(f"백업 크롤러 통신 오류: {str(e)}")
    return scraped_items

def crawl_naver_news_article(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        article_body = soup.find("article", id="dic_area") or soup.find("div", id="articleBodyContents")
        if article_body:
            return article_body.get_text(strip=True)
    except Exception:
        pass
    return "본문 텍스트 자동 스크랩 제한 기사입니다. PDF 원문 저장을 이용해 확인하세요."

# Playwright 활용 이미지 및 원문 레이아웃 보존 PDF 변환 엔진
def convert_url_to_pdf(url):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)", viewport={"width": 1280, "height": 800})
            page = context.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            
            # 레이아웃 깨짐을 방지하기 위해 인쇄 스타일 백그라운드 활성화 플래그 적용
            pdf_bytes = page.pdf(format="A4", print_background=True, display_header_footer=False)
            browser.close()
            return pdf_bytes
    except Exception as e:
        return None

# --- 대시보드 코어 작동 로직 ---

# 상단 현황판 위젯 배치 (Metrics)
if st.session_state.scraped_data:
    df_metrics = pd.DataFrame(st.session_state.scraped_data)
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    m_col1.metric("📊 총 수집 기사 수", f"{len(df_metrics)} 건")
    m_col2.metric("🏷️ 매칭 대분류군", f"{len(df_metrics['대분류'].unique())} 개")
    m_col3.metric("🏢 참여 언론사 수", f"{len(df_metrics['언론사'].unique())} 사")
    m_col4.metric("📅 동기화 시각", datetime.now().strftime('%H:%M:%S'))
    st.write("---")

# 실행 제어 버튼
c1, c2 = st.columns([3, 1])
with c1:
    start_button = st.button("🔄 지금 스크랩 및 AI 분석 시작하기", type="primary", use_container_width=True)
with c2:
    if st.button("🧹 데이터 초기화"):
        st.session_state.scraped_data = []
        st.rerun()

if start_button:
    if not target_keywords:
        st.warning("⚠️ 검색할 키워드가 선택되지 않았습니다. 사이드바 설정을 확인하세요.")
    else:
        openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None
        all_scraped = []
        
        # 가독성 높은 실시간 상태 메인 대시보드 알림창 구동
        progress_bar = st.progress(0)
        status_notification = st.empty()
        
        for idx, keyword in enumerate(target_keywords):
            status_notification.info(f"🚀 현재 수집 중인 에너지 키워드: **[{keyword}]** (진행률: {idx+1}/{len(target_keywords)})")
            items = fetch_news_hybrid(keyword, naver_client_id, naver_client_secret)
            
            for item in items:
                title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", '"').replace("&apos;", "'")
                link = item['link']
                press = item['originallink'].split('//')[-1].split('/')[0] if 'originallink' in item else "네이버뉴스"
                
                if "news.naver.com" in link:
                    content = crawl_naver_news_article(link)
                else:
                    content = item['description'].replace("<b>", "").replace("</b>", "")
                
                large_cat, small_cat = classify_category(title, content, openai_client)
                summary = summarize_content(title, content, openai_client)
                
                # 요구사항 4번 규칙에 맞는 파일네임 설계 및 치환 적용
                raw_filename = f"({large_cat})({small_cat}){title}_{press}.pdf"
                safe_filename = clean_filename(raw_filename)
                
                all_scraped.append({
                    "대분류": large_cat,
                    "소분류": small_cat,
                    "기사제목": title,
                    "언론사": press,
                    "URL": link,
                    "본문": content,
                    "파일명": safe_filename,
                    "5줄요약": summary
                })
            progress_bar.progress((idx + 1) / len(target_keywords))
            
        status_notification.success("🎉 모든 지정 키워드의 실시간 뉴스 스크랩 및 카테고리 매핑이 완료되었습니다!")
        st.session_state.scraped_data = all_scraped
        st.toast("뉴스 가동 데이터 수집 완료!", icon="🌿")
        st.rerun()

# 결과물 시각화 테이블 및 다운로드 시스템 작동 영역
if st.session_state.scraped_data:
    df = pd.DataFrame(st.session_state.scraped_data)
    
    st.subheader("📋 실시간 수집 리포트 제어 프레임")
    
    # 1. 다중 선택 체크박스가 가미된 하이엔드 데이터 에디터 출력
    df.insert(0, "선택", False)
    edited_df = st.data_editor(
        df[["선택", "대분류", "소분류", "기사제목", "언론사", "파일명"]], 
        hide_index=True, 
        use_container_width=True
    )
    
    selected_indices = edited_df[edited_df["선택"] == True].index.tolist()
    
    # 2. 고급형 탭 분할 심층 정보 창 (요약 탭 / 본문 미리보기 탭)
    if selected_indices:
        st.write("---")
        st.subheader("🔍 선택 기사 상세 AI 인텔리전스 인프라")
        
        for idx in selected_indices:
            row = st.session_state.scraped_data[idx]
            st.markdown(f'<div class="report-card"><h4>🏷️ [{row["대분류"]} / {row["소분류"]}] {row["기사제목"]} <small style="color:#6B7280;">({row["언론사"]})</small></h4></div>', unsafe_allow_html=True)
            
            tab1, tab2 = st.tabs(["📋 OpenAI 기반 5줄 요약 보고서", "📰 수집된 본문 텍스트 미리보기"])
            with tab1:
                st.markdown(row['5줄요약'])
                st.caption(f"🔗 원문 주소 확인하기: {row['URL']}")
            with tab2:
                st.write(row['본문'][:1500] + ("..." if len(row['본문']) > 1500 else ""))
                
    # 3. 고화질 레이아웃 보존형 PDF 일괄 압축 ZIP 다운로드 모듈 파트
    st.write("---")
    st.subheader("🗂️ 리포트 파일 내보내기 익스포터")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📥 선택한 기사만 고화질 PDF (이미지 포함) ZIP 다운로드"):
            if not selected_indices:
                st.warning("테이블 좌측 체크박스에서 내보낼 뉴스 대상들을 체크해 주세요.")
            else:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    with st.spinner("Playwright 엔진이 각 웹사이트 기사의 고화질 레이아웃 및 이미지를 그대로 PDF로 가공 중입니다..."):
                        for idx in selected_indices:
                            item = st.session_state.scraped_data[idx]
                            pdf_bytes = convert_url_to_pdf(item['URL'])
                            if pdf_bytes:
                                zip_file.writestr(item['파일명'], pdf_bytes)
                
                st.download_button(
                    label="💾 [다운로드] 선택 기사 PDF 리포트.zip",
                    data=zip_buffer.getvalue(),
                    file_name=f"선택뉴스_인텔리전스_PDF_{datetime.now().strftime('%Y%m%d_%H%M')}.zip",
                    mime="application/zip",
                    use_container_width=True
                )
                
    with col2:
        if st.button("🗂️ 수집된 전체 기사 고화질 PDF 일괄 ZIP 다운로드"):
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                with st.spinner("수집된 모든 뉴스 페이지의 인쇄 레이아웃을 고해상도 PDF 파일로 일괄 인쇄 중입니다..."):
                    for item in st.session_state.scraped_data:
                        pdf_bytes = convert_url_to_pdf(item['URL'])
                        if pdf_bytes:
                            zip_file.writestr(item['파일명'], pdf_bytes)
            
            st.download_button(
                label="💾 [다운로드] 전체 기사 PDF 리포트.zip",
                data=zip_buffer.getvalue(),
                file_name=f"전체뉴스_인텔리전스_PDF_{datetime.now().strftime('%Y%m%d_%H%M')}.zip",
                mime="application/zip",
                use_container_width=True
            )
else:
    st.info("💡 좌측 패널의 설정값들을 확인하신 후 [지금 스크랩 및 AI 분석 시작하기] 버튼을 누르시면 업무 자동화 시스템이 시작됩니다.")
