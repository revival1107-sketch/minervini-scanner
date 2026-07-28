import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import math
from datetime import datetime, timedelta

def analyze_minervini(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        # auto_adjust=True: 배당/분할 조정된 가격 (기술적 분석용 필수)
        df = ticker.history(period="1y", auto_adjust=True)
        
        # 최소 252거래일 확보 (52주 고가/저가용)
        if df.empty or len(df) < 252:
            return None, f"데이터 부족 ({len(df)}거래일, 최소 252 필요)"

        # 다중 컬럼 처리
        if isinstance(df.columns, pd.MultiIndex):
            df = df.xs(ticker_symbol, axis=1, level=1)
            
        close = df['Close'].squeeze()  # Series로 확실히 변환

        # 기업 정보 안전 획득
        try:
            info = ticker.info or {}
        except Exception:
            info = {}
        info = info if isinstance(info, dict) else {}

        company_name = info.get('shortName') or info.get('longName') or ""
        display_ticker = f"{ticker_symbol} ({company_name})" if company_name else ticker_symbol

        current_price = close.iloc[-1]
        sma_50 = close.rolling(50).mean().iloc[-1]
        sma_150 = close.rolling(150).mean().iloc[-1]
        sma_200 = close.rolling(200).mean().iloc[-1]
        sma_200_1m_ago = close.rolling(200).mean().iloc[-22]

        # 52주 고가/저가 (정확히 252거래일)
        trailing_252 = close.tail(252)
        low_52week = trailing_252.min()
        high_52week = trailing_252.max()

        # Minervini Trend Template (7개 핵심 조건)
        c1 = current_price > sma_150
        c2 = current_price > sma_200
        c3 = sma_150 > sma_200
        c4 = sma_50 > sma_150          # cond3와 동일 but 명확화
        c5 = current_price > sma_50    # 추가: 50일선 상회
        c6 = sma_200 > sma_200_1m_ago  # 200일선 상승
        c7 = current_price >= high_52week * 0.75  # 52주 고가 25% 이내

        # 점수 계산 (7개 중 6개 이상 충족)
        conditions = [c1, c2, c3, c4, c5, c6, c7]
        score = sum(conditions)
        is_stage2 = score >= 6

        # 기본적 분석 (안전한 숫자 처리)
        def safe_num(x):
            return isinstance(x, (int, float)) and not (math.isnan(x) or math.isinf(x))
        
        eps_growth = info.get('earningsQuarterlyGrowth')
        rev_growth = info.get('revenueGrowth')
        
        has_strong_fundamentals = (
            (safe_num(eps_growth) and eps_growth > 0.20) or
            (safe_num(rev_growth) and rev_growth > 0.20)
        )

        # VCP (60일 = 3개의 20일 블록)
        recent = close.tail(60)
        volatilities = [
            (recent.iloc[i:i+20].max() - recent.iloc[i:i+20].min()) / recent.iloc[i:i+20].mean()
            for i in [0, 20, 40]
        ]
        is_vcp = (
            len(volatilities) == 3 and 
            volatilities[0] > volatilities[1] > volatilities[2]
        )

        # 컨센서스/RS (yahoo 제공 시)
        rs_score = info.get('recommendationMean', None)  # 애널리스트 평균 의견

        if is_stage2:
            reasons = []
            if all([c1, c2, c3]): reasons.append("✅ 이평선 정배열")
            if c6: reasons.append("✅ 200일선 상승")
            if c7: reasons.append("✅ 52주 고가근접")
            if has_strong_fundamentals: reasons.append("✅ 실적 성장")
            if is_vcp: reasons.append("✅ VCP 패턴")

            status = "Strong" if (has_strong_fundamentals and is_vcp) else "Watch"
            
            return {
                "Ticker": display_ticker,
                "Price": round(float(current_price), 2),
                "Score": f"{score}/7",
                "Status": status,
                "Reason": " / ".join(reasons) if reasons else "기본 충족",
                "VCP": "Yes" if is_vcp else "No",
                "Fund": "Yes" if has_strong_fundamentals else "No"
            }, None
            
        return None, f"미충족 ({score}/7)"
        
    except Exception as e:
        return None, f"에러: {str(e)}"
