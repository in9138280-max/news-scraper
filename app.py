import os
import re
import io
import zipfile
import streamlit as st
import pandas as pd
from datetime import datetime

# 1. 페이지 기본 설정 (가장 상단에 위치해야 함)
st.set_page_config(page_title="뉴스 스크랩 자동화 에이전트", layout="wide")
st.title("🌿 뉴스 스크랩 자동화 에이전트")
st.caption("매일 주요 키워드의 뉴스를 수집, 분류, 요약하여 PDF로 저장합니다.")

# 필수 라이브러리 체크 및 임포트
try:
    import requests
    from bs4 import BeautifulSoup
    from openai import OpenAI
except ImportError:
    st.error("필수 라이브러리가 로드되지 않았습니다. GitHub에 requirements.txt 파일이 올바르게 있는지 확인해주세요.")

# 2. 세션 상태 및 변수 초기화
if "scraped_data" not in st.session_state:
    st.session_state.scraped_data = []

LARGE_CATEGORIES = ["배출권", "탄소시장", "탄소세", "ESG", "전기차", "탄소중립", "CBAM", "IAA"]
SMALL_CATEGORIES = ["자발적 탄소시장", "국제감출", "탄소제거", "기후공시", "전환금융", "녹색금융", "재생에너지", "기후테크"]
SEARCH_KEYWORDS = ["탈탄소", "탄소중립", "CBAM", "IIA", "녹색금융", "ESG", "탄소배출권"]

# 3. API 키 안전하게 가져오기 (Streamlit Secrets 우선 -> 없으면 사이드바 수동 입력)
st.sidebar.header("🔑 API 설정")
secrets_id = st.secrets.get("NAVER_CLIENT_ID", "")
secrets_secret = st.secrets.get("NAVER_CLIENT_SECRET", "")
secrets_openai = st.secrets.get("OPENAI_API_KEY", "")

naver_client_id = st.sidebar.text_input("네이버 Client ID", value=secrets_id, type="password")
naver_client_secret = st.sidebar.text_input("네이버 Client Secret", value=secrets_secret, type="password")
openai_api_key = st.sidebar.text_input("OpenAI API Key", value=secrets_openai, type="password")

# 4. 파일명 특수문자 전처리 함수
def clean_filename(filename):
    return re.sub(r'[\s\\/:*?"<>|]+', '_', filename)

# 5. 카테고리 분류 로직 (룰 베이스 + LLM 하이브리드)
def classify_category(title, content, openai_client=None):
    text = title + " " + content
    
    large_counts = {cat: text.count(cat) for cat in LARGE_CATEGORIES}
    small_counts = {cat: text.count(cat) for cat in SMALL_CATEGORIES}
    
    best_large = max(large_counts, key=large_counts.get) if max(large_counts.values()) > 0 else None
    best_small = max(small_counts, key=small_counts.get) if max(small_counts.values()) > 0 else None
    
    if (not best_large or not best_small) and openai_client:
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": f"주어진 뉴스 정보를 바탕으로 다음 카테고리 중 가장 적절한 대분류와 소분류를 딱 하나씩만 골라 컴마(,)로 구분해 답해줘.\n대분류 후보: {LARGE_CATEGORIES}\n소분류 후보: {SMALL_CATEGORIES}\n출력 예시: 탄소중립,기후테크"},
                    {"role": "user", "content": f"제목: {title}\n본문 일부: {content[:300]}"}
                ],
                temperature=0.0
            )
            res_text = response.choices[0].message.content.strip()
            llm_large, llm_small = res_text.split(',')
            best_large = best_large or llm_large.strip()
            best_small = best_small or llm_small.strip()
        except Exception:
            pass
            
    return best_large or "기타", best_small or "기타"

# 6. OpenAI 기반 5줄 요약 함수
def summarize_content(title, content, openai_client):
    if not openai_client:
        return "OpenAI API Key가 설정되지 않아 요약할 수 없습니다."
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "너는 뉴스 요약 전문가야. 제공된 뉴스 본문을 바탕으로 핵심 내용을 핵심만 추려서 반드시 5줄 이내의 문장으로 요약해줘. 마크다운 글머리기호(-)를 사용해줘."},
                {"role": "user", "content": f"제목: {title}\n본문: {content[:2000]}"}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"요약 실패: {str(e)}"

# 7. 네이버 뉴스 API 검색 함수
def fetch_news(keyword, client_id, client_secret):
    url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display=5&sort=sim"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json().get('items', [])
    except Exception:
        pass
    return []

# 네이버 뉴스 인링크 본문 크롤링 함수
def crawl_naver_news_article(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, "html.parser")
        
        article_body = soup.find("article", id="dic_area") or soup.find("div", id="articleBodyContents")
        if article_body:
            return article_body.get_text(strip=True)
    except Exception:
        pass
    return "본문을 직접 가져오기 어렵거나 외보고 기사입니다."

# --- UI 및 비즈니스 로직 구동 ---

if st.button("🔄 지금 스크랩 시작하기", type="primary"):
    if not (naver_client_id and naver_client_secret):
        st.warning("사이드바 또는 Secrets에 네이버 API Key를 입력해주세요.")
    else:
        # OpenAI 클라이언트 초기화 위치 안전하게 보정
        openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None
        
        all_scraped = []
        progress_bar = st.progress(0)
        st.info("뉴스를 수집하고 분석하는 중입니다. 잠시만 기다려주세요...")
        
        for idx, keyword in enumerate(SEARCH_KEYWORDS):
            items = fetch_news(keyword, naver_client_id, naver_client_secret)
            
            for item in items:
                title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", '"')
                link = item['link']
                press = item['originallink'].split('//')[-1].split('/')[0] if 'originallink' in item else "언론사"
                
                if "news.naver.com" in link:
                    content = crawl_naver_news_article(link)
                else:
                    content = item['description'].replace("<b>", "").replace("</b>", "")
                
                large_cat, small_cat = classify_category(title, content, openai_client)
                summary = summarize_content(title, content, openai_client)
                
                raw_filename = f"({large_cat})({small_cat}){title}_{press}"
                safe_filename = clean_filename(raw_filename) + ".txt" # 클라우드 안정성을 위해 기본 텍스트 추출 저장으로 세팅
                
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
            progress_bar.progress((idx + 1) / len(SEARCH_KEYWORDS))
            
        st.session_state.scraped_data = all_scraped
        st.success(f"총 {len(all_scraped)}건의 관련 기사 스크랩을 완료했습니다!")

# 스크랩 데이터 테이블 시각화 및 다운로드 영역
if st.session_state.scraped_data:
    df = pd.DataFrame(st.session_state.scraped_data)
    
    st.subheader("📋 스크랩된 기사 목록")
    df.insert(0, "선택", False)
    edited_df = st.data_editor(
        df[["선택", "대분류", "소분류", "기사제목", "언론사", "파일명"]], 
        hide_index=True, 
        use_container_width=True
    )
    
    selected_indices = edited_df[edited_df["선택"] == True].index.tolist()
    
    if selected_indices:
        st.write("---")
        st.subheader("🔍 선택한 기사 핵심 요약 (5줄 이내)")
        for idx in selected_indices:
            row = st.session_state.scraped_data[idx]
            with st.expander(f"[{row['대분류']}/{row['소분류']}] {row['기사제목']}"):
                st.markdown(row['5줄요약'])
                st.caption(f"원문 링크: {row['URL']}")
    
    st.write("---")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📥 선택한 기사 ZIP 다운로드"):
            if not selected_indices:
                st.warning("선택된 기사가 없습니다. 테이블 왼편의 체크박스를 선택해주세요.")
            else:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for idx in selected_indices:
                        item = st.session_state.scraped_data[idx]
                        # 클라우드 환경 방화벽에 안전한 정형 텍스트 리포트 생성
                        report_content = f"제목: {item['기사제목']}\n언론사: {item['언론사']}\n카테고리: [{item['대분류']}/{item['소분류']}]\nURL: {item['URL']}\n\n[5줄 요약]\n{item['5줄요약']}\n\n[본문 내용]\n{item['본문']}"
                        zip_file.writestr(item['파일명'], report_content.encode('utf-8'))
                
                st.download_button(
                    label="💾 다운로드 준비 완료 (클릭)",
                    data=zip_buffer.getvalue(),
                    file_name=f"선택기사_스크랩_{datetime.now().strftime('%Y%m%d')}.zip",
                    mime="application/zip"
                )
                
    with col2:
        if st.button("🗂️ 전체 기사 일괄 ZIP 다운로드"):
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for item in st.session_state.scraped_data:
                    report_content = f"제목: {item['기사제목']}\n언론사: {item['언론사']}\n카테고리: [{item['대분류']}/{item['소분류']}]\nURL: {item['URL']}\n\n[5줄 요약]\n{item['5줄요약']}\n\n[본문 내용]\n{item['본문']}"
                    zip_file.writestr(item['파일명'], report_content.encode('utf-8'))
            
            st.download_button(
                label="💾 전체 다운로드 준비 완료 (클릭)",
                data=zip_buffer.getvalue(),
                file_name=f"전체기사_스크랩_{datetime.now().strftime('%Y%m%d')}.zip",
                mime="application/zip"
            )
else:
    st.info("키 값을 설정한 뒤 [지금 스크랩 시작하기] 버튼을 누르면 뉴스 수집이 시작됩니다.")
