import os
import re
import io
import zipfile
import streamlit as st
import pandas as pd
from datetime import datetime

# 1. 페이지 레이아웃 및 테마 기본 설정
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

# 고정 대분류 / 소분류 정의
LARGE_CATEGORIES = ["배출권", "탄소시장", "탄소세", "ESG", "전기차", "탄소중립", "CBAM", "IAA", "기후변화"]
SMALL_CATEGORIES = ["자발적 탄소시장", "국제감출", "탄소제거", "기후공시", "전환금융", "녹색금융", "재생에너지", "기후테크", "온실가스"]

# 3. 사이드바 제어 패널 설계
st.sidebar.markdown("### 🔑 API 자격 증명")
secrets_id = st.secrets.get("NAVER_CLIENT_ID", "")
secrets_secret = st.secrets.get("NAVER_CLIENT_SECRET", "")
secrets_openai = st.secrets.get("OPENAI_API_KEY", "")

naver_client_id = st.sidebar.text_input("네이버 Client ID", value=secrets_id, type="password")
naver_client_secret = st.sidebar.text_input("네이버 Client Secret", value=secrets_secret, type="password")
openai_api_key = st.sidebar.text_input("OpenAI API Key", value=secrets_openai, type="password")

st.sidebar.write("---")
st.sidebar.markdown("### 🎯 확장된 타겟 키워드 목록")

# 26개 확장 키워드 리스트 전면 영구 적용
extended_keywords = [
    "탈탄소", "탄소중립", "넷제로", "ghg", "온실가스", "탄소배출", "배출권", 
    "배출권거래제", "탄소배출권", "ETS", "탄소세", "탄소시장", "IAA", 
    "산업가속화법", "산업가속화법률", "CBAM", "탄소국경조정제도", 
    "자발적 탄소시장", "ESG", "전환금융", "기후변화", "온실가스배출", 
    "녹색금융", "기후테크", "기후공시"
]

target_keywords = st.sidebar.multiselect(
    "수집 및 분석을 진행할 키워드를 선택/편집하세요", 
    options=extended_keywords, 
    default=extended_keywords
)

# 4. 파일네임 특수문자 예외 처리 전처리 함수 (\ / : * ? " < > | 공백 치환)
def clean_filename(filename):
    # 탐색기 가시성을 위해 요구사항에 맞춤 설계 수행
    cleaned = re.sub(r'[\s\\/:*?"<>|]+', '_', filename)
    # 확장자 중복 방지 처리
    if cleaned.endswith("__pdf") or cleaned.endswith("_pdf"):
        cleaned = cleaned.rsplit('_', 1)[0]
    if not cleaned.endswith(".pdf"):
        cleaned += ".pdf"
    return cleaned

# 5. 연관어 가중치가 포함된 고도화 하이브리드 매칭 엔진
def classify_category(title, content, openai_client=None):
    text = f"{title} {content}".lower()
    
    large_counts = {cat: text.count(cat.lower()) for cat in LARGE_CATEGORIES}
    small_counts = {cat: text.count(cat.lower()) for cat in SMALL_CATEGORIES}
    
    if "ets" in text or "배출권거래제" in text:
        large_counts["배출권"] += 3
        large_counts["탄소시장"] += 2
    if "넷제로" in text or "탈탄소" in text:
        large_counts["탄소중립"] += 2
    if "ghg" in text or "온실가스배출" in text:
        small_counts["온실가스"] += 3
    if "탄소국경조정제도" in text:
        large_counts["CBAM"] += 4
    if "산업가속화" in text:
        large_counts["IAA"] += 4
        
    max_large_val = max(large_counts.values())
    max_small_val = max(small_counts.values())
    
    best_large = max(large_counts, key=large_counts.get) if max_large_val > 0 else None
    best_small = max(small_counts, key=small_counts.get) if max_small_val > 0 else None
    
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

# 6. OpenAI 기반 5줄 이내 핵심 요약 함수
def summarize_content(title, content, openai_client):
    if not openai_client:
        return "💡 OpenAI API Key가 입력되지 않아 요약을 제공하지 않습니다."
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

# 7. 사내 방화벽 대비용 하이브리드 뉴스 수집 엔진
def fetch_news_hybrid(keyword, client_id, client_secret):
    if client_id and client_secret:
        url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display=3&sort=sim"
        headers = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret}
        try:
            response = requests.get(url, headers=headers, timeout=3)
            if response.status_code == 200:
                return response.json().get('items', [])
        except Exception:
            pass
            
    # 사내 네트워크 차단 시 백업 일반 검색 크롤러 기동
    scraped_items = []
    try:
        search_url = f"https://search.naver.com/search.naver?where=news&query={keyword}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(search_url, headers=headers, timeout=4)
        soup = BeautifulSoup(res.text, "html.parser")
        
        articles = soup.select("ul.list_news > li")
        for art in articles[:2]: 
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
    except Exception:
        pass
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
            pdf_bytes = page.pdf(format="A4", print_background=True, display_header_footer=False)
            browser.close()
            return pdf_bytes
    except Exception:
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
    start_button = st.button("🔄 확장 키워드 기반 전면 스크랩 및 AI 분석 가동", type="primary", use_container_width=True)
with c2:
    if st.button("🧹 데이터 초기화"):
        st.session_state.scraped_data = []
        st.rerun()

if start_button:
    if not target_keywords:
        st.warning("⚠️ 검색할 키워드가 선택되지 않았습니다. 사이드바 패널을 조정해 주세요.")
    else:
        openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None
        all_scraped = []
        
        progress_bar = st.progress(0)
        status_notification = st.empty()
        
        for idx, keyword in enumerate(target_keywords):
            status_notification.info(f"🚀 현재 수집 중인 기후 에너지 키워드: **[{keyword}]** (진행률: {idx+1}/{len(target_keywords)})")
            items = fetch_news_hybrid(keyword, naver_client_id, naver_client_secret)
            
            for item in items:
                title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", '"').replace("&apos;", "'")
                link = item['link']
                press = item['originallink'].split('//')[-1].split('/')[0] if 'originallink' in item else "뉴스포털"
                
                # 중복 수집 주소 방지 로직
                if any(x['URL'] == link for x in all_scraped):
                    continue
                
                if "news.naver.com" in link:
                    content = crawl_naver_news_article(link)
                else:
                    content = item['description'].replace("<b>", "").replace("</b>", "")
                
                large_cat, small_cat = classify_category(title, content, openai_client)
                summary = summarize_content(title, content, openai_client)
                
                # 스크린샷과 동일한 완벽한 명명 규칙 바인딩
                raw_filename = f"({large_cat})({small_cat}){title}_{press}"
                safe_filename = clean_filename(raw_filename)
                
                all_scraped.append({
                    "대분류": large_cat,
                    "소분류": small_cat,
                    "기사제목": title,
                    "언론사": press,
                    "URL": link,
                    "본문": content,
                    "파일명": safe_filename,
                    "5줄요약": summary,
                    "PDF상태": "⏳ 준비 완료"  # 실시간 상태 인디케이터 초기값 설정
                })
            progress_bar.progress((idx + 1) / len(target_keywords))
            
        status_notification.success("🎉 모든 지정 키워드의 실시간 리포트 셋업이 완료되었습니다!")
        st.session_state.scraped_data = all_scraped
        st.toast("뉴스 가동 데이터 수집 완료!", icon="🌿")
        st.rerun()

# 테이블 시각화 프레임 핸들러
if st.session_state.scraped_data:
    df = pd.DataFrame(st.session_state.scraped_data)
    st.subheader("📋 실시간 수집 리포트 제어 프레임")
    
    df.insert(0, "선택", False)
    # 테이블 내부에 PDF 빌드 상태 컬럼 추가 노출
    edited_df = st.data_editor(
        df[["선택", "대분류", "소분류", "기사제목", "언론사", "파일명", "PDF상태"]], 
        hide_index=True, 
        use_container_width=True,
        disabled=["대분류", "소분류", "기사제목", "언론사", "파일명", "PDF상태"]
    )
    selected_indices = edited_df[edited_df["선택"] == True].index.tolist()
    
    # 탭 분할 상세 인포 컴포넌트
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
                
    # PDF 내보내기 모듈 익스포터
    st.write("---")
    st.subheader("🗂️ 리포트 파일 내보내기 익스포터")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📥 선택한 기사만 고화질 PDF (이미지 포함) ZIP 다운로드"):
            if not selected_indices:
                st.warning("테이블 좌측 체크박스에서 내보낼 기사들을 체크해 주세요.")
            else:
                zip_buffer = io.BytesIO()
                status_track = st.empty()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for i, idx in enumerate(selected_indices):
                        item = st.session_state.scraped_data[idx]
                        status_track.info(f"⏳ ({i+1}/{len(selected_indices)}) [{item['언론사']}] 기사 PDF 빌드 중...")
                        
                        pdf_bytes = convert_url_to_pdf(item['URL'])
                        if pdf_bytes:
                            zip_file.writestr(item['파일명'], pdf_bytes)
                            st.session_state.scraped_data[idx]["PDF상태"] = "✅ 변환 성공"
                        else:
                            st.session_state.scraped_data[idx]["PDF상태"] = "❌ 변환 실패"
                
                status_track.success("✨ 선택한 모든 기사의 PDF 변환 및 압축이 완수되었습니다!")
                st.download_button(
                    label="💾 [다운로드 완료] 선택 기사 PDF 리포트.zip",
                    data=zip_buffer.getvalue(),
                    file_name=f"선택뉴스_인텔리전스_PDF_{datetime.now().strftime('%Y%m%d_%H%M')}.zip",
                    mime="application/zip",
                    use_container_width=True
                )
                
    with col2:
        if st.button("🗂️ 수집된 전체 기사 고화질 PDF 일괄 ZIP 다운로드"):
            zip_buffer = io.BytesIO()
            status_track = st.empty()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for i, item in enumerate(st.session_state.scraped_data):
                    status_track.info(f"⏳ ({i+1}/{len(st.session_state.scraped_data)}) [{item['언론사']}] 전체 리포트 PDF 인쇄 중...")
                    
                    pdf_bytes = convert_url_to_pdf(item['URL'])
                    if pdf_bytes:
                        zip_file.writestr(item['파일명'], pdf_bytes)
                        item["PDF상태"] = "✅ 변환 성공"
                    else:
                        item["PDF상태"] = "❌ 변환 실패"
            
            status_track.success("✨ 모든 뉴스 데이터의 전체 PDF 가공이 완료되었습니다!")
            st.download_button(
                label="💾 [다운로드 완료] 전체 기사 PDF 리포트.zip",
                data=zip_buffer.getvalue(),
                file_name=f"전체뉴스_인텔리전스_PDF_{datetime.now().strftime('%Y%m%d_%H%M')}.zip",
                mime="application/zip",
                use_container_width=True
            )
else:
    st.info("💡 좌측 패널의 확장 키워드 목록을 확인하신 후 [확장 키워드 기반 전면 스크랩 및 AI 분석 가동] 버튼을 누르시면 자동 수집이 시작됩니다.")
