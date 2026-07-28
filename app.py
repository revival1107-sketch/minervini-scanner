import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import math  # ✅ 추가: NaN/Inf 체크를 위한 math 모듈
from datetime import datetime, timedelta

# 페이지 설정
st.set_page_config(page_title="Minervini Auto-Scanner", layout="wide")

st.title("🎯 Minervini Super-Stock Auto-Scanner")
st.markdown("""
이 앱은 주요 시장의 전 종목을 자동으로 스캔하여 **마크 미너비니의 SEPA 전략**에 부합하는 '최적의 종목'을 발굴합니다.
- **Stage 2 상승 추세** 확인 (이평선 정배열 및 200일선 우상향)
- **52주 신고가/신저가** 위치 분석
- **기본적 분석** (실적 성장성) 및 **VCP 패턴** 근사치 분석
""")

# --- 시장별 티커 리스트 가져오기 ---
@st.cache_data(ttl=3600)
def get_sp500_tickers():
    try:  # ← 4개 공백 들여쓰기
        table = pd.read_html(
            'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies',
            keep_default_na=False
        )
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

        # ✅ 수정: 200일 이평선의 22일 전 값까지 계산하려면 최소 222거래일 데이터 필요
        if df.empty or len(df) < 222:
            return None, "데이터 부족 (최소 222거래일 필요)"

        raw_info = ticker.info
        info = raw_info if isinstance(raw_info, dict) else {}

        # ✅ 수정: 종목명 가져오기 (Ticker 옆에 괄호로 표기)
        company_name = info.get('shortName') or info.get('longName') or ""
        display_ticker = f"{ticker_symbol} ({company_name})" if company_name else ticker_symbol

        close = df['Close']
        current_price = close.iloc[-1]
        sma_50 = close.rolling(50).mean().iloc[-1]
        sma_150 = close.rolling(150).mean().iloc[-1]
        sma_200 = close.rolling(200).mean().iloc[-1]

        # ✅ 수정: 한 달(~22거래일) 전 200일선 (NaN 발생 방지를 위해 데이터 길이 확인됨)
        sma_200_series = close.rolling(200).mean()
        sma_200_month_ago = sma_200_series.iloc[-22]

        # 52주 최저/최고 (정확히 252거래일 기준)
        low_52week = close.tail(min(252, len(close))).min()
        high_52week = close.tail(min(252, len(close))).max()

        # 미너비니 Trend Template 조건
        cond1 = current_price > sma_150 and current_price > sma_200
        cond2 = sma_150 > sma_200
        cond3 = sma_50 > sma_150
        cond4 = sma_200 > sma_200_month_ago
        cond5 = current_price > (low_52week * 1.25)  # 52주 최저가의 125% 이상
        cond6 = current_price > (high_52week * 0.75)  # 52주 최고가의 75% 이상

        is_stage2 = sum([cond1, cond2, cond3, cond4, cond5, cond6]) >= 5

        # 기본정보 안전 처리 (math.isnan 사용을 위해 import math 필수)
        eps_growth = info.get('earningsQuarterlyGrowth')
        rev_growth = info.get('revenueGrowth')

        def is_valid_num(x):
            return x is not None and not (isinstance(x, float) and (math.isnan(x) or math.isinf(x)))

        is_fundamental_strong = (
            (is_valid_num(eps_growth) and eps_growth > 0.2) or
            (is_valid_num(rev_growth) and rev_growth > 0.2)
        )

        # VCP (변동성 축소 패턴 - 간소화된 근사치)
        recent_data = close.tail(60)
        volatilities = []
        for i in range(0, 60, 20):
            chunk = recent_data.iloc[i:i+20]
            if len(chunk) > 1:
                volatilities.append((chunk.max() - chunk.min()) / chunk.mean())

        is_vcp = len(volatilities) >= 3 and all(
            volatilities[i] > volatilities[i+1] for i in range(len(volatilities)-1)
        )

        if is_stage2:
            reason = []
            if cond1 and cond2 and cond3:
                reason.append("✅ 이평선 정배열")
            if cond4:
                reason.append("✅ 200일선 우상향")
            if cond5 and cond6:
                reason.append("✅ 신고가 근처")
            if is_fundamental_strong:
                reason.append("✅ 실적 성장")
            if is_vcp:
                reason.append("✅ VCP 패턴")

            return {
                "Ticker": display_ticker,
                "Price": round(current_price, 2),
                "Status": "Strong" if (is_fundamental_strong and is_vcp) else "Watch",
                "Reason": " / ".join(reason) if reason else "기본 충족",
                "Score": f"{sum([cond1, cond2, cond3, cond4, cond5, cond6])}/6"
            }, None
        return None, "미충족"
    except Exception as e:
        return None, f"에러: {str(e)}"

# --- UI 구현 ---
st.sidebar.header("⚙️ 자동 발굴 설정")
scan_mode = st.sidebar.radio("스캔 모드 선택", ["자동 발굴 (Market Scan)", "수동 입력 (Manual)"])

# 변수 초기화
tickers = []

if scan_mode == "자동 발굴 (Market Scan)":
    market = st.sidebar.selectbox(
        "대상 시장 선택",
        ["미국 (S&P 500)", "미국 (Nasdaq 100)", "한국 (KOSPI 200/주요주)"]
    )
    tickers = get_market_tickers(market)
    st.sidebar.info(f"현재 {len(tickers)}개의 종목을 전수 조사합니다.")
else:
    ticker_input = st.sidebar.text_area("티커 입력 (쉼표로 구분)", "NVDA, AAPL, MSFT, TSLA")
    if ticker_input:
        tickers = [t.strip() for t in ticker_input.split(",") if t.strip()]
    else:
        tickers = []

if st.sidebar.button("🚀 스캔 시작"):
    if not tickers:
        st.error("스캔할 종목 리스트가 없습니다. 시장을 선택하거나 티커를 입력하세요.")
    else:
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()

        for idx, ticker in enumerate(tickers):
            status_text.text(f"Analyzing {ticker} ({idx+1}/{len(tickers)})...")

            res, err = analyze_minervini(ticker)
            if res:
                results.append(res)

            progress_bar.progress((idx + 1) / len(tickers))

        status_text.empty()

        if results:
            st.subheader(f"🎯 오늘의 슈퍼 스톡 후보 ({len(results)}종목 발굴)")
            res_df = pd.DataFrame(results)

            # Strong 우선 정렬
            status_order = {"Strong": 0, "Watch": 1}
            res_df['_sort'] = res_df['Status'].map(status_order)
            res_df = res_df.sort_values(by=['_sort', 'Ticker']).drop(columns=['_sort'])

            st.table(res_df)
            st.success("위 종목들은 트렌드 템플릿을 통과한 정예 종목들입니다. 차트에서 피벗 포인트를 확인하세요!")
        else:
            st.warning("현재 시장 조건에 부합하는 종목이 없습니다. 시장 전체가 조정기일 가능성이 높습니다.")
