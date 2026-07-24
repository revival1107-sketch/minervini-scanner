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
이 앱은 사용자가 입력하지 않아도 **주요 시장(S&P 500, KOSPI 200 등)의 전 종목을 자동으로 스캔**하여
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
# requests를 통해 페이지 내용을 먼저 가져옴
response = requests.get(url, headers=headers)
response.raise_for_status() # 에러 발생 시 예외 처리

# 가져온 HTML 텍스트를 pandas로 읽음
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
low_52week = df['Close'].min()
high_52week = df['Close'].max()

cond1 = current_price > sma_150 and current_price > sma_200
cond2 = sma_150 > sma_200
cond3 = sma_50 > sma_150
cond4 = sma_200 > sma_200_month_ago
cond5 = current_price > (low_52week * 1.25)
cond6 = current_price > (high_52week * 0.75)

is_stage2 = sum([cond1, cond2, cond3, cond4, cond5, cond6]) >= 5

eps_growth = info.get('earningsQuarterlyGrowth')
rev_growth = info.get('revenueGrowth')
is_fundamental_strong = (
(eps_growth is not None and eps_growth > 0.2) or
(rev_growth is not None and rev_growth > 0.2)
)

recent_data = df['Close'].tail(60)
chunk_size = 20
volatilities = []
for i in range(0, 60, chunk_size):
chunk = recent_data.iloc[i:i+chunk_size]
if len(chunk) > 0:
volatilities.append((chunk.max() - chunk.min()) / chunk.mean())

is_vcp = False
if len(volatilities) == 3:
is_vcp = volatilities[0] > volatilities[1] > volatilities[2]

if is_stage2:
reason = []
if cond1 and cond2 and cond3: reason.append("✅ 이평선 정배열")
if cond4: reason.append("✅ 200일선 우상향")
if cond5 and cond6: reason.append("✅ 신고가 근처")
if is_fundamental_strong: reason.append("✅ 실적 성장")
if is_vcp: reason.append("✅ VCP 패턴")

return {
"Ticker": ticker_symbol,
"Price": round(current_price, 2),
"Status": "Strong" if (is_fundamental_strong and is_vcp) else "Watch",
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
status_order = {"Strong": 0, "Watch": 1}
res_df['_sort'] = res_df['Status'].map(status_order)
res_df = res_df.sort_values(by=['_sort', 'Ticker']).drop(columns=['_sort'])
st.table(res_df)
st.success("위 종목들은 트렌드 템플릿을 통과한 정예 종목들입니다. 차트에서 피벗 포인트를 확인하세요!")
else:
st.warning("현재 시장 조건에 부합하는 종목이 없습니다. 시장 전체가 조정기일 가능성이 높습니다.")
