import os
import re
import io
import zipfile
import streamlit as st
import pandas as pd
from datetime import datetime

# 1. 페이지 레이아웃 및 테마 기본 설정
st.set_page_config(page_title="탄소중립 뉴스 정보 분석 시스템", layout="wide", initial_sidebar_state="expanded")

# 라이브러리 정상 임포트 체크
try:
    import requests
    from bs4 import BeautifulSoup
    from openai import OpenAI
    from playwright.sync_api import sync_playwright
except ImportError:
    st.error("필수 라이브러리가 부족합니다. GitHub의 requirements.txt 세팅을 확인해주세요.")

# 기획예산처 공식 로고 기반 행정 시스템 디자인 주입
st.markdown("""
    <style>
    /* 전체 배경 및 기본 폰트 색상 정돈 */
    .stApp { background-color: #F8FAFC; }
    h1, h2, h3 { color: #0A2540 !important; font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; }
    
    /* 공공기관 메인 상단 배너 인프라 (로고 우측 정렬 구조) */
    .gov-banner-container {
        background-color: #FFFFFF;
        padding: 1.5rem 2rem;
        border-bottom: 3px solid #0A2540;
        border-radius: 4px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        margin-bottom: 2rem;
        display: flex;
        align-items: center;
    }
    .gov-logo-area {
        flex: 0 0 auto;
        margin-right: 2rem;
        display: flex;
        align-items: center;
        border-right: 1px solid #E2E8F0;
        padding-right: 2rem;
    }
    .gov-text-area {
        flex: 1 1 auto;
    }
    .gov-title { font-size: 2rem; font-weight: 700; color: #0A2540; letter-spacing: -0.05rem; margin: 0; }
    .gov-subtitle { font-size: 0.95rem; color: #64748B; margin-top: 0.4rem; font-weight: 400; line-height: 1.4; }
    
    /* 버튼 스타일 관공서 규격화 */
    .stButton>button {
        background-color: #0A2540 !important;
        color: #FFFFFF !important;
        border-radius: 3px !important;
        border: 1px solid #0A2540 !important;
        font-weight: 600 !important;
        padding: 0.5rem 1rem !important;
        transition: all 0.2s ease;
    }
    .stButton>button:hover {
        background-color: #1E3A8A !important;
        border-color: #1E3A8A !important;
    }
    
    /* 초기화 버튼 (서브 버튼) 스타일 개별 격리 */
    div[data-testid="stHorizontalBlock"] > div:nth-child(2) .stButton>button {
        background-color: #FFFFFF !important;
        color: #475569 !important;
        border: 1px solid #CBD5E1 !important;
    }
    div[data-testid="stHorizontalBlock"] > div:nth-child(2) .stButton>button:hover {
        background-color: #F1F5F9 !important;
    }
    
    /* 보고서 카드 스타일 */
    .report-card {
        background-color: #FFFFFF;
        padding: 1.5rem;
        border-radius: 4px;
        border: 1px solid #E2E8F0;
        border-left: 4px solid #0A2540;
        margin-bottom: 1.2rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.02);
    }
    .report-card h4 { margin: 0 0 0.5rem 0; font-size: 1.15rem; color: #0A2540; }
    
    /* 사이드바 스타일 공직풍 매핑 */
    .css-163ttbj, [data-testid="stSidebar"] {
        background-color: #1E293B !important;
    }
    .css-163ttbj .stMarkdown, [data-testid="stSidebar"] .stMarkdown h3 {
        color: #FFFFFF !important;
    }
    label { color: #334155 !important; font-weight: 600 !important; }
    </style>
""", unsafe_allow_html=True)

# 메인 행정 헤더 영역 가동 (로고 레이아웃 바인딩)
# 로고 파일이 app.py와 동일한 루트 디렉토리에 존재하면 최적의 크기(높이 65px)로 가시성을 확보합니다.
logo_html_content = ""
if os.path.exists("logo.png"):
    import base64
    with open("logo.png", "rb") as f:
        encoded_logo = base64.b64encode(f.read()).decode()
    logo_html_content = f'<div class="gov-logo-area"><img src="data:image/png;base64,{encoded_logo}" style="height: 65px; width: auto; object-fit: contain;"></div>'
else:
    logo_html_content = '<div class="gov-logo-area" style="font-weight:bold; color:#0A2540; font-size:1.3rem;">🏛️ 기획예산처</div>'

st.markdown(f"""
    <div class="gov-banner-container">
        {logo_html_content}
        <div class="gov-text-area">
            <div class="gov-title">탄소중립 뉴스 정보 분석 시스템</div>
            <div class="gov-subtitle">본 시스템은 국가 기후변화 및 탄소중립 정책 수립 지원을 위해 실시간 언론 보도 자료를 수집·요약하는 공공 목적의 인텔리전스 프레임워크입니다.</div>
        </div>
    </div>
""", unsafe_allow_html=True)

# 2. 세션 상태 데이터 유지 보장
if "scraped_data" not in st.session_state:
    st.session_state.scraped_data = []

# 고정 대분류 / 소분류 정의
LARGE_CATEGORIES = ["배출권", "탄소시장", "탄소세", "ESG", "전기차", "탄소중립", "CBAM", "IAA", "기후변화"]
SMALL_CATEGORIES = ["자발적 탄소시장", "국제감출", "탄소제거", "기후공시", "전환금융", "녹색금융", "재생에너지", "기후테크", "온실가스"]

# 3. 사이드바 제어 패널 설계
st.sidebar.markdown("### 🔒 시스템 자격 인증")
secrets_id = st.secrets.get("NAVER_CLIENT_ID", "")
secrets_secret = st.secrets.get("NAVER_CLIENT_SECRET", "")
secrets_openai = st.secrets.get("OPENAI_API_KEY", "")

naver_client_id = st.sidebar.text_input("네이버 Client ID", value=secrets_id, type="password")
naver_client_secret = st.sidebar.text_input("네이버 Client Secret", value=secrets_secret, type="password")
openai_api_key = st.sidebar.text_input("OpenAI API Key", value=secrets_openai, type="password")

st.sidebar.write("---")
st.sidebar.markdown("### 🎯 조사 대상 지정 키워드")

extended_keywords = [
    "탈탄소", "탄소중립", "넷제로", "ghg", "온실가스", "탄소배출", "배출권", 
    "배출권거래제", "탄소배출권", "ETS", "탄소세", "탄소시장", "IAA", 
    "산업가속화법", "산업가속화법률", "CBAM", "탄소국경조정제도", 
    "자발적 탄소시장", "ESG", "전환금융", "기후변화", "온실가스배출", 
    "녹색금융", "기후테크", "기후공시"
]

target_keywords = st.sidebar.multiselect(
    "범정부 모니터링 키워드 선택", 
    options=extended_keywords, 
    default=extended_keywords
)

# 4. 파일네임 특수문자 예외 처리 전처리 함수
def clean_filename(filename):
    cleaned = re.sub(r'[\s\\/:*?"<>|]+', '_', filename)
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
        return "💡 OpenAI API Key가 입력되지 않아 행정 요약문을 도출할 수 없습니다."
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "너는 대한민국 공공기관의 기후경제 담당 서기관이야. 제공된 뉴스 본문을 정독하여 주요 정부 시사점과 객관적 팩트 위주로 '반드시 5줄 이내의 문장'으로 정갈하게 요약해줘. 명조계열 보고서 서식처럼 개조식 개요 형태(- 문장형태)로 출력해줘."},
                {"role": "user", "content": f"제목: {title}\n본문: {content}"}
            ],
            temperature=0.1
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ 요약 실패: {str(e)}"

# 7. 네트워크 예외 대비 하이브리드 수집 로직
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
    return "본문 텍스트 자동 스크랩 제한 기사입니다. PDF 원문 출력을 이용하십시오."

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

# --- 대시보드 데이터 제어 로직 ---

# 상단 종합 지표 대시보드
if st.session_state.scraped_data:
    df_metrics = pd.DataFrame(st.session_state.scraped_data)
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    m_col1.metric("📊 누적 수집 보도 건수", f"{len(df_metrics)} 건")
    m_col2.metric("🏷️ 매칭 대분류 지표", f"{len(df_metrics['대분류'].unique())} 종")
    m_col3.metric("🏢 모니터링 언론사", f"{len(df_metrics['언론사'].unique())} 개사")
    m_col4.metric("📅 최종 동기화 시각", datetime.now().strftime('%Y-%m-%d %H:%M'))
    st.markdown("<br>", unsafe_allow_html=True)

# 주요 행정 명령 제어판
c1, c2 = st.columns([3.5, 1])
with c1:
    start_button = st.button("🏛️ 범정부 탄소중립 보도자료 종합 수집 및 AI 분석 가동", use_container_width=True)
with c2:
    if st.button("🧹 수집 데이터 초기화", use_container_width=True):
        st.session_state.scraped_data = []
        st.rerun()

if start_button:
    if not target_keywords:
        st.warning("⚠️ 모니터링 대상 키워드가 지정되지 않았습니다.")
    else:
        openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None
        all_scraped = []
        
        progress_bar = st.progress(0)
        status_notification = st.empty()
        
        for idx, keyword in enumerate(target_keywords):
            status_notification.info(f"📋 공적 데이터 수집 중: 키워드 **[{keyword}]** (진행률: {idx+1}/{len(target_keywords)})")
            items = fetch_news_hybrid(keyword, naver_client_id, naver_client_secret)
            
            for item in items:
                title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", '"').replace("&apos;", "'")
                link = item['link']
                press = item['originallink'].split('//')[-1].split('/')[0] if 'originallink' in item else "언론기관"
                
                if any(x['URL'] == link for x in all_scraped):
                    continue
                
                if "news.naver.com" in link:
                    content = crawl_naver_news_article(link)
                else:
                    content = item['description'].replace("<b>", "").replace("</b>", "")
                
                large_cat, small_cat = classify_category(title, content, openai_client)
                summary = summarize_content(title, content, openai_client)
                
                # (대분류)(소분류)기사제목_언론사 포맷 생성 규칙 바인딩
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
                    "PDF상태": "⏳ 대기 중"
                })
            progress_bar.progress((idx + 1) / len(target_keywords))
            
        status_notification.success("🎉 뉴스 스크랩 및 범주화 체계 구축이 완료되었습니다.")
        st.session_state.scraped_data = all_scraped
        st.rerun()

# 행정 보고서 산출물 인프라 영역
if st.session_state.scraped_data:
    df = pd.DataFrame(st.session_state.scraped_data)
    st.subheader("📋 국가 기후변화 보도자료 종합 관제 테이블")
    
    df.insert(0, "선택", False)
    edited_df = st.data_editor(
        df[["선택", "대분류", "소분류", "기사제목", "언론사", "파일명", "PDF상태"]], 
        hide_index=True, 
        use_container_width=True,
        disabled=["대분류", "소분류", "기사제목", "언론사", "파일명", "PDF상태"]
    )
    selected_indices = edited_df[edited_df["선택"] == True].index.tolist()
    
    # 공문서 심층 검토용 탭 분할 아키텍처
    if selected_indices:
        st.write("---")
        st.subheader("🔍 주요 안건별 행정 분석 및 AI 요약 보고")
        for idx in selected_indices:
            row = st.session_state.scraped_data[idx]
            st.markdown(f'<div class="report-card"><h4>📌 [{row["대분류"]} / {row["소분류"]}] {row["기사제목"]} <small style="color:#64748B; font-weight:normal;"> - {row["언론사"]}</small></h4></div>', unsafe_allow_html=True)
            
            tab1, tab2 = st.tabs(["📋 AI 정책 분석 요약문 (5줄 이내)", "📰 보도자료 수집 원문 데이터"])
            with tab1:
                st.markdown(row['5줄요약'])
                st.caption(f"🌐 데이터 출처 관제 주소: {row['URL']}")
            with tab2:
                st.write(row['본문'][:1500] + ("..." if len(row['본문']) > 1500 else ""))
                
    # PDF 산출물 행정 익스포터
    st.write("---")
    st.subheader("🗂️ 기후에너지 정책 보고서 파일 익스포트")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📥 선택한 안건 문서 고화질 PDF (이미지 포함) ZIP 생성"):
            if not selected_indices:
                st.warning("선택 항목 관제 테이블에서 출력할 기사를 선택해 주십시오.")
            else:
                zip_buffer = io.BytesIO()
                status_track = st.empty()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for i, idx in enumerate(selected_indices):
                        item = st.session_state.scraped_data[idx]
                        status_track.info(f"⏳ (프로세스 {i+1}/{len(selected_indices)}) [{item['언론사']}] 행정 PDF 빌드 및 전자 서식 보존 인쇄 중...")
                        
                        pdf_bytes = convert_url_to_pdf(item['URL'])
                        if pdf_bytes:
                            zip_file.writestr(item['파일명'], pdf_bytes)
                            st.session_state.scraped_data[idx]["PDF상태"] = "✅ 출력 성공"
                        else:
                            st.session_state.scraped_data[idx]["PDF상태"] = "❌ 출력 실패"
                
                status_track.success("✨ 선택된 안건 보도자료의 PDF 포맷 가공 절차가 완료되었습니다.")
                st.download_button(
                    label="💾 [다운로드] 선택 안건 PDF 리포트 파일셋.zip",
                    data=zip_buffer.getvalue(),
                    file_name=f"정부_탄소중립_선택리포트_{datetime.now().strftime('%Y%m%d')}.zip",
                    mime="application/zip",
                    use_container_width=True
                )
                
    with col2:
        if st.button("🗂️ 수집된 전체 보도자료 고화질 PDF 일괄 ZIP 내보내기"):
            zip_buffer = io.BytesIO()
            status_track = st.empty()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for i, item in enumerate(st.session_state.scraped_data):
                    status_track.info(f"⏳ (프로세스 {i+1}/{len(st.session_state.scraped_data)}) [{item['언론사']}] 공공 서식화 일괄 인쇄 처리 중...")
                    
                    pdf_bytes = convert_url_to_pdf(item['URL'])
                    if pdf_bytes:
                        zip_file.writestr(item['파일명'], pdf_bytes)
                        item["PDF상태"] = "✅ 출력 성공"
                    else:
                        item["PDF상태"] = "❌ 출력 실패"
            
            status_track.success("✨ 모니터링된 전 건의 PDF 전산 서식화 인쇄가 완료되었습니다.")
            st.download_button(
                label="💾 [다운로드] 전체 안건 PDF 리포트 파일셋.zip",
                data=zip_buffer.getvalue(),
                file_name=f"정부_탄소중립_전체리포트_{datetime.now().strftime('%Y%m%d')}.zip",
                mime="application/zip",
                use_container_width=True
            )
else:
    st.info("💡 모니터링 대상 설정값을 검토하신 후 상단의 [범정부 탄소중립 보도자료 종합 수집 및 AI 분석 가동] 단추를 클릭하시면 정식 분석 공정이 수립됩니다.")
