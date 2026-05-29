import os
import re
import io
import zipfile
import requests
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from bs4 import BeautifulSoup
from openai import OpenAI

# [Premium UI 가이드] 페이지 레이아웃 및 다크/라이트 하이브리드 인텔리전스 테마 세팅
st.set_page_config(
    page_title="기획예산처 탄소중립정책과 AI 인텔리전스", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

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
# 사이드바 최상단 로고 배치
if os.path.exists("logo.png"):
    st.logo("logo.png")

# 메인 브랜딩 헤더 카드 구동
st.markdown('<div class="premium-header-card">', unsafe_allow_html=True)
header_logo_col, header_text_col = st.columns([1, 4.2])

with header_logo_col:
    if os.path.exists("logo.png"):
        # 왜곡이나 마진 말림 현상을 원천 배제한 크기 고정 배치
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
if "all_history" not in st.session_state:
    st.session_state.all_history = []
if "library" not in st.session_state:
    st.session_state.library = []

# 사이드바 자격 인증 및 다량 키워드 설정
st.sidebar.markdown("### 🔒 전산 자격 인증")
naver_client_id = st.sidebar.text_input("네이버 Client ID", value=st.secrets.get("NAVER_CLIENT_ID", ""), type="password")
naver_client_secret = st.sidebar.text_input("네이버 Client Secret", value=st.secrets.get("NAVER_CLIENT_SECRET", ""), type="password")
openai_api_key = st.sidebar.text_input("OpenAI API Key", value=st.secrets.get("OPENAI_API_KEY", ""), type="password")

st.sidebar.write("---")
st.sidebar.markdown("### 🎯 범정부 모니터링 키워드")

# 복구 완료된 25개 전체 정책 핵심 키워드 풀
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

# ----------------------------------------------------
# 날짜 파싱 및 48시간 필터 유틸리티
# ----------------------------------------------------
HOURS_48 = timedelta(hours=48)

def to_naive_local(dt):
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone().replace(tzinfo=None)
    return dt

def parse_article_date(date_str):
    """다양한 형식의 기사 발행일 문자열을 datetime으로 변환"""
    if not date_str:
        return None
    date_str = date_str.strip()

    try:
        return to_naive_local(parsedate_to_datetime(date_str))
    except Exception:
        pass

    relative_patterns = [
        (r"(\d+)\s*분\s*전", "minutes"),
        (r"(\d+)\s*시간\s*전", "hours"),
        (r"(\d+)\s*일\s*전", "days"),
    ]
    now = datetime.now()
    for pattern, unit in relative_patterns:
        match = re.match(pattern, date_str)
        if match:
            value = int(match.group(1))
            if unit == "minutes":
                return now - timedelta(minutes=value)
            if unit == "hours":
                return now - timedelta(hours=value)
            if unit == "days":
                return now - timedelta(days=value)

    date_patterns = [
        r"(\d{4})\.(\d{1,2})\.(\d{1,2})\.?",
        r"(\d{4})-(\d{1,2})-(\d{1,2})",
        r"(\d{4})/(\d{1,2})/(\d{1,2})",
    ]
    for pattern in date_patterns:
        match = re.search(pattern, date_str)
        if match:
            try:
                return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            except ValueError:
                pass

    return None

def is_within_48_hours(dt):
    """현재 시각 기준 48시간 이내 발행 여부"""
    dt = to_naive_local(dt)
    if dt is None:
        return False
    return datetime.now() - dt <= HOURS_48

def format_pub_date(dt):
    if dt is None:
        return ""
    return to_naive_local(dt).strftime("%Y-%m-%d %H:%M")

def sync_library_from_bookmarks(data_list, edited_df):
    """대시보드 북마크 체크 상태를 session_state.library에 동기화"""
    library_urls = {item["URL"] for item in st.session_state.library}
    data_by_url = {item["URL"]: item for item in data_list}

    for _, row in edited_df.iterrows():
        url = row["URL"]
        if row.get("북마크", False):
            if url not in library_urls and url in data_by_url:
                st.session_state.library.append(data_by_url[url])
                library_urls.add(url)
        elif url in library_urls:
            st.session_state.library = [x for x in st.session_state.library if x["URL"] != url]
            library_urls.discard(url)

def refresh_scraped_data_from_history():
    """all_history 중 48시간 이내 기사만 scraped_data(대시보드)에 반영"""
    st.session_state.scraped_data = [
        item for item in st.session_state.all_history
        if is_within_48_hours(parse_article_date(item.get("발행일시", "")))
    ]

def clean_filename(filename):
    cleaned = re.sub(r'[\s\\/:*?"<>|]+', '_', filename)
    if not cleaned.endswith(".hwp"):
        cleaned += ".hwp"
    return cleaned

# 타임아웃을 완전 방어하는 고성능 실시간 다량 수집 엔진
def fetch_mass_news_stable(keywords, client_id, client_secret, existing_urls=None):
    scraped_items = []
    existing_urls = existing_urls or set()
    seen_links = set(existing_urls)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    for kw in keywords:
        if client_id and client_secret:
            url = f"https://openapi.naver.com/v1/search/news.json?query={kw}&display=50&sort=date"
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
                        pub_dt = parse_article_date(item.get('pubDate', ''))

                        if link in seen_links:
                            continue
                        if not is_within_48_hours(pub_dt):
                            continue

                        seen_links.add(link)
                        scraped_items.append({
                            "title": title,
                            "link": link,
                            "press": press,
                            "description": desc,
                            "keyword": kw,
                            "pub_date": format_pub_date(pub_dt),
                        })
                    continue
            except Exception:
                pass
        
        # 백업 서브 크롤링 파트
        try:
            for page in range(3):
                start_num = (page * 10) + 1
                search_url = f"https://search.naver.com/search.naver?where=news&query={kw}&start={start_num}&sort=1"
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

                            date_el = art.select_one("span.info")
                            date_text = date_el.get_text().strip() if date_el else ""
                            pub_dt = parse_article_date(date_text)

                            if link in seen_links:
                                continue
                            if not is_within_48_hours(pub_dt):
                                continue

                            seen_links.add(link)
                            scraped_items.append({
                                "title": title,
                                "link": link,
                                "press": press,
                                "description": desc,
                                "keyword": kw,
                                "pub_date": format_pub_date(pub_dt),
                            })
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

def render_article_detail_cards(items):
    """선택 안건 심층 분석 카드 렌더링"""
    for target_item in items:
        st.markdown(f"""
            <div class="dashboard-card">
                <span style="background:#0A2540; color:#FFFFFF; padding:4px 10px; border-radius:4px; font-size:0.8rem; font-weight:600;">
                    {target_item['대분류']} / {target_item['소분류']}
                </span>
                <h4 style="margin: 0.8rem 0 0.3rem 0; font-size:1.3rem;">{target_item['기사제목']}</h4>
                <p style="color:#64748B; font-size:0.85rem; margin-bottom:1rem;">출처 본청: {target_item['언론사']} | 인덱싱 키워드: {target_item['수집키워드']} | 발행: {target_item.get('발행일시', '-')}</p>
                <div class="ai-summary-box">
                    <strong>📄 AI 에이전트 요약 개조식 보고 서식</strong><br>
                    {target_item['5줄요약']}
                </div>
            </div>
        """, unsafe_allow_html=True)

# ----------------------------------------------------
# 메인 비즈니스 로직 제어부
# ----------------------------------------------------
openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None

# 이슈 스파이크 알림 감지 및 고급형 아웃라인 표출
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

# 행정 명령 컨트롤 타워 버튼 배치
col_btn1, col_btn2 = st.columns([4.2, 1])
with col_btn1:
    execute = st.button("🏛️ 범정부 지정 정책 키워드 기반 빅데이터 동향 수집 및 에이전트 분석 가동", use_container_width=True)
with col_btn2:
    if st.button("🧹 전산 데이터 초기화", use_container_width=True):
        st.session_state.scraped_data = []
        st.session_state.all_history = []
        st.session_state.library = []
        st.rerun()

if execute:
    status_bar = st.empty()
    status_bar.info("⏳ 고성능 포털 동적 수집 엔진을 가동합니다. 최근 48시간 이내 미디어 인덱스를 동기화 중입니다...")
    
    existing_urls = {item["URL"] for item in st.session_state.all_history}
    raw_news = fetch_mass_news_stable(target_keywords, naver_client_id, naver_client_secret, existing_urls=existing_urls)
    
    if not raw_news:
        if existing_urls:
            refresh_scraped_data_from_history()
            status_bar.warning("ℹ️ 신규 기사가 없습니다. 기존 히스토리에서 48시간 이내 데이터를 유지합니다.")
        else:
            status_bar.error("❌ 데이터 연동 실패. 네트워크 응답 처리를 다시 점검하십시오.")
    else:
        skipped_count = len(existing_urls)
        status_bar.info(
            f"🔎 최근 48시간 이내 신규 {len(raw_news)}건 식별 "
            f"(히스토리 중복 {skipped_count}건 제외). AI 행정 요약 모델 구동 중..."
        )
        
        new_analyzed = []
        p_bar = st.progress(0)
        
        for index, item in enumerate(raw_news):
            full_body = crawl_article_body_stable(item['link'])
            if "데이터 추출 제한" in full_body:
                full_body = item['description']
                
            large_cat, small_cat, summary_text = classify_and_summarize(item['title'], full_body, openai_client)
            
            raw_filename = f"({large_cat})({small_cat}){item['title']}_{item['press']}"
            safe_hwp_name = clean_filename(raw_filename)
            
            new_analyzed.append({
                "대분류": large_cat,
                "소분류": small_cat,
                "기사제목": item['title'],
                "언론사": item['press'],
                "URL": item['link'],
                "본문": full_body,
                "파일명": safe_hwp_name,
                "5줄요약": summary_text,
                "수집키워드": item['keyword'],
                "발행일시": item.get('pub_date', ''),
                "수집일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
            p_bar.progress((index + 1) / len(raw_news))

        st.session_state.all_history.extend(new_analyzed)
        refresh_scraped_data_from_history()
        status_bar.success(
            f"🏛️ 증분 수집 완료. 신규 {len(new_analyzed)}건 추가 "
            f"(전체 히스토리 {len(st.session_state.all_history)}건, "
            f"대시보드 48h {len(st.session_state.scraped_data)}건)."
        )
        st.rerun()

# ----------------------------------------------------
# 📊 출력단 - 탭 기반 BI 대시보드 레이아웃
# ----------------------------------------------------
tab_dashboard, tab_history, tab_library = st.tabs([
    "📊 대시보드",
    "📚 전체 히스토리",
    "🔖 라이브러리 (북마크)",
])

# ── Tab 1: 대시보드 ──
with tab_dashboard:
    if st.session_state.scraped_data:
        df_display = pd.DataFrame(st.session_state.scraped_data)
        library_urls = {item["URL"] for item in st.session_state.library}

        # Section A: 종합 브리핑 영역
        st.write("---")
        st.markdown("### 📊 빅데이터 기반 탄소중립 정책동향 종합 브리핑")
        with st.expander("📝 금주 탄소중립 정책동향 분석 리포트 확인", expanded=True):
            trend_report = generate_weekly_trend_summary(st.session_state.scraped_data, openai_client)
            st.markdown(f"<div class='ai-summary-box'>{trend_report}</div>", unsafe_allow_html=True)
            
        # Section B: 종합 관제 센터 테두리 테이블
        st.write("---")
        st.markdown("### 📋 실시간 수집 보도자료 종합 관제 센터")
        st.caption("최근 48시간 이내 발행 기사만 표시됩니다. 북마크 체크 시 라이브러리 탭에 자동 저장됩니다.")
        
        df_display.insert(0, "선택", False)
        df_display.insert(1, "북마크", df_display["URL"].apply(lambda u: u in library_urls))
        
        edited_df = st.data_editor(
            df_display[["선택", "북마크", "대분류", "소분류", "기사제목", "언론사", "발행일시", "수집키워드", "URL"]],
            hide_index=True,
            use_container_width=True,
            disabled=["대분류", "소분류", "기사제목", "언론사", "발행일시", "수집키워드", "URL"],
            column_config={
                "선택": st.column_config.CheckboxColumn("선택", default=False),
                "북마크": st.column_config.CheckboxColumn("북마크", default=False),
            },
            key="dashboard_editor",
        )

        sync_library_from_bookmarks(st.session_state.scraped_data, edited_df)
        
        url_to_idx = {item["URL"]: idx for idx, item in enumerate(st.session_state.scraped_data)}
        selected_rows = [
            url_to_idx[row["URL"]]
            for _, row in edited_df.iterrows()
            if row["선택"] and row["URL"] in url_to_idx
        ]
        
        # Section C: 심층 요약 분석 피드
        if selected_rows:
            st.markdown("### 🔍 선택 안건별 심층 AI 행정 분석 피드")
            selected_items = [st.session_state.scraped_data[idx] for idx in selected_rows]
            render_article_detail_cards(selected_items)
                
            # Section D: 공문서 출력 다운로더
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

# ── Tab 2: 전체 히스토리 ──
with tab_history:
    st.markdown("### 📚 세션 전체 수집 히스토리")
    st.caption(f"세션 동안 누적 수집된 전체 기사 {len(st.session_state.all_history)}건")

    if st.session_state.all_history:
        df_history = pd.DataFrame(st.session_state.all_history)
        display_cols = ["대분류", "소분류", "기사제목", "언론사", "발행일시", "수집일시", "수집키워드", "URL"]
        available_cols = [c for c in display_cols if c in df_history.columns]
        st.dataframe(
            df_history[available_cols],
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("아직 수집된 히스토리가 없습니다. 상단 수집 버튼을 실행해 주세요.")

# ── Tab 3: 라이브러리 (북마크) ──
with tab_library:
    st.markdown("### 🔖 라이브러리 — 북마크 저장 기사")
    st.caption(f"북마크 저장 {len(st.session_state.library)}건")

    if st.session_state.library:
        df_library = pd.DataFrame(st.session_state.library)
        display_cols = ["대분류", "소분류", "기사제목", "언론사", "발행일시", "수집키워드", "URL"]
        available_cols = [c for c in display_cols if c in df_library.columns]
        st.dataframe(
            df_library[available_cols],
            hide_index=True,
            use_container_width=True,
        )

        st.write("---")
        st.markdown("### 🔍 북마크 안건 심층 AI 행정 분석")
        render_article_detail_cards(st.session_state.library)

        st.write("---")
        st.markdown("### 🖨️ 북마크 안건 HWP 일괄 다운로드")
        zip_library_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_library_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for item_data in st.session_state.library:
                hwp_file_stream = generate_hwp_text_file(item_data)
                zip_file.writestr(item_data['파일명'], hwp_file_stream.getvalue())

        st.download_button(
            label="📥 북마크 전체 표준 공문서(HWP) 파일셋 다운로드 (.zip)",
            data=zip_library_buffer.getvalue(),
            file_name=f"기획예산처_탄소중립_북마크_{datetime.now().strftime('%Y%m%d')}.zip",
            mime="application/zip",
            use_container_width=True,
        )
    else:
        st.info("북마크된 기사가 없습니다. 대시보드 테이블의 '북마크' 열에서 기사를 저장해 주세요.")
