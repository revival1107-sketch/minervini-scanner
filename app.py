def analyze_minervini(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(period="1y")
        if df.empty or len(df) < 200:
            return None, "데이터 부족 (200일 미만)"

        raw_info = ticker.info
        info = raw_info if isinstance(raw_info, dict) else {}

        company_name = info.get('shortName') or info.get('longName') or ""
        display_ticker = f"{ticker_symbol} ({company_name})" if company_name else ticker_symbol

        close = df['Close']
        current_price = close.iloc[-1]
        sma_50 = close.rolling(50).mean().iloc[-1]
        sma_150 = close.rolling(150).mean().iloc[-1]
        sma_200 = close.rolling(200).mean().iloc[-1]
        
        # 한 달(~22거래일) 전 200일선
        sma_200_series = close.rolling(200).mean()
        sma_200_month_ago = sma_200_series.iloc[-22] if len(sma_200_series) >= 22 else sma_200

        # 52주 최저/최고 (정확히 252거래일)
        low_52week = close.tail(min(252, len(close))).min()
        high_52week = close.tail(min(252, len(close))).max()

        cond1 = current_price > sma_150 and current_price > sma_200
        cond2 = sma_150 > sma_200
        cond3 = sma_50 > sma_150
        cond4 = sma_200 > sma_200_month_ago
        cond5 = current_price > (low_52week * 1.25)   # 52주 최저가의 125% 이상
        cond6 = current_price > (high_52week * 0.75)   # 52주 최고가의 75% 이상

        is_stage2 = sum([cond1, cond2, cond3, cond4, cond5, cond6]) >= 5

        # 기본정보 안전 처리
        eps_growth = info.get('earningsQuarterlyGrowth')
        rev_growth = info.get('revenueGrowth')
        
        def is_valid_num(x):
            return x is not None and not (isinstance(x, float) and (math.isnan(x) or math.isinf(x)))
        
        is_fundamental_strong = (
            (is_valid_num(eps_growth) and eps_growth > 0.2) or
            (is_valid_num(rev_growth) and rev_growth > 0.2)
        )

        # VCP (간소화된 근사치 - 실제 매매 시 차트 확인 필수)
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
            if cond1 and cond2 and cond3: reason.append("✅ 이평선 정배열")
            if cond4: reason.append("✅ 200일선 우상향")
            if cond5 and cond6: reason.append("✅ 신고가 근처")
            if is_fundamental_strong: reason.append("✅ 실적 성장")
            if is_vcp: reason.append("✅ VCP 패턴")

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
