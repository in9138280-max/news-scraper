import os
import re
import io
import zipfile
import asyncio
import streamlit as st
import pandas as pd
from collections import Counter
from datetime import datetime

# 주요 라이브러리 (보안망 환경을 고려해 필요시 알림 제공)
try:
    import requests
    from bs4 import BeautifulSoup
    from openai import OpenAI
    from playwright.sync_api import sync_playwright
except ImportError:
    st.error("필수 라이브러리가 부족합니다. 터미널에 다음을 입력해 설치해주세요:\n"
             "`pip pip install requests beautifulsoup4 openai streamlit playwright pandas` 후 "
             "`playwright install`을 실행해야 합니다.")

# 1. 페이지 기본 설정 및 세션 상태 초기화
st.set_page_config(page_title="뉴스 스크랩 자동화 에이전트", layout="wide")
st.title(" 🌿 뉴스 스크랩 자동화 에이전트")
st.caption("매일 주요 키워드의 뉴스를 수집, 분류, 요약하여 PDF로 저장합니다.")

if "scraped_data" not in st.session_state:
    st.session_state.scraped_data = []

# 2. 고정 상수 정의
LARGE_CATEGORIES = ["배출권", "탄소시장", "탄소세", "ESG", "전기차", "탄소중립", "CBAM", "IAA"]
SMALL_CATEGORIES = ["자발적 탄소시장", "국제감출", "탄소제거", "기후공시", "전환금융", "녹색금융", "재생에너지", "기후테크"]
SEARCH_KEYWORDS = ["탈탄소", "탄소중립", "CBAM", "IIA", "녹색금융", "ESG", "탄소배출권"]

# API 키 및 크리덴셜 설정 (Streamlit 사이드바)
st.sidebar.header("🔑 API 설정")
naver_client_id = st.sidebar.text_input("네이버 Client ID", type="password")
naver_client_secret = st.sidebar.text_input("네이버 Client Secret", type="password")
openai_api_key = st.sidebar.text_input("OpenAI API Key", type="password")

# 3. 유틸리티 함수: 파일명 특수문자 전처리
def clean_filename(filename):
    # \ / : * ? " < > | 특수문자를 언더바(_)로 치환
    return re.sub(r'[\s\\/:*?"<>|]+', '_', filename)

# 4. 카테고리 분류 로직 (룰 베이스 + LLM 하이브리드)
def classify_category(title, content, openai_client=None):
    text = title + " " + content
    
    # 1차: 빈도수 체크
    large_counts = {cat: text.count(cat) for cat in LARGE_CATEGORIES}
    small_counts = {cat: text.count(cat) for cat in SMALL_CATEGORIES}
    
    best_large = max(large_counts, key=large_counts.get) if max(large_counts.values()) > 0 else None
    best_small = max(small_counts, key=small_counts.get) if max(small_counts.values()) > 0 else None
    
    # 2차: 모호할 경우 OpenAI LLM 사용 (Fallback)
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

# 5. OpenAI 기반 5줄 요약 함수
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

# 6. 네이버 뉴스 API 검색 및 크롤링
def fetch_news(keyword, client_id, client_secret):
    url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display=5&sort=sim"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get('items', [])
    return []

# 네이버 뉴스 인링크 본문 및 이미지 크롤링 함수
def crawl_naver_news_article(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, "html.parser")
        
        # 네이버 뉴스 본문 영역 파싱 (언론사별 구조 다름 대응 기본형)
        article_body = soup.find("article", id="dic_area") or soup.find("div", id="articleBodyContents")
        if article_body:
            # 본문 내 텍스트 추출
            text = article_body.get_text(strip=True)
            return text
    except Exception:
        pass
    return "본문을 가져올 수 없는 링크이거나 외보고 기사입니다."

# 7. Playwright를 활용한 웹페이지 PDF 변환 기능
def convert_url_to_pdf(url):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle")
            # PDF 바이너리로 리턴
            pdf_data = page.pdf(format="A4", print_background=True)
            browser.close()
            return pdf_data
    except Exception as e:
        st.error(f"PDF 생성 중 실패 (Playwright 오류): {e}")
        return None

# --- UI 및 비즈니스 로직 구동 ---

if st.button("🔄 지금 스크랩 시작하기", type="primary"):
    if not (naver_client_id and naver_client_secret):
        st.warning("네이버 API Key (ID/Secret)를 입력해주세요.")
    else:
        openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None
        
        all_scraped = []
        progress_bar = st.progress(0)
        st.info("뉴스를 수집하고 분석하는 중입니다. 잠시만 기다려주세요...")
        
        # 각 키워드별 순회 검색
        for idx, keyword in enumerate(SEARCH_KEYWORDS):
            items = fetch_news(keyword, naver_client_id, naver_client_secret)
            
            for item in items:
                title = item['title'].replace("<b>", "").replace("</b>", "")
                link = item['link']
                press = item['originallink'].split('//')[-1].split('/')[0] if 'originallink' in item else "언론사"
                
                # 네이버 뉴스 인링크(news.naver.com) 우선 수집
                if "news.naver.com" in link:
                    content = crawl_naver_news_article(link)
                else:
                    content = item['description'].replace("<b>", "").replace("</b>", "")
                
                # 카테고리 및 요약 진행
                large_cat, small_cat = classify_category(title, content, openai_client)
                summary = summarize_content(title, content, openai_client)
                
                # 파일명 생성 규칙 적용 및 전처리
                raw_filename = f"({large_cat})({small_cat}){title}_{press}"
                safe_filename = clean_filename(raw_filename) + ".pdf"
                
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
            
        st.session_state.scraped_data = all_scraped
        st.success(f"총 {len(all_scraped)}건의 관련 기사 스크랩을 완료했습니다!")

# 8. 스크랩 데이터 테이블 시각화 및 다운로드 영역
if st.session_state.scraped_data:
    df = pd.DataFrame(st.session_state.scraped_data)
    
    st.subheader("📋 스크랩된 기사 목록")
    st.caption("다운로드할 기사들을 다중 선택한 뒤 하단에서 일괄 다운로드 버튼을 누르세요.")
    
    # 사용자가 선택할 수 있는 데이터 편집기(Table) 제공
    df.insert(0, "선택", False)
    edited_df = st.data_editor(
        df[["선택", "대분류", "소분류", "기사제목", "언론사", "파일명"]], 
        hide_index=True, 
        use_container_width=True
    )
    
    # 선택된 기사의 인덱스 추출
    selected_indices = edited_df[edited_df["선택"] == True].index.tolist()
    
    # 아래 공간에 선택한 기사의 요약문 실시간 출력
    if selected_indices:
        st.write("---")
        st.subheader("🔍 선택한 기사 핵심 요약 (5줄 이내)")
        for idx in selected_indices:
            row = st.session_state.scraped_data[idx]
            with st.expander(f"[{row['대분류']}/{row['소분류']}] {row['기사제목']}"):
                st.markdown(row['5줄요약'])
                st.caption(f"원문 링크: {row['URL']}")
    
    # 9. 다운로드 처리 (선택 다운로드 / 전체 다운로드)
    st.write("---")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📥 선택한 기사 ZIP 다운로드"):
            if not selected_indices:
                st.warning("선택된 기사가 없습니다. 테이블 왼편의 체크박스를 선택해주세요.")
            else:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    with st.spinner("선택된 기사 웹페이지를 이미지 포함 PDF로 굽는 중..."):
                        for idx in selected_indices:
                            item = st.session_state.scraped_data[idx]
                            pdf_bytes = convert_url_to_pdf(item['URL'])
                            if pdf_bytes:
                                zip_file.writestr(item['파일명'], pdf_bytes)
                
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
                with st.spinner("모든 기사 웹페이지를 이미지 포함 PDF로 굽는 중..."):
                    for item in st.session_state.scraped_data:
                        pdf_bytes = convert_url_to_pdf(item['URL'])
                        if pdf_bytes:
                            zip_file.writestr(item['파일명'], pdf_bytes)
            
            st.download_button(
                label="💾 전체 다운로드 준비 완료 (클릭)",
                data=zip_buffer.getvalue(),
                file_name=f"전체기사_스크랩_{datetime.now().strftime('%Y%m%d')}.zip",
                mime="application/zip"
            )
else:
    st.info("사이드바에 API 키를 입력한 뒤 [지금 스크랩 시작하기] 버튼을 누르면 데이터가 표시됩니다.")