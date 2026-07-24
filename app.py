import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import time

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
        # 브라우저인 척 하기 위한 헤더 설정 (User-Agent) - 줄바꿈 수정됨
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # requests 를 통해 페이지 내용을 먼저 가져옴
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        # 가져온 HTML 텍스트를 pandas 로 읽음
        table = pd.read_html(response.text)
        df = table[0]
        # Symbol 컬럼이 있는지 확인하고 리스트 반환
        if 'Symbol' in df.columns:
            return df['Symbol'].tolist()
        else:
            return []
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
                "005935.KS", "000270.KS", "035420.KS", "035720.KS", "035450.KS", "006400.KS"]
    return []

# --- 분석 함수 ---
def analyze_minervini(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        # 데이터 다운로드
        df = ticker.history(period="1y")
        
        if df.empty or len(df) < 200:
            return None, "데이터 부족"

        # 최근 정보 추출 (info 속성은 느릴 수 있으므로 필요한 것만 추출 또는 예외 처리)
        # yfinance 최신 버전에서는 info 접근 시 에러가 날 수 있어 try-except 로 감쌈
        try:
            info = ticker.info
        except:
            info = {}

        current_price = df['Close'].iloc[-1]
        
        # 이동평균선 계산
        sma_50 = df['Close'].rolling(window=50).mean().iloc[-1]
        sma_150 = df['Close'].rolling(window=150).mean().iloc[-1]
        sma_200 = df['Close'].rolling(window=200).mean().iloc[-1]
        
        # 200 일선 전월 비교 (약 22 거래일 전)
        if len(df) > 222:
            sma_200_month_ago = df['Close'].rolling(window=200).mean().iloc[-22]
        else:
            sma_200_month_ago = sma_200 # 데이터가 부족하면 현재값으로 대체 (조건 통과 못하게 하려면 0 으로)

        low_52week = df['Close'].min()
        high_52week = df['Close'].max()

        # --- Minervini Trend Template 조건 ---
        cond1 = current_price > sma_150 and current_price > sma_200
        cond2 = sma_150 > sma_200
        cond3 = sma_50 > sma_150
        cond4 = sma_200 > sma_200_month_ago
        cond5 = current_price > (low_52week * 1.25)
        cond6 = current_price > (high_52week * 0.75)

        is_stage2 = sum([cond1, cond2, cond3, cond4, cond5, cond6]) >= 5

        # --- 기본적 분석 (실적) ---
        # yfinance 에서 성장률 데이터가 없는 경우가 많으므로 None 처리 조심
        eps_growth = info.get('earningsQuarterlyGrowth')
        rev_growth = info.get('revenueGrowth')
        
        is_fundamental_strong = False
        if eps_growth is not None and eps_growth > 0.2:
            is_fundamental_strong = True
        elif rev_growth is not None and rev_growth > 0.2:
            is_fundamental_strong = True

        # --- VCP 패턴 (간이 변동성 수축) ---
        recent_data = df['Close'].tail(60)
        chunk_size = 20
        volatilities = []
        # 60 일 데이터를 20 일씩 3 구간으로 나눔
        for i in range(0, 60, chunk_size):
            chunk = recent_data.iloc[i:i+chunk_size]
            if len(chunk) > 0:
                volatility = (chunk.max() - chunk.min()) / chunk.mean()
                volatilities.append(volatility)

        is_vcp = False
        if len(volatilities) == 3:
            # 변동성이 우하향해야 함 (첫번째 > 두번째 > 세번째)
            # 허용 오차를 두어 완벽히 감소하지 않아도 인정할 수 있으나, 여기서는 엄격하게 적용
            if volatilities[0] > volatilities[1] > volatilities[2]:
                is_vcp = True

        # --- 최종 판정 ---
        if is_stage2:
            reason = []
            if cond1 and cond2 and cond3: reason.append("✅ 이평선 정배열")
            if cond4: reason.append("✅ 200 일선 우상향")
            if cond5 and cond6: reason.append("✅ 신고가 근처")
            if is_fundamental_strong: reason.append("✅ 실적 성장")
            if is_vcp: reason.append("✅ VCP 패턴")

            # 실적이나 VCP 가 없어도 트렌드 템플릿만 통과하면 Watch 리스트에 올림
            status = "Strong" if (is_fundamental_strong and is_vcp) else "Watch"
            
            return {
                "Ticker": ticker_symbol,
                "Price": round(current_price, 2),
                "Status": status,
                "Reason": " / ".join(reason) if reason else "기본 충족"
            }, None
        
        return None, "미충족"
    
    except Exception as e:
        return None, f"에러: {str(e)}"

# --- UI 구현 ---
st.sidebar.header("⚙️ 자동 발굴 설정")
scan_mode = st.sidebar.radio("스캔 모드 선택", ["자동 발굴 (Market Scan)", "수동 입력 (Manual)"])

tickers = []

if scan_mode == "자동 발굴 (Market Scan)":
    market = st.sidebar.selectbox(
        "대상 시장 선택",
        ["미국 (S&P 500)", "미국 (Nasdaq 100)", "한국 (KOSPI 200/주요주)"]
    )
    # S&P 500 은 로딩에 시간이 걸릴 수 있으므로 캐시 활용
    with st.sidebar.spinner("티커 리스트를 불러오는 중..."):
        tickers = get_market_tickers(market)
    
    if tickers:
        st.sidebar.info(f"현재 {len(tickers)}개의 종목을 전수 조사합니다.")
    else:
        st.sidebar.warning("티커 리스트를 불러올 수 없습니다.")
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

        # 전체 종목 수에 따라 경고 메시지 (S&P 500 은 시간이 많이 걸림)
        if len(tickers) > 50:
            st.warning(f"⚠️ {len(tickers)}개 종목을 분석합니다. 완료까지 수 분이 소요될 수 있습니다.")

        for idx, ticker in enumerate(tickers):
            status_text.text(f"Analyzing {ticker} ({idx+1}/{len(tickers)})...")
            res, err = analyze_minervini(ticker)
            if res:
                results.append(res)
            # 진행률 업데이트
            progress_bar.progress((idx + 1) / len(tickers))
            
            # 너무 빠른 요청으로 인한 차단 방지 (선택사항, 느려지지만 안정적)
            # time.sleep(0.1) 

        status_text.empty()
        progress_bar.empty()

        if results:
            st.subheader(f"🎯 오늘의 슈퍼 스톡 후보 ({len(results)}종목 발굴)")
            res_df = pd.DataFrame(results)
            
            # 정렬: Strong 가 먼저, 그 다음 Ticker 순
            status_order = {"Strong": 0, "Watch": 1}
            res_df['_sort'] = res_df['Status'].map(status_order)
            res_df = res_df.sort_values(by=['_sort', 'Ticker']).drop(columns=['_sort'])
            
            # 테이블 표시
            st.dataframe(res_df, use_container_width=True)
            
            st.success("위 종목들은 트렌드 템플릿을 통과한 정예 종목들입니다. 차트에서 피벗 포인트를 확인하세요!")
        else:
            st.warning("현재 시장 조건에 부합하는 종목이 없습니다. 시장 전체가 조정기일 가능성이 높습니다.")
