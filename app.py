import os
import re
import io
import zipfile
import streamlit as st
import pandas as pd
from datetime import datetime

# 페이지 레이아웃 및 정부 표준 네이비 테마 기본 설정
st.set_page_config(page_title="탄소중립정책과 기사 분석 에이전트", layout="wide", initial_sidebar_state="expanded")

# 라이브러리 체크
try:
    import requests
    from bs4 import BeautifulSoup
    from openai import OpenAI
except ImportError:
    st.error("⚠️ 필수 라이브러리가 부족합니다. GitHub의 requirements.txt 환경을 확인해주세요.")

# 최소한의 가독성을 위한 스타일 지점 (로고 레이아웃을 건드리지 않는 범위 내)
st.markdown("""
    <style>
    .stApp { background-color: #F8FAFC; }
    /* 멀티셀렉트 태그 색상 통일 (#0A2540) */
    span[data-baseweb="tag"] { background-color: #0A2540 !important; color: #FFFFFF !important; }
    /* 버튼 스타일 통일 */
    .stButton>button { background-color: #0A2540 !important; color: #FFFFFF !important; font-weight: 600 !important; }
    </style>
""", unsafe_allow_html=True)

# ----------------------------------------------------
# [1] 로고 구현부 - 사이드바 및 메인 화면 정출처 고정
# ----------------------------------------------------
# 1. 사이드바 상단 고정
if os.path.exists("logo.png"):
    st.logo("logo.png")

# 2. 메인 화면 최상단 고정 (CSS 레이아웃 방해 없이 순정 가로 분할)
main_logo_col, main_title_col = st.columns([1, 4])

with main_logo_col:
    if os.path.exists("logo.png"):
        # 간섭을 피하기 위해 마진 없이 고정 크기로 렌더링
        st.image("logo.png", width=220)
    else:
        st.subheader("🏛️ 기획예산처")

with main_title_col:
    st.markdown("<h1 style='margin:0; padding-top:10px; color:#0A2540;'>탄소중립정책과 기사 분석 에이전트</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#475569; margin:0;'>실시간 언론 보도 자료 수집 및 빅데이터 기반 동향 분석 행정 시스템</p>", unsafe_allow_html=True)

st.write("---")

# ----------------------------------------------------
# 데이터 및 설정 세팅
# ----------------------------------------------------
if "scraped_data" not in st.session_state:
    st.session_state.scraped_data = []

# 사이드바 설정 제어판
st.sidebar.markdown("### 🔒 행정 자격 인증")
naver_client_id = st.sidebar.text_input("네이버 Client ID", value=st.secrets.get("NAVER_CLIENT_ID", ""), type="password")
naver_client_secret = st.sidebar.text_input("네이버 Client Secret", value=st.secrets.get("NAVER_CLIENT_SECRET", ""), type="password")
openai_api_key = st.sidebar.text_input("OpenAI API Key", value=st.secrets.get("OPENAI_API_KEY", ""), type="password")

st.sidebar.write("---")
st.sidebar.markdown("### 🎯 범정부 모니터링 키워드")

# 누락 없는 25개 전체 정책 키워드 풀
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

# 파일명 정제 함수
def clean_filename(filename):
    cleaned = re.sub(r'[\s\\/:*?"<>|]+', '_', filename)
    if not cleaned.endswith(".hwp"):
        cleaned += ".hwp"
    return cleaned

# 타임아웃 및 누락을 방지하는 크롤링 엔진
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
        
        # 백업 크롤링 가동
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
        return "탄소중립", "일반", "- OpenAI API Key를 입력하시면 정교한 보고서용 3줄 개조식 요약이 수립됩니다."
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
# 제어 기능 및 메인 로직 구동
# ----------------------------------------------------
# 에러 원천 방어용 클라이언트 객체 글로벌 사전 할당
openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None

col_btn1, col_btn2 = st.columns([4, 1])
with col_btn1:
    execute = st.button("🏛️ 기획예산처 지정 정책 키워드 기반 다량 뉴스 수집 및 에이전트 분석 가동", use_container_width=True)
with col_btn2:
    if st.button("🧹 전산 데이터 초기화", use_container_width=True):
        st.session_state.scraped_data = []
        st.rerun()

if execute:
    status_bar = st.empty()
    status_bar.info("⏳ 포털 다량 수집 엔진 가동 중... 실시간 보도를 긁어옵니다.")
    
    raw_news = fetch_mass_news_stable(target_keywords, naver_client_id, naver_client_secret)
    
    if not raw_news:
        status_bar.error("❌ 뉴스 수집에 실패했습니다. 네트워크 상태를 확인해주세요.")
    else:
        status_bar.info(f"🔎 총 {len(raw_news)}건의 소스 확보 완료. 행정 요약 수립 중...")
        
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
        status_bar.success(f"🏛️ 분석 완료. 총 {len(analyzed_pool)}건의 데이터가 연동되었습니다.")
        st.rerun()

# 결과 출력 화면
if st.session_state.scraped_data:
    df_display = pd.DataFrame(st.session_state.scraped_data)
    
    st.write("---")
    st.markdown("### 📊 빅데이터 기반 탄소중립 정책동향 종합 브리핑")
    with st.expander("📝 금주 탄소중립 정책동향 종합 리포트", expanded=True):
        trend_report = generate_weekly_trend_summary(st.session_state.scraped_data, openai_client)
        st.markdown(f"<div style='background-color:#ffffff; padding:15px; border:1px solid #0A2540; border-radius:4px;'>{trend_report}</div>", unsafe_allow_html=True)
        
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
    
    if selected_rows:
        st.markdown("### 🔍 선택 안건별 심층 AI 행정 요약본")
        for idx in selected_rows:
            target_item = st.session_state.scraped_data[idx]
            st.markdown(f"""
                <div style="background-color:#ffffff; padding:20px; border-left:5px solid #0A2540; border:1px solid #E2E8F0; margin-bottom:10px;">
                    <h4>📌 [{target_item['대분류']} / {target_item['소분류']}] {target_item['기사제목']}</h4>
                    <small>출처: {target_item['언론사']} | 키워드: {target_item['수집키워드']}</small>
                    <p style="background-color:#F8FAFC; padding:10px; margin-top:10px;">{target_item['5줄요약']}</p>
                </div>
            """, unsafe_allow_html=True)
            
        st.write("---")
        st.markdown("### 🖨️ 정부 표준 결재용 한글(HWP) 문서 출력")
        
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
else:
    st.info("🏛️ 시스템 초기화 상태입니다. 상단 수집 가동 단추를 누르면 공정 분석 체계가 수립됩니다.")
