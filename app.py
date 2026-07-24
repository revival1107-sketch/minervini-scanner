import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests # <--- 추가됨
from datetime import datetime, timedelta

# 페이지 설정
st.set_page_config(page_title="Minervini Auto-Scanner", layout="wide")

st.title("🎯 Minervini Super-Stock Auto-Scanner")
st.markdown("""
이 앱은 사용자가 입력하지 않아도 **주요 시장 (S&P 500, KOSPI 200 등) 의 전 종목을 자동으로 스캔**하여
마크 미너비니의 SEPA 전략에 부합하는 '최적의 종목'만 발굴해 줍니다.
""")

# --- 시장별 티커 리스트 가져오기 (차단 우회 버전) ---
@st.cache_data(ttl=3600)
def get_sp500_tickers():
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        # 브라우저인 척 하기 위한 헤더 설정 (User-Agent)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)
Chrome/91.0.4472.124 Safari/537.36'
        }
        # requests 를 통해 페이지 내용을 먼저 가져옴
        response = requests.get(url, headers=headers)
        response.raise_for_status() # 에러 발생 시 예외 처리

        # 가져온 HTML 텍스트를 pandas 로 읽음
        table = pd.read_html(response.text, keep_default_na=False)
        df = table[0]
        return df['Symbol'].tolist()
    except Exception as e:
        st.warning(f"위키피디아 로드 실패 ({e}). 백업 리스트를 사용합니다.")
        return ["AAPL", "MSFT", "AMZN", "NVDA", "META", "GOOGL", "GOOG", "TSLA", "AVGO",
                "BRK-B", "WMT", "JPM", "V", "UNH", "XOM", "LLY", "JNJ", "MA", "PG", "HD"]

def get_market_tickers(market):
    if market == "미국 (S&P 500)":
        return get_sp500_tickers()
    elif market == "미국 (Nasdaq 100)":
        return ["AAPL", "MSFT", "AMZN", "NVDA", "META", "GOOGL", "GOOG", "TSLA", "AVGO",
                "PEP", "COST", "ADBE", "CSCO", "AMD", "CMCSA", "NFLX", "INTC", "TMUS",
                "AMGN", "HON"]
    elif market == "한국 (KOSPI 200/주요주)":
        return ["005930.KS", "000660.KS", "005380.KS", "068270.KS", "005490.KS",
                "005935.KS", "000270.KS", "035420.KS", "035720.KS"]
    return []

# --- 분석 함수 ---
def analyze_minervini(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(period="1y")
        if df.empty or len(df) < 200:
            return None, "데이터 부족"

        raw_info = ticker.info
        info = raw_info if isinstance(raw_info, dict) else {}

        current_price = df['Close'].iloc[-1]
        sma_50 = df['Close'].rolling(window=50).mean().iloc[-1]
        sma_150 = df['Close'].rolling(window=150).mean().iloc[-1]
        sma_200 = df['Close'].rolling(window=200).mean().iloc[-1]
        sma_200_month_ago = df['Close'].rolling(window=200).mean().iloc[-22]
        low_52week = df
