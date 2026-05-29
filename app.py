import os
import re
import io
import zipfile
import streamlit as st
import pandas as pd
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from openai import OpenAI

# [Premium UI 가이드] 페이지 레이아웃 및 다크/라이트 하이브리드 인텔리전스 테마 세팅
st.set_page_config(
    page_title="기획예산처 탄소중립정책과 AI 인텔리전스", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# 라이브러리 검증 및 로드
try:
    import requests
    from bs4 import BeautifulSoup
    from openai import OpenAI
except ImportError:
    st.error("⚠️ 필수 라이브러리가 부족합니다. 환경 설정을 확인해주세요.")

# ----------------------------------------------------
# 🎨 PREMIUM BI DASHBOARD BRANDING CSS (돈 쓴 것 같은 UI)
# ----------------------------------------------------
st.markdown("""
    <style>
    /* 1. 전체 백그라운드를 세련된 미색 그레이로 전환 */
    .stApp {
        background-color: #F1F5F9;
        font-family: 'Inter', 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif;
    }
    
    /* 2. 메인 헤더 배너: 프리미엄 미니멀리즘 스타일 */
    .premium-header-card {
        background: #FFFFFF;
        padding: 2rem 2.5rem;
        border-radius: 16px;
        box-shadow: 0 4px 25px rgba(10, 37, 64, 0.04);
        border: 1px solid rgba(226, 232, 240, 0.8);
        margin-bottom: 2rem;
    }
    .premium-title {
        font-size: 2.4rem;
        font-weight: 800;
        color: #0A2540;
        letter-spacing: -0.08rem;
        margin: 0;
    }
    .premium-subtitle {
        font-size: 1.05rem;
        color: #64748B;
        margin-top: 0.6rem;
        font-weight: 400;
        line-height: 1.6;
    }
    
    /* 3. 컴포넌트 폰트 핏 및 스타일 튜닝 */
    h1, h2, h3, h4 {
        color: #0A2540 !important;
        font-weight: 700 !important;
    }
    
    /* 4. 대시보드 내부 컨텐츠 카드 (유리막 그림자 효과) */
    .dashboard-card {
        background: #FFFFFF;
        padding: 1.8rem;
        border-radius: 14px;
        box-shadow: 0 4px 20px rgba(15, 23, 42, 0.03);
        border: 1px solid rgba(226, 232, 240, 0.7);
        margin-bottom: 1.5rem;
    }
    
    /* 5. 하이테크 느낌의 3줄 요약 프레임 (네이비 & 사이언 매칭) */
    .ai-summary-box {
        background: linear-gradient(135deg, #FFFFFF 0%, #F8FAFC 100%);
        border-left: 6px solid #0A2540;
        padding: 1.5rem;
        border-radius: 4px 12px 12px 4px;
        box-shadow: inset 0 1px 3px rgba(0,0,0,0.02);
        line-height: 1.8;
        color: #334155;
    }
    
    /* 6. 정부 표준 버튼 -> 프리미엄 라운드 버튼으로 업그레이드 */
    .stButton>button {
        background: linear-gradient(135deg, #0A2540 0%, #1E3A8A 100%) !important;
        color: #FFFFFF !important;
        border-radius: 8px !important;
        border: none !important;
        font-weight: 600 !important;
        padding: 0.75rem 1.5rem !important;
        box-shadow: 0 4px 12px rgba(10, 37, 64, 0.15) !important;
        transition: all 0.2s ease;
    }
    .stButton>button:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 20px rgba(10, 37, 64, 0.25) !important;
    }
    
    /* 7. 멀티셀렉트 태그: 고급스러운 네이비 칩 펜시 스타일 */
    span[data-baseweb="tag"] {
        background-color: #0A2540 !important;
        color: #FFFFFF !important;
        border-radius: 6px !important;
        padding: 2px 6px !important;
        font-weight: 500;
    }
    
    /* 8. 데이터 에디터 표 내부 그리드 미세 튜닝 */
    div[data-testid="stDataEditor"] {
        border-radius: 12px !important;
        overflow: hidden;
        box-shadow: 0 4px 15px rgba(0,0,0,0.02);
    }
    
    /* 9. 스파이크 경고 시스템: 세련된 다크 로즈 경고창 */
    .premium-spike-alert {
        background: #FFF5F5;
        border: 1px solid #FEB2B2;
        border-left: 5px solid #E53E3E;
        padding: 1.2rem 1.6rem;
        border-radius: 12px;
        margin-bottom: 1.8rem;
        color: #9B2C2C;
        box-shadow: 0 4px 12px rgba(229, 62, 62, 0.03);
    }
    </style>
""", unsafe_allow_html=True)

# ----------------------------------------------------
# 🏛️ 상단 레이아웃 - 로고 & 타이틀 완전 고정형 아키텍처
# ----------------------------------------------------
if os.path.exists("logo.png"):
    st.logo("logo.png")

st.markdown('<div class="premium-header-card">', unsafe_allow_html=True)
header_logo_col, header_text_col = st.columns([1, 4.2])

with header_logo_col:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=210)
    else:
        st.markdown("<h2 style='margin:0; color:#0A2540; letter-spacing:-0.1rem;'>🏛️ 기획예산처</h2>", unsafe_allow_html=True)

with header_text_col:
    st.markdown("""
        <div class="premium-title">탄소중립정책과 기사 분석 에이전트</div>
        <div class="premium-subtitle">본 플랫폼은 기획예산처 탄소중립정책과의 실시간 정책 동향 관측을 위해 고도화된 빅데이터 다량 수집 체계 및 AI 심층 검증 기술을 결합한 프리미엄 행정 인텔리전스 시스템입니다.</div>
    """, unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ----------------------------------------------------
# CORE 시스템 인프라 및 세션 관리
# ----------------------------------------------------
if "scraped_data" not in st.session_state:
    st.session_state.scraped_data = []

st.sidebar.markdown("### 🔒 전산 자격 인증")
naver_client_id = st.sidebar.text_input("네이버 Client ID", value=st.secrets.get("NAVER_CLIENT_ID", ""), type="password")
naver_client_secret = st.sidebar.text_input("네이버 Client Secret", value=st.secrets.get("NAVER_CLIENT_SECRET", ""), type="password")
openai_api_key = st.sidebar.text_input("OpenAI API Key", value=st.secrets.get("OPENAI_API_KEY", ""), type="password")

st.sidebar.write("---")
st.sidebar.markdown("### 🎯 범정부 모니터링 키워드")

extended_keywords = [
    "탈탄소", "탄소중립", "넷제로", "ghg", "온실가스", "탄소배출", "배출권", 
    "배출권거래제", "탄소배출권", "ETS", "탄소세", "탄소시장", "IAA", 
    "산업가속화법", "산업가속화법률", "CBAM", "탄소국경조정제도", 
    "자발적 탄소시장", "ESG", "전환금융", "기후변화", "온실가스배출", 
    "녹색금융", "기후테크", "기후공시"
]

target_keywords = st.sidebar.multiselect(
    "조사 대상 정책 키워드", 
    options=extended_keywords, 
    default=["탄소중립", "탄소배출권", "배출권거래제", "CBAM", "ESG"]
)

def clean_filename(filename):
    cleaned = re.sub(r'[\s\\/:*?"<>|]+', '_', filename)
    if not cleaned.endswith(".hwp"):
        cleaned += ".hwp"
    return cleaned

def fetch_mass_news_stable(keywords, client_id, client_secret):
    scraped_items = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    for kw in keywords:
        if client_id and client_secret:
            url = f"https://openapi.naver.com/v1/search/news.json?query={kw}&display=50&sort=sim"
            headers_api = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret}
            try:
                res = requests.get(url, headers=headers_api, timeout=7)
                if res.status_code == 200:
                    items = res.json().get('items', [])
                    for item in items:
                        title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", '"').replace("&amp;", "&")
                        link = item['link']
                        press = item.get('originallink', '언론사').split('//')[-1].split('/')[0]
                        desc = item['description'].replace("<b>", "").replace("</b>", "").replace("&quot;", '"')
                        
                        if not any(x['link'] == link for x in scraped_items):
                            scraped_items.append({"title": title, "link": link, "press": press, "description": desc, "keyword": kw})
                    continue
            except Exception:
                pass
        
        try:
            for page in range(3):
                start_num = (page * 10) + 1
                search_url = f"https://search.naver.com/search.naver?where=news&query={kw}&start={start_num}"
                res = requests.get(search_url, headers=headers, timeout=5)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, "html.parser")
                    articles = soup.select("ul.list_news > li")
                    for art in articles:
                        title_el = art.select_one("a.news_tit")
                        if title_el:
                            title = title_el.get_text().strip()
                            link = title_el['href']
                            press_el = art.select_one("a.info.press")
                            press = press_el.get_text().replace("언론사 선정", "").strip() if press_el else "언론사"
                            desc_el = art.select_one("div.news_dsc")
                            desc = desc_el.get_text().strip() if desc_el else ""
                            
                            if not any(x['link'] == link for x in scraped_items):
                                scraped_items.append({"title": title, "link": link, "press": press, "description": desc, "keyword": kw})
        except Exception:
            pass
    return scraped_items

def crawl_article_body_stable(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(url, headers=headers, timeout=3)
        soup = BeautifulSoup(res.text, "html.parser")
        body = soup.find("article", id="dic_area") or soup.find("div", id="articleBodyContents") or soup.find("div", id="newsct_article")
        if body:
            return body.get_text(strip=True)
    except Exception:
        pass
    return "본문 데이터 추출 제한 기사입니다. 제공된 출처 링크를 참조하십시오."

def classify_and_summarize(title, content, openai_client):
    if openai_client is None:
        return "탄소중립", "일반", "- OpenAI API Key를 입력하시면 정교한 보고서용 3줄 개조식 요약이 자동 매칭됩니다."
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "너는 기획예산처의 탄소중립정책과 전문 기사 분석관이야. 기사 제목과 본문을 분석해 대분류군, 소분류군을 한 단어씩 선택하고 기사 내용을 공문서 지침에 맞춰 정확히 3줄의 개조식(- 문장형태)으로 요약해줘.\n출력 형식:\n대분류: 단어\n소분류: 단어\n요약:\n- 요약내용1\n- 요약내용2\n- 요약내용3"},
                {"role": "user", "content": f"제목: {title}\n본문: {content[:800]}"}
            ],
            temperature=0.2
        )
        res_text = response.choices[0].message.content.strip()
        large_cat, small_cat, summary = "탄소중립", "일반", "- 요약 데이터 파싱 실패"
        
        lines = res_text.split("\n")
        summary_lines = []
        for line in lines:
            if line.startswith("대분류:"): large_cat = line.split(":", 1)[1].strip()
            elif line.startswith("소분류:"): small_cat = line.split(":", 1)[1].strip()
            elif line.startswith("-"): summary_lines.append(line.strip())
        if summary_lines:
            summary = "\n".join(summary_lines)
        return large_cat, small_cat, summary
    except Exception:
        return "탄소중립", "일반", "- 분석 엔진 연동 일시 오류"

def generate_hwp_text_file(row_data):
    hwp_template = f"""[기획예산처 탄소중립정책과 - 행정 보도 요약 보고서]

1. 안 건 명 : {row_data['기사제목']}
2. 출 처 청 : {row_data['언론사']} (원문 주소: {row_data['URL']})
3. 정책 분류 : 대분류 [ {row_data['대분류']} ] / 소분류 [ {row_data['소분류']} ]
4. 수집 일시 : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

--------------------------------------------------------------------------------
◈ 핵심 요약 및 정책 시사점 (개조식 보고 서식)
--------------------------------------------------------------------------------
{row_data['5줄요약']}

--------------------------------------------------------------------------------
본 문서는 시스템을 통해 자동 생성된 기획예산처 내부 결재 및 참조용 보고 서식입니다.
"""
    return io.BytesIO(hwp_template.encode('utf-8'))

def generate_weekly_trend_summary(data_list, openai_client):
    if openai_client is None:
        return "💡 OpenAI API Key가 제공되지 않아 빅데이터 동향 종합 브리핑을 도출할 수 없습니다."
    
    context = ""
    for idx, d in enumerate(data_list[:15]):
        context += f"[{idx+1}] {d['기사제목']} -> {d['5줄요약']}\n"
        
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "너는 기획예산처의 경제동향 수석 심의관이야. 뉴스 요약 세트를 분석하여 [1. 종합 정책 평가], [2. 주요 리스크 관리 안건], [3. 부처별 예산·정책 대응 제언] 동향 보고서를 개조식(◼︎, ❍, - 기호 사용)으로 엄격하게 작성해줘."},
                {"role": "user", "content": f"수집된 빅데이터 동향 정보셋:\n{context}"}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"동향 리포트 구성 중 기술적 지연 발생: {str(e)}"

# ----------------------------------------------------
# 메인 비즈니스 로직 제어부
# ----------------------------------------------------
openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None

if st.session_state.scraped_data:
    df_spike = pd.DataFrame(st.session_state.scraped_data)
    kw_counts = df_spike['수집키워드'].value_counts()
    for kw, count in kw_counts.items():
        if count >= 6:
            st.markdown(f"""
                <div class="premium-spike-alert">
                    <span style="font-size:1.15rem; font-weight:700;">🚨 [동향 경보] 주요 정책 안건 이슈 스파이크 발생</span><br>
                    현재 데이터 스트리밍 분석 결과 <strong>'{kw}'</strong> 어젠다 관련 언론 보도가 단시간 내 <strong>{count}건 이상 폭증</strong>했습니다. 예산 심사 및 부처 협의 시 리스크 관리에 유의하십시오.
                </div>
            """, unsafe_allow_html=True)

col_btn1, col_btn2 = st.columns([4.2, 1])
with col_btn1:
    execute = st.button("🏛️ 범정부 지정 정책 키워드 기반 빅데이터 동향 수집 및 에이전트 분석 가동", use_container_width=True)
with col_btn2:
    if st.button("🧹 전산 데이터 초기화", use_container_width=True):
        st.session_state.scraped_data = []
        st.rerun()

if execute:
    status_bar = st.empty()
    status_bar.info("⏳ 고성능 포털 동적 수집 엔진을 가동합니다. 실시간 미디어 인덱스를 동기화 중입니다...")
    
    raw_news = fetch_mass_news_stable(target_keywords, naver_client_id, naver_client_secret)
    
    if not raw_news:
        status_bar.error("❌ 데이터 연동 실패. 네트워크 응답 처리를 다시 점검하십시오.")
    else:
        status_bar.info(f"🔎 총 {len(raw_news)}건의 정책 미디어 데이터 소스를 식별했습니다. AI 행정 요약 모델 구동 중...")
        
        analyzed_pool = []
        p_bar = st.progress(0)
        
        for index, item in enumerate(raw_news):
            full_body = crawl_article_body_stable(item['link'])
            if "데이터 추출 제한" in full_body:
                full_body = item['description']
                
            large_cat, small_cat, summary_text = classify_and_summarize(item['title'], full_body, openai_client)
            
            raw_filename = f"({large_cat})({small_cat}){item['title']}_{item['press']}"
            safe_hwp_name = clean_filename(raw_filename)
            
            analyzed_pool.append({
                "대분류": large_cat,
                "소분류": small_cat,
                "기사제목": item['title'],
                "언론사": item['press'],
                "URL": item['link'],
                "본문": full_body,
                "파일명": safe_hwp_name,
                "5줄요약": summary_text,
                "수집키워드": item['keyword']
            })
            p_bar.progress((index + 1) / len(raw_news))
            
        st.session_state.scraped_data = analyzed_pool
        status_bar.success(f"🏛️ 데이터 바인딩 완료. 총 {len(analyzed_pool)}건의 안건이 원격 데이터 인프라에 안착되었습니다.")
        st.rerun()

if st.session_state.scraped_data:
    df_display = pd.DataFrame(st.session_state.scraped_data)
    
    st.write("---")
    st.markdown("### 📊 빅데이터 기반 탄소중립 정책동향 종합 브리핑")
    with st.expander("📝 금주 탄소중립 정책동향 분석 리포트 확인", expanded=True):
        trend_report = generate_weekly_trend_summary(st.session_state.scraped_data, openai_client)
        st.markdown(f"<div class='ai-summary-box'>{trend_report}</div>", unsafe_allow_html=True)
        
    st.write("---")
    st.markdown("### 📋 실시간 수집 보도자료 종합 관제 센터")
    
    df_display.insert(0, "선택", False)
    
    edited_df = st.data_editor(
        df_display[["선택", "대분류", "소분류", "기사제목", "언론사", "수집키워드"]],
        hide_index=True,
        use_container_width=True,
        disabled=["대분류", "소분류", "기사제목", "언론사", "수집키워드"]
    )
    
    selected_rows = edited_df[edited_df["선택"] == True].index.tolist()
    
    if selected_rows:
        st.markdown("### 🔍 선택 안건별 심층 AI 행정 분석 피드")
        for idx in selected_rows:
            target_item = st.session_state.scraped_data[idx]
            st.markdown(f"""
                <div class="dashboard-card">
                    <span style="background:#0A2540; color:#FFFFFF; padding:4px 10px; border-radius:4px; font-size:0.8rem; font-weight:600;">
                        {target_item['대분류']} / {target_item['소분류']}
                    </span>
                    <h4 style="margin: 0.8rem 0 0.3rem 0; font-size:1.3rem;">{target_item['기사제목']}</h4>
                    <p style="color:#64748B; font-size:0.85rem; margin-bottom:1rem;">출처 본청: {target_item['언론사']} | 인덱싱 키워드: {target_item['수집키워드']}</p>
                    <div class="ai-summary-box">
                        <strong>📄 AI 에이전트 요약 개조식 보고 서식</strong><br>
                        {target_item['5줄요약']}
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
        st.write("---")
        st.markdown("### 🖨️ 정부 표준 결재용 한글(HWP) 문서 출력 컨트롤러")
        col_hwp1, col_hwp2 = st.columns([1, 1])
        
        with col_hwp1:
            zip_hwp_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_hwp_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for idx in selected_rows:
                    item_data = st.session_state.scraped_data[idx]
                    hwp_file_stream = generate_hwp_text_file(item_data)
                    zip_file.writestr(item_data['파일명'], hwp_file_stream.getvalue())
            
            st.download_button(
                label="📥 선택 안건 표준 공문서(HWP) 파일셋 다운로드 (.zip)",
                data=zip_hwp_buffer.getvalue(),
                file_name=f"기획예산처_탄소중립_선택보고서_{datetime.now().strftime('%Y%m%d')}.zip",
                mime="application/zip",
                use_container_width=True
            )
        with col_hwp2:
            st.markdown("<p style='color:#64748B; font-size:0.9rem; padding-top:8px;'>💡 상단 관제 센터 테이블에서 체크박스를 터치하면 결재용 파일셋 빌더에 즉각 자동 누적 반영됩니다.</p>", unsafe_allow_html=True)
else:
    st.markdown("""
        <div style="text-align:center; padding:5rem; color:#94A3B8;">
            <p style="font-size:1.2rem;">🏛️ 플랫폼 데이터 초기화 상태입니다.</p>
            <p style="font-size:0.9rem;">상단의 [빅데이터 동향 수집 및 에이전트 분석 가동] 버튼을 클릭하시면 실시간 인텔리전스 체계가 수립됩니다.</p>
        </div>
    """, unsafe_allow_html=True)
