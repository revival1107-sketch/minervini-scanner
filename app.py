
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 페이지 설정
st.set_page_config(page_title="Minervini Super-Stock Scanner", layout="wide")

st.title("🚀 Minervini Super-Stock Scanner")
st.markdown("""
마크 미너비니의 **SEPA 전략**과 **Trend Template**, **VCP 패턴**을 분석하여
폭발적 상승 가능성이 높은 '슈퍼 스톡'을 발굴합니다.
""")

# --- 분석 함수 정의 ---
def analyze_minervini(ticker_symbol):
    try:
         # 데이터 가져오기 (1년치)
         ticker = yf.Ticker(ticker_symbol)
         df = ticker.history(period="1y")
         info = ticker.info

         if len(df) < 200:
             return None, "데이터 부족 (200거래일 미만)"

         # 1. 트렌드 템플릿 계산
         current_price = df['Close'].iloc[-1]
         sma_50 = df['Close'].rolling(window=50).mean().iloc[-1]
         sma_150 = df['Close'].rolling(window=150).mean().iloc[-1]
         sma_200 = df['Close'].rolling(window=200).mean().iloc[-1]

         # 200일선 추세 (1개월 전과 비교)
         sma_200_month_ago = df['Close'].rolling(window=200).mean().iloc[-22]

         low_52week = df['Close'].min()
         high_52week = df['Close'].max()

         # 조건 검사
         cond1 = current_price > sma_150 and current_price > sma_200
         cond2 = sma_150 > sma_200
         cond3 = df['Close'].rolling(window=50).mean().iloc[-1] > sma_150
         cond4 = sma_200 > sma_200_month_ago
         cond5 = current_price > (low_52week * 1.25)
         cond6 = current_price > (high_52week * 0.75)

         trend_score = sum([cond1, cond2, cond3, cond4, cond5, cond6])
         is_stage2 = trend_score >= 5 # 6개 중 5개 이상 충족 시 Stage 2로 간주

         # 2. 펀더멘털 분석 (EPS 성장)
         # yfinance의 info에서 EPS 성장률 등을 가져옴 (제공되지 않는 경우 0 처리)
         eps_growth = info.get('earningsQuarterlyGrowth', 0)
         rev_growth = info.get('revenueGrowth', 0)
         is_fundamental_strong = eps_growth > 0.2 or rev_growth > 0.2

         # 3. VCP 패턴 분석 (단순화된 변동성 축소 로직)
         # 최근 3개 구간의 변동폭(고점-저점)이 줄어드는지 확인
         recent_data = df['Close'].tail(60) # 최근 60일
         chunk_size = 20
         volatilities = []
         for i in range(0, 60, chunk_size):
             chunk = recent_data.iloc[i:i+chunk_size]
             volatilities.append((chunk.max() - chunk.min()) / chunk.mean())

         # 변동성이 점진적으로 감소하는지 확인 (예: 0.2 -> 0.1 -> 0.05)
         is_vcp = volatilities[0] > volatilities[1] > volatilities[2]

         # 결과 종합
         if is_stage2:
             reason = []
             if cond1 and cond2 and cond3: reason.append("✅ 이평선 정배열 (Stage 2)")
             if cond4: reason.append("✅ 200일선 우상향 중")
             if cond5 and cond6: reason.append("✅ 52주 신고가 근처 (강한 추세)")
             if is_fundamental_strong: reason.append(f"✅ 실적 성장 확인 (EPS/매출 성장)")
             if is_vcp: reason.append("✅ VCP 패턴 감지 (변동성 축소 중)")

             return {
                 "Ticker": ticker_symbol,
                 "Price": round(current_price, 2),
                 "Status": "Strong Candidate" if (is_fundamental_strong and is_vcp) else "Trend Watch",
                 "Reason": " / ".join(reason)
             }, None

         return None, "트렌드 템플릿 미충족"

     except Exception as e:
         return None, f"오류 발생: {str(e)}"

# --- UI 구현 ---
st.sidebar.header("⚙️ 스캔 설정")
market = st.sidebar.selectbox("시장 선택", ["미국 (US)", "한국 (KR)"])
ticker_input = st.sidebar.text_area("티커 입력 (쉼표로 구분)",
                                     "NVDA, AAPL, MSFT, TSLA, AVGO, PLTR" if market == "미국 (US)" else "005930.KS, 000660.KS,
 005380.KS, 068270.KS, 005490.KS")

if st.sidebar.button("🚀 스캔 시작"):
    tickers = [t.strip() for t in ticker_input.split(",")]
    results = []

    progress_bar = st.progress(0)
    for idx, ticker in enumerate(tickers):
        with st.spinner(f"Analyzing {ticker}..."):
            res, err = analyze_minervini(ticker)
            if res:
                results.append(res)
        progress_bar.progress((idx + 1) / len(tickers))

    if results:
        st.subheader("🎯 발굴된 슈퍼 스톡 후보")
        res_df = pd.DataFrame(results)
        st.table(res_df)

        st.info("💡 **팁**: 'Strong Candidate'이면서 'VCP 패턴 감지'가 뜬 종목의 차트를 열어 피벗 포인트(돌파 지점)를
확인하세요.")
    else:
        st.warning("현재 설정된 티커 중 조건에 부합하는 종목이 없습니다.")
