import os
import re
import io
import zipfile
import streamlit as st
import pandas as pd
from datetime import datetime

# 1. 페이지 레이아웃 및 정부 표준 테마 설정
st.set_page_config(page_title="탄소중립정책과 기사 분석 에이전트", layout="wide", initial_sidebar_state="expanded")

# 라이브러리 임포트 및 예외 처리
try:
    import requests
    from bs4 import BeautifulSoup
    from openai import OpenAI
except ImportError:
    st.error("⚠️ 필수 라이브러리가 부족합니다. GitHub의 requirements.txt 환경을 확인해주세요.")

# 기획예산처 공식 가이드라인 기반 UI/UX 스타일 주입
st.markdown("""
    <style>
    /* 전체 공적 배경 및 서체 정돈 */
    .stApp { background-color: #F8FAFC; }
    h1, h2, h3, h4 { color: #0A2540 !important; font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; }
    
    /* 3. 중앙 상단 행정 배너 및 타이틀 레이아웃 (아이콘 배제, 정부 상징 로고 전용 공간) */
    .gov-banner-container {
        background-color: #FFFFFF;
        padding: 1.6rem 2.2rem;
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
    .gov-text-area { flex: 1 1 auto; }
    .gov-title { font-size: 2.1rem; font-weight: 700; color: #0A2540; letter-spacing: -0.06rem; margin: 0; }
    .gov-subtitle { font-size: 0.95rem; color: #64748B; margin-top: 0.4rem; font-weight: 400; line-height: 1.5; }
    
    /* 1. 키워드 선택창 및 멀티셀렉트 색상 통일 (#0A2540 네이비) */
    span[data-baseweb="tag"] {
        background-color: #0A2540 !important;
        color: #FFFFFF !important;
        border-radius: 3px !important;
    }
    span[data-baseweb="tag"] button {
        color: #FFFFFF !important;
    }
    div[data-baseweb="select"] {
        border-color: #CBD5E1 !important;
    }
    
    /* 정부 표준 단추(버튼) 스타일 규격화 */
    .stButton>button {
        background-color: #0A2540 !important;
        color: #FFFFFF !important;
        border-radius: 3px !important;
        border: 1px solid #0A2540 !important;
        font-weight: 600 !important;
        padding: 0.6rem 1.2rem !important;
    }
    .stButton>button:hover {
        background-color: #1E3A8A !important;
        border-color: #1E3A8A !important;
    }
    
    /* 대시보드 카드 및 리포트 스타일 */
    .report-card {
        background-color: #FFFFFF;
        padding: 1.5rem;
        border-radius: 4px;
        border: 1px solid #E2E8F0;
        border-left: 5px solid #0A2540;
        margin-bottom: 1.2rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    }
    .summary-box {
        background-color: #FFFFFF;
        border: 1px solid #0A2540;
        padding: 1.5rem;
        border-radius: 4px;
        font-family: 'Malgun Gothic', sans-serif;
        line-height: 1.7;
        color: #1E293B;
    }
    
    /* 이슈 스파이크 경보 스타일 */
    .spike-alert {
        background-color: #FEF2F2;
        border: 1px solid #FCA5A5;
        border-left: 5px solid #DC2626;
        padding: 1.2rem;
        border-radius: 4px;
        margin-bottom: 1.5rem;
        color: #991B1B;
    }
    </style>
""", unsafe_allow_html=True)

# 2. 기획예산처 로고 주입 및 예외 처리 아키텍처
logo_html_content = ""
if os.path.exists("logo.png"):
    import base64
    with open("logo.png", "rb") as f:
        encoded_logo = base64.b64encode(f.read()).decode()
    logo_html_content = f'<div class="gov-logo-area"><img src="data:image/png;base64,{encoded_logo}" style="height: 55px; width: auto; object-fit: contain;"></div>'
else:
    logo_html_content = '<div class="gov-logo-area" style="font-weight:bold; color:#0A2540; font-size:1.4rem; letter-spacing:-0.1rem;">🏛️ 기획예산처</div>'

# 3. 중앙 상단 타이틀 명칭 변경 적용
st.markdown(f"""
    <div class="gov-banner-container">
        {logo_html_content}
        <div class="gov-text-area">
            <div class="gov-title">탄소중립정책과 기사 분석 에이전트</div>
            <div class="gov-subtitle">본 시스템은 기획예산처 탄소중립정책과의 업무 효율화를 위해 실시간 언론 보도 자료를 다량 수집, 검증하고 빅데이터 기반의 동향 분석 보고서를 자동 생성하는 공정형 행정 인텔리전스입니다.</div>
        </div>
    </div>
""", unsafe_allow_html=True)

# 세션 데이터 보존 스토리지
if "scraped_data" not in st.session_state:
    st.session_state.scraped_data = []

LARGE_CATEGORIES = ["배출권", "탄소시장", "탄소세", "ESG", "전기차", "탄소중립", "CBAM", "IAA", "기후변화"]
SMALL_CATEGORIES = ["자발적 탄소시장", "국제감축", "탄소제거", "기후공시", "전환금융", "녹색금융", "재생에너지", "기후테크", "온실가스"]

# 사이드바 환경 설정
st.sidebar.markdown("### 🔒 행정 자격 인증")
naver_client_id = st.sidebar.text_input("네이버 Client ID", value=st.secrets.get("NAVER_CLIENT_ID", ""), type="password")
naver_client_secret = st.sidebar.text_input("네이버 Client Secret", value=st.secrets.get("NAVER_CLIENT_SECRET", ""), type="password")
openai_api_key = st.sidebar.text_input("OpenAI API Key", value=st.secrets.get("OPENAI_API_KEY", ""), type="password")

st.sidebar.write("---")
st.sidebar.markdown("### 🎯 범정부 모니터링 키워드")

# 복구된 25개 전체 정책 키워드 풀
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

# 4. 타임아웃 및 누락을 방지하는 안정적 뉴스 다량 수집 엔진
def fetch_mass_news_stable(keywords, client_id, client_secret):
    scraped_items = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    for kw in keywords:
        # 네이버 OpenAPI 연동 우선 시도 (실패 시 일반 크롤링 백업 백코딩)
        if client_id and client_secret:
            # 다량 수집을 위해 display 개수를 최대치(50건)로 상향 조정
            url = f"https://openapi.naver.com/v1/search/news.json?query={kw}&display=50&sort=sim"
            headers_api = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret}
            try:
                res = requests.get(url, headers=headers_api, timeout=5)
                if res.status_code == 200:
                    items = res.json().get('items', [])
                    for item in items:
                        title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", '"')
                        link = item['link']
                        press = item.get('originallink', '언론사').split('//')[-1].split('/')[0]
                        desc = item['description'].replace("<b>", "").replace("</b>", "")
                        
                        if not any(x['URL'] == link for x in scraped_items):
                            scraped_items.append({"title": title, "link": link, "press": press, "description": desc, "keyword": kw})
                    continue
            except Exception:
                pass
        
        # API 미입력 또는 타임아웃 발생 시 크롤링으로 다량 우회 수집
        try:
            for page in range(2): # 다량 수집을 위해 2개 페이지 파싱
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
                            
                            if not any(x['URL'] == link for x in scraped_items):
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
    # 의존성 에러 완전 방어 규칙 바인딩
    if not openai_client:
        return "탄소중립", "일반", "- OpenAI API Key를 입력하시면 정교한 보고서용 3줄 개조식 요약이 생성됩니다."
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "너는 기획예산처의 탄소중립정책과 분석관이야. 기사 제목과 본문을 분석해 대분류군, 소분류군을 한 단어씩 선택하고 기사 내용을 공문서 지침에 맞춰 3줄의 개조식(- 문장형태)으로 요약해줘.\n출력 형식:\n대분류: 단어\n소분류: 단어\n요약:\n- 요약내용1\n- 요약내용2\n- 요약내용3"},
                {"role": "user", "content": f"제목: {title}\n본문: {content[:800]}"}
            ],
            temperature=0.2
        )
        res_text = response.choices[0].message.content.strip()
        large_cat, small_cat, summary = "탄소중립", "일반", "- 요약문 도출 실패"
        
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
        return "탄소중립", "일반", "- 분석 엔진 네트워크 일시 지연 오류"

# 6. 공문서 표준 한글(HWP) 서식 텍스트 파일 생성기
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

# 7. 주간/월간 탄소중립 동향 보고서 (빅데이터 마스터 요약 모듈)
def generate_weekly_trend_summary(data_list, openai_client):
    if not openai_client:
        return "💡 OpenAI API Key가 제공되지 않아 빅데이터 동향 종합 브리핑을 추출할 수 없습니다."
    
    context = ""
    for idx, d in enumerate(data_list[:15]):
        context += f"[{idx+1}] {d['기사제목']} -> {d['5줄요약']}\n"
        
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "너는 기획예산처의 경제동향 수석 심의관이야. 제공된 다량의 탄소중립 뉴스 요약본 전체를 파악하여, 기획예산처 지휘부에 보고할 금주의 [1. 종합 정책 평가], [2. 주요 리스크 관리 안건], [3. 부처별 예산·정책 대응 제언] 동향 보고서를 개조식(◼︎, ❍, - 기호 사용)으로 정갈하게 작성해줘."},
                {"role": "user", "content": f"수집된 빅데이터 동향 정보셋:\n{context}"}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"동향 리포트 구성 중 오류가 발생했습니다: {str(e)}"

# --- 제어 인터페이스 설계 및 구동 ---

# 8. 정부 맞춤형 키워드 알림 및 이슈 스파이크 감지 엔진
if st.session_state.scraped_data:
    df_spike = pd.DataFrame(st.session_state.scraped_data)
    kw_counts = df_spike['수집키워드'].value_counts()
    for kw, count in kw_counts.items():
        if count >= 6: # 특정 핵심 어젠다에 6건 이상의 보도가 집중될 때 경보 표출
            st.markdown(f"""
                <div class="spike-alert">
                    <strong>🚨 [행정 주의보] 탄소중립정책과 이슈 스파이크 감지</strong><br>
                    현재 <strong>'{kw}'</strong> 관련 정책 보도 자료가 단시간 내에 <strong>{count}건 이상 급증</strong>했습니다. 
                    기획예산처 예산 심사 및 대외 리스크 관리 부서는 해당 어젠다의 보도 추이를 면밀히 모니터링하시기 바랍니다.
                </div>
            """, unsafe_allow_html=True)

# 행정 명령 단추 컨트롤러
col_btn1, col_btn2 = st.columns([4, 1])
with col_btn1:
    execute = st.button("🏛️ 기획예산처 지정 정책 키워드 기반 다량 뉴스 수집 및 에이전트 분석 가동", use_container_width=True)
with col_btn2:
    if st.button("🧹 데이터 초기화", use_container_width=True):
        st.session_state.scraped_data = []
        st.rerun()

if execute:
    # 에러 방어용 객체 할당 초기화
    openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None
    
    status_bar = st.empty()
    status_bar.info("⏳ 포털 다량 수집 엔진 가동 중... 지정하신 모든 정책 키워드의 뉴스를 긁어옵니다.")
    
    # 4. 다량 수집 엔진 구동
    raw_news = fetch_mass_news_stable(target_keywords, naver_client_id, naver_client_secret)
    
    if not raw_news:
        status_bar.error("❌ 뉴스 수집에 실패했습니다. 키 값을 확인하거나 잠시 후 다시 시도해주세요.")
    else:
        status_bar.info(f"🔎 총 {len(raw_news)}건의 정책 보도 소스 확보 완료. 개별 안건 심층 분석 및 행정 요약 수립 중...")
        
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
        status_bar.success(f"🏛️ 분석 완료. 총 {len(analyzed_pool)}건의 대량 기사 데이터가 안전하게 바인딩되었습니다.")
        st.rerun()

# 5. 수집 결과 및 한눈에 보는 요약정리 화면 표출
if st.session_state.scraped_data:
    df_display = pd.DataFrame(st.session_state.scraped_data)
    
    # 7. 주간/월간 탄소중립 동향 보고서 (빅데이터 종합 요약)
    st.write("---")
    st.markdown("### 📊 빅데이터 기반 탄소중립 정책동향 종합 브리핑")
    with st.expander("📝 금주 탄소중립 정책동향 종합 리포트 (클릭하여 열기)", expanded=True):
        openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None
        trend_report = generate_weekly_trend_summary(st.session_state.scraped_data, openai_client)
        st.markdown(f"<div class='summary-box'>{trend_report}</div>", unsafe_allow_html=True)
        
    st.write("---")
    st.markdown("### 📋 실시간 수집 보도자료 종합 관제 테이블")
    
    df_display.insert(0, "선택", False)
    edited_df = st.data_editor(
        df_display[["선택", "대분류", "소분류", "기사제목", "언론사", "수집키워드"]],
        hide_index=True,
        use_container_width=True,
        disabled=["대분류", "소분류", "기사제목", "언론사", "수집키워드"]
    )
    
    selected_rows = edited_df[edited_df["선택"] == True].index.tolist()
    
    # 5. 선택 안건 한눈에 보기 상세 요약 스크린
    if selected_rows:
        st.markdown("### 🔍 선택 안건별 심층 AI 행정 요약본")
        for idx in selected_rows:
            target_item = st.session_state.scraped_data[idx]
            st.markdown(f"""
                <div class="report-card">
                    <h4 style="margin:0;">📌 [{target_item['대분류']} / {target_item['소분류']}] {target_item['기사제목']}</h4>
                    <span style="color:#64748B; font-size:0.85rem;">출처: {target_item['언론사']} | 연관 키워드: {target_item['수집키워드']}</span>
                    <div style="margin-top:0.8rem; background-color:#F8FAFC; padding:1rem; border-radius:4px; border:1px solid #E2E8F0;">
                        <strong>[본문 핵심 3줄 요약]</strong><br>
                        {target_item['5줄요약']}
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
        # 6. 공문서 표준 한글 파일(.hwp) 내보내기 기능
        st.write("---")
        st.markdown("### 🖨️ 정부 표준 결재용 한글(HWP) 문서 출력 컨트롤러")
        col_hwp1, col_hwp2 = st.columns(2)
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
            st.caption("💡 상단 관제 테이블에서 요약 출력을 원하는 보도자료의 좌측 체크박스를 선택하면 정식 한글(HWP) 서식으로 인덱싱된 보고서가 다운로드 파일셋에 추가됩니다.")
else:
    st.info("🏛️ 시스템 초기화 상태입니다. [다량 뉴스 수집 및 에이전트 분석 가동] 단추를 누르면 공정 분석 체계가 수립됩니다.")
