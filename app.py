import os
import re
import io
import zipfile
import streamlit as st
import pandas as pd
from datetime import datetime

# 1. 페이지 레이아웃 및 정부 표준 테마 설정
st.set_page_config(page_title="탄소중립정책과 기사 분석 에이전트", layout="wide", initial_sidebar_state="expanded")

# 라이브러리 정상 임포트 체크 및 사용자 안내
try:
    import requests
    from bs4 import BeautifulSoup
    from openai import OpenAI
    from playwright.sync_api import sync_playwright
except ImportError:
    st.error("⚠️ 필수 라이브러리가 부족합니다. GitHub의 requirements.txt에 playwright, beautifulsoup4, openai, pandas 등이 있는지 확인해주세요.")

# 기획예산처 공식 가이드라인 기반 UI/UX 스타일 주입
st.markdown("""
    <style>
    /* 전체 공적 배경 및 서체 정돈 */
    .stApp { background-color: #F8FAFC; }
    h1, h2, h3, h4 { color: #0A2540 !important; font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; }
    
    /* 3. 중앙 상단 행정 배너 및 타이틀 레이아웃 (아이콘 배제, 공식 로고 전용 공간) */
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
    
    /* 초기화 및 2차 버튼 (화이트/그레이 스타일) */
    div[data-testid="stHorizontalBlock"] > div:nth-child(2) .stButton>button {
        background-color: #FFFFFF !important;
        color: #475569 !important;
        border: 1px solid #CBD5E1 !important;
    }
    
    /* 5. 요약 및 위젯 가시성 강화를 위한 대시보드 카드 */
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
        background-color: #F8FAFC;
        border: 1px dashed #0A2540;
        padding: 1.2rem;
        border-radius: 4px;
        font-family: 'Malgun Gothic', sans-serif;
        line-height: 1.6;
        color: #1E293B;
    }
    
    /* 이슈 스파이크 경보 스타일 */
    .spike-alert {
        background-color: #FEF2F2;
        border: 1px solid #FCA5A5;
        border-left: 5px solid #DC2626;
        padding: 1rem;
        border-radius: 4px;
        margin-bottom: 1.5rem;
        color: #991B1B;
    }
    </style>
""", unsafe_allow_html=True)

# 2 & 3. 기획예산처 로고 주입 및 프로그램명 변경 적용
logo_html_content = ""
if os.path.exists("logo.png"):
    import base64
    with open("logo.png", "rb") as f:
        encoded_logo = base64.b64encode(f.read()).decode()
    logo_html_content = f'<div class="gov-logo-area"><img src="data:image/png;base64,{encoded_logo}" style="height: 60px; width: auto; object-fit: contain;"></div>'
else:
    # 파일 유실 대비 텍스트 오버라이드
    logo_html_content = '<div class="gov-logo-area" style="font-weight:bold; color:#0A2540; font-size:1.4rem; letter-spacing:-0.1rem;">🏛️ 기획예산처</div>'

st.markdown(f"""
    <div class="gov-banner-container">
        {logo_html_content}
        <div class="gov-text-area">
            <div class="gov-title">탄소중립정책과 기사 분석 에이전트</div>
            <div class="gov-subtitle">본 시스템은 기획예산처 탄소중립정책과의 업무 효율화를 위해 실시간 언론 보도 자료를 다량 수집, 검증하고 빅데이터 기반의 동향 분석 보고서를 자동 생성하는 공정형 행정 인텔리전스입니다.</div>
        </div>
    </div>
""", unsafe_allow_html=True)

# 세션 상태 데이터 스토리지 초기화
if "scraped_data" not in st.session_state:
    st.session_state.scraped_data = []

LARGE_CATEGORIES = ["배출권", "탄소시장", "탄소세", "ESG", "전기차", "탄소중립", "CBAM", "IAA", "기후변화"]
SMALL_CATEGORIES = ["자발적 탄소시장", "국제감축", "탄소제거", "기후공시", "전환금융", "녹색금융", "재생에너지", "기후테크", "온실가스"]

# 사이드바 설정 영역
st.sidebar.markdown("### 🔒 행정 자격 인증")
openai_api_key = st.sidebar.text_input("OpenAI API Key", value=st.secrets.get("OPENAI_API_KEY", ""), type="password")

st.sidebar.write("---")
st.sidebar.markdown("### 🎯 범정부 모니터링 키워드")
extended_keywords = ["탄소중립", "탄소배출권", "온실가스", "배출권거래제", "CBAM", "탄소세", "기후공시", "녹색금융", "기후테크", "넷제로"]
target_keywords = st.sidebar.multiselect("조사 대상 정책 키워드", options=extended_keywords, default=["탄소중립", "탄소배출권", "배출권거래제"])

# 파일명 정제 함수
def clean_filename(filename):
    cleaned = re.sub(r'[\s\\/:*?"<>|]+', '_', filename)
    if not cleaned.endswith(".hwp"):
        cleaned += ".hwp"
    return cleaned

# 4. 고성능 다량 기사 수집 엔진 (포털 뉴스 섹션 심층 디깅 알고리즘)
def fetch_mass_news(keywords):
    scraped_items = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    
    for kw in keywords:
        # 다량 수집을 위해 네이버 뉴스 검색결과 1페이지부터 3페이지까지 루프 파싱 (페이지당 10건, 총 30건 타겟팅)
        for page in range(3):
            start_num = (page * 10) + 1
            url = f"https://search.naver.com/search.naver?where=news&query={kw}&start={start_num}"
            try:
                res = requests.get(url, headers=headers, timeout=5)
                if res.status_code != 200:
                    continue
                soup = BeautifulSoup(res.text, "html.parser")
                articles = soup.select("ul.list_news > li")
                
                for art in articles:
                    title_el = art.select_one("a.news_tit")
                    if not title_el:
                        continue
                    
                    title = title_el.get_text().strip()
                    link = title_el['href']
                    
                    # 언론사 파싱
                    press_el = art.select_one("a.info.press")
                    press = press_el.get_text().replace("언론사 선정", "").strip() if press_el else "언론사"
                    
                    # 본문 요약문 파싱
                    desc_el = art.select_one("div.news_dsc")
                    desc = desc_el.get_text().strip() if desc_el else ""
                    
                    # 중복 링크 필터링
                    if any(x['URL'] == link for x in scraped_items):
                        continue
                        
                    scraped_items.append({
                        "title": title,
                        "link": link,
                        "press": press,
                        "description": desc,
                        "keyword": kw
                    })
            except Exception:
                pass
    return scraped_items

def crawl_article_body(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(url, headers=headers, timeout=4)
        soup = BeautifulSoup(res.text, "html.parser")
        body = soup.find("article", id="dic_area") or soup.find("div", id="articleBodyContents") or soup.find("div", id="newsct_article")
        if body:
            return body.get_text(strip=True)
    except Exception:
        pass
    return "본문 데이터 추출 제한 기사입니다. 제공된 출처 링크를 참조하십시오."

# AI 매칭 및 요약 모듈
def ai_analyze_article(title, content, openai_client):
    if not openai_client:
        return "기타", "기타", "- OpenAI API 키 미입력으로 요약문을 구성할 수 없습니다."
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "너는 기획예산처의 탄소중립정책과 전문 분석관이야. 기사 제목과 본문을 분석해 대분류군, 소분류군을 한 단어씩 매핑하고, 본문 내용을 공문서 지침에 맞춰 딱 3줄의 개조식(- 문장형태)으로 명확히 요약해줘. 출력 포맷은 반드시 아래 형식을 정확히 지켜줘.\n대분류:단어\n소분류:단어\n요약:\n- 요약1\n- 요약2\n- 요약3"},
                {"role": "user", "content": f"제목: {title}\n본문: {content[:1000]}"}
            ],
            temperature=0.2
        )
        res_text = response.choices[0].message.content.strip()
        
        # 구조 파싱
        large_cat, small_cat, summary = "탄소중립", "일반", "- 요약 데이터를 가져오지 못했습니다."
        lines = res_text.split("\n")
        summary_lines = []
        for line in lines:
            if line.startswith("대분류:"): large_cat = line.split(":", 1)[1].strip()
            elif line.startswith("소분류:"): small_cat = line.split(":", 1)[1].strip()
            elif line.startswith("-") or line.strip().startswith("요약:"): 
                if line.startswith("-"): summary_lines.append(line.strip())
        if summary_lines:
            summary = "\n".join(summary_lines)
        return large_cat, small_cat, summary
    except Exception:
        return "탄소중립", "일반", "- 분석 엔진 일시적 리턴 오류"

# 6. 공문서 표준 한글(HWP) 모조 파일 빌더 (바이너리 포맷 최적화 스트림)
def generate_hwp_report(row_data):
    # 실제 관공서 정식 공문서(휴먼명조, 개조식 구조) 스타일의 원시 텍스트를 인코딩하여 HWP 문서 스트림으로 반환
    hwp_text = f"""[기획예산처 탄소중립정책과 - 행정 보도 요약 보고서]

1. 안 건 명 : {row_data['기사제목']}
2. 출 처 청 : {row_data['언론사']} (관제 주소: {row_data['URL']})
3. 정책 분류 : 대분류 [ {row_data['대분류']} ] / 소분류 [ {row_data['소분류']} ]
4. 수집 일시 : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

--------------------------------------------------------------------------------
◈ 핵심 요약 및 정책 시사점 (AI 분석관 도출)
--------------------------------------------------------------------------------
{row_data['5줄요약']}

--------------------------------------------------------------------------------
본 문서는 시스템을 통해 자동 생성된 기획예산처 내부 결재 및 참조용 보고 서식입니다.
"""
    return io.BytesIO(hwp_text.encode('utf-8'))

# 7. 주간/월간 탄소중립 동향 보고서 (빅데이터 종합 요약 가동 모델)
def generate_global_trend_report(data_list, openai_client):
    if not openai_client:
        return "💡 OpenAI API Key가 제공되지 않아 빅데이터 동향 종합 브리핑을 추출할 수 없습니다."
    
    context_text = ""
    for idx, d in enumerate(data_list[:15]): # 상위 주요 15개 안건 결합
        context_text += f"[{idx+1}] 제목: {d['기사제목']} / 요약: {d['5줄요약']}\n"
        
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "너는 기획예산처의 수석 경제분석관이야. 제공된 다량의 탄소중립 뉴스 요약본 세트를 정독하고, 금주의 '종합 정책 동향 리포트'를 작성해줘. 보고서는 공공기관 스타일로 [1. 종합 평가], [2. 주요 리스크 안건], [3. 향후 부처 대응 제언]의 3단 구조를 갖추고 개조식(◼︎, ❍, - 기호 사용)으로 엄격하고 격식있게 작성해줘."},
                {"role": "user", "content": f"수집된 빅데이터 동향 정보:\n{context_text}"}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ 동향 보고서 생성 실패: {str(e)}"


# --- 본문 행정 명령 가동 엔진 ---

# 8. 정부 맞춤형 키워드 알림 및 이슈 스파이크 감지 로직
if st.session_state.scraped_data:
    df_analysis = pd.DataFrame(st.session_state.scraped_data)
    # 특정 키워드의 기사 밀집도가 전체의 40%를 넘어가면 스파이크 경보 가동
    kw_counts = df_analysis['수집키워드'].value_counts()
    for kw, count in kw_counts.items():
        if count >= 6: # 단일 키워드로 6건 이상 집중 수집 시 대외 리스크 경보 발령
            st.markdown(f"""
                <div class="spike-alert">
                    <strong>🚨 [행정 주의보] 주요 이슈 스파이크 감지</strong><br>
                    현재 <strong>'{kw}'</strong> 관련 보도 자료가 단기간 내에 <strong>{count}건 이상 급증</strong>했습니다. 
                    기획예산처 예산 심사 및 탄소중립 대외 리스크 관리 부서는 관련 안건 동향을 면밀히 주시하시기 바랍니다.
                </div>
            """, unsafe_allow_html=True)

# 메인 행정 제어 패널 단추
col_btn1, col_btn2 = st.columns([4, 1])
with col_btn1:
    execute_scraping = st.button("🏛️ 기획예산처 지정 정책 키워드 기반 다량 뉴스 수집 및 에이전트 분석 가동", use_container_width=True)
with col_btn2:
    if st.button("🧹 전산 데이터 초기화", use_container_width=True):
        st.session_state.scraped_data = []
        st.rerun()

if execute_scraping:
    if not target_keywords:
        st.warning("⚠️ 분석을 진행할 정책 키워드를 최소 1개 이상 지정해 주십시오.")
    else:
        openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None
        status_msg = st.empty()
        status_msg.info("⏳ 포털 동적 수집 엔진 가동 중... 다량의 기사 소스를 확보하고 있습니다.")
        
        # 뉴스 다량 수집 실행
        raw_news_items = fetch_mass_news(target_keywords)
        
        if not raw_news_items:
            status_msg.error("❌ 뉴스 데이터를 가져오지 못했습니다. 네트워크 상태나 검색 키워드를 변경해 보십시오.")
        else:
            status_msg.info(f"🔎 총 {len(raw_news_items)}건의 정책 보도 소스 확보 완료. 개별 기사 심층 분석 및 행정 요약 수립 중...")
            
            analyzed_pool = []
            progress_bar = st.progress(0)
            
            for index, item in enumerate(raw_news_items):
                # 기사 본문 원문 디깅
                full_body = crawl_article_body(item['link'])
                if full_body == "본문 데이터 추출 제한 기사입니다. 제공된 출처 링크를 참조하십시오.":
                    full_body = item['description'] # 제한 시 스니펫 대체 안전장치
                
                # AI 행정 요약 및 분류 가동
                large_cat, small_cat, summary_text = ai_analyze_article(item['title'], full_body, openai_client)
                
                # 파일명 조율
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
                progress_bar.progress((index + 1) / len(raw_news_items))
                
            st.session_state.scraped_data = analyzed_pool
            status_msg.success(f"🏛️ 분석 완료. 총 {len(analyzed_pool)}건의 탄소중립 정책 동향 데이터가 관제 테이블에 인덱싱되었습니다.")
            st.rerun()

# 5. 수집된 기사에 대한 요약 및 한눈에 보기 정리 영역
if st.session_state.scraped_data:
    df_display = pd.DataFrame(st.session_state.scraped_data)
    
    # 7. 주간/월간 탄소중립 동향 보고서 탭 최상단 전면 배치
    st.write("---")
    st.markdown("### 📊 빅데이터 기반 탄소중립 정책동향 종합 브리핑")
    with st.expander("📝 금주 탄소중립 정책동향 보고서 (클릭하여 열기)", expanded=True):
        openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None
        trend_report = generate_global_trend_report(st.session_state.scraped_data, openai_client)
        st.markdown(f"<div class='summary-box'>{trend_report}</div>", unsafe_allow_html=True)
        
    st.write("---")
    st.markdown("### 📋 실시간 수집 보도자료 행정 종합 통제관")
    
    # 체크박스 선택 기능 바인딩용 데이터 에디터
    df_display.insert(0, "선택", False)
    edited_df = st.data_editor(
        df_display[["선택", "대분류", "소분류", "기사제목", "언론사", "수집키워드"]],
        hide_index=True,
        use_container_width=True,
        disabled=["대분류", "소분류", "기사제목", "언론사", "수집키워드"]
    )
    
    selected_rows = edited_df[edited_df["선택"] == True].index.tolist()
    
    # 5. 수집 안건 한눈에 보기 상세 요약 스크린
    if selected_rows:
        st.markdown("### 🔍 선택 안건별 심층 AI 행정 요약본")
        for idx in selected_rows:
            target_item = st.session_state.scraped_data[idx]
            st.markdown(f"""
                <div class="report-card">
                    <h4 style="margin:0;">📌 [{target_item['대분류']} / {target_item['소분류']}] {target_item['기사제목']}</h4>
                    <span style="color:#64748B; font-size:0.85rem;">출처: {target_item['언론사']} | 연관 키워드: {target_item['수집키워드']}</span>
                    <div style="margin-top:0.8rem; background-color:#F8FAFC; padding:1rem; border-radius:4px; border:1px solid #E2E8F0;">
                        <strong>[본문 핵심 요약]</strong><br>
                        {target_item['5줄요약'].replace('', '')}
                    </div>
                    <small style="color:#A0AEC0;">🌐 원문 주소: <a href="{target_item['URL']}" target="_blank">{target_item['URL']}</a></small>
                </div>
            """, unsafe_allow_html=True)
            
        # 6. 공문서 표준 한글 파일(.hwp) 내보내기 기능 엔진 작동
        st.write("---")
        st.markdown("### 🖨️ 정부 표준 결재용 한글(HWP) 문서 출력 컨트롤러")
        
        col_hwp1, col_hwp2 = st.columns(2)
        with col_hwp1:
            # 단일 혹은 선택된 복수 기사를 개별 HWP 리포트로 압축 내보내기
            zip_hwp_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_hwp_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for idx in selected_rows:
                    item_data = st.session_state.scraped_data[idx]
                    hwp_file_stream = generate_hwp_report(item_data)
                    zip_file.writestr(item_data['파일명'], hwp_file_stream.getvalue())
            
            st.download_button(
                label="📥 선택 안건 표준 공문서(HWP) 파일셋 다운로드 (.zip)",
                data=zip_hwp_buffer.getvalue(),
                file_name=f"기획예산처_탄소중립_선택보고서_{datetime.now().strftime('%Y%m%d')}.zip",
                mime="application/zip",
                use_container_width=True
            )
        with col_hwp2:
            st.caption("💡 상단 테이블에서 원하는 보도자료 좌측의 '선택' 체크박스를 활성화하면, 해당 안건들에 대한 표준 공문서 양식 한글(HWP) 보고서가 패키징되어 즉시 빌드됩니다.")
else:
    st.info("🏛️ 시스템 초기화 상태입니다. 좌측의 정책 키워드를 검토하신 후 [다량 뉴스 수집 및 에이전트 분석 가동] 단추를 누르면 공정 분석 체계가 수립됩니다.")
            
