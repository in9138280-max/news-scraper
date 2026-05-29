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

# 페이지 설정
st.set_page_config(page_title="기획예산처 탄소중립정책과 AI 인텔리전스", layout="wide", initial_sidebar_state="expanded")

# CSS 스타일 (생략된 부분 없이 모두 포함)
st.markdown("""
    <style>
    .stApp { background-color: #F1F5F9; font-family: sans-serif; }
    .premium-header-card { background: #FFFFFF; padding: 2rem; border-radius: 16px; box-shadow: 0 4px 25px rgba(0,0,0,0.05); margin-bottom: 2rem; }
    .premium-title { font-size: 2rem; font-weight: 800; color: #0A2540; }
    .premium-spike-alert { background: #FFF5F5; border-left: 5px solid #E53E3E; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; color: #9B2C2C; }
    .ai-summary-box { background: #F8FAFC; border-left: 4px solid #0A2540; padding: 1rem; border-radius: 4px; margin-top: 10px; }
    </style>
""", unsafe_allow_html=True)

# 세션 상태 초기화
if "scraped_data" not in st.session_state: st.session_state.scraped_data = []

# 사이드바
st.sidebar.markdown("### 🔒 전산 자격 인증")
naver_client_id = st.sidebar.text_input("네이버 Client ID", type="password")
naver_client_secret = st.sidebar.text_input("네이버 Client Secret", type="password")
openai_api_key = st.sidebar.text_input("OpenAI API Key", type="password")

keywords = ["탄소중립", "탈탄소", "탄소배출", "배출권거래제", "CBAM", "ESG", "IAA", "ETS", "CCUS", "NFA", "GHG", "넷제로", "온실가스", "탄소세", "탄소시장", "전환금융", "녹색금융", "기후테크", "기후공시", "온실가스배출", "기후변화"]
target_keywords = st.sidebar.multiselect("조사 대상 키워드", options=keywords, default=["탄소중립", "ESG", "CBAM"])

def clean_filename(filename):
    return re.sub(r'[\s\\/:*?"<>|]+', '_', filename) + ".pdf"

# 수집 및 분석 함수들 (기존 로직 유지)
def fetch_news(keywords, cid, csecret):
    items = []
    for kw in keywords:
        url = f"https://openapi.naver.com/v1/search/news.json?query={kw}&display=10"
        headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csecret}
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            for item in res.json().get('items', []):
                item['keyword'] = kw
                items.append(item)
    return items

def analyze_article(title, content, client):
    if not client: return "탄소중립", "일반", "- 분석 대기 중"
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "기사 분석 후 '대분류:단어', '소분류:단어', '요약:- 내용' 형식으로 출력"},
                  {"role": "user", "content": f"제목: {title}\n내용: {content[:500]}"}]
    )
    return res.choices[0].message.content.strip().split('\n')

# 메인 UI
st.markdown('<div class="premium-header-card">', unsafe_allow_html=True)
st.markdown('<div class="premium-title">탄소중립정책과 기사 분석 에이전트</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# 알림 영역
if st.session_state.scraped_data:
    df_spike = pd.DataFrame(st.session_state.scraped_data)
    for kw, count in df_spike['keyword'].value_counts().items():
        if count >= 3:
            st.markdown(f'<div class="premium-spike-alert">🚨 [동향 경보] "{kw}" 관련 기사 {count}건 식별됨</div>', unsafe_allow_html=True)

if st.button("🚀 분석 가동"):
    raw_data = fetch_news(target_keywords, naver_client_id, naver_client_secret)
    analyzed = []
    client = OpenAI(api_key=openai_api_key) if openai_api_key else None
    for item in raw_data:
        large, small, summary = analyze_article(item['title'], item['description'], client)
        analyzed.append({
            "대분류": large.replace("대분류:", ""),
            "소분류": small.replace("소분류:", ""),
            "제목": item['title'],
            "언론사": item.get('originallink', '언론사'),
            "5줄요약": summary,
            "keyword": item['keyword']
        })
    st.session_state.scraped_data = analyzed
    st.rerun()

if st.button("🧹 초기화"):
    st.session_state.scraped_data = []
    st.rerun()

# 결과 표시
if st.session_state.scraped_data:
    df = pd.DataFrame(st.session_state.scraped_data)
    st.data_editor(df[["대분류", "소분류", "제목", "언론사"]], use_container_width=True)
