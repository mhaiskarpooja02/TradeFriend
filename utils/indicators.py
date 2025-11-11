import pandas as pd
import talib

class IndicatorEngine:
    def __init__(self, df, symbol):
        self.df = df.copy()
        self.symbol = symbol

    # ---------------------------
    # EMA Crossover Check
    # ---------------------------
    def check_ema_crossover(self, EMA_SHORT=9, EMA_LONG=21, RSI_PERIOD=14,
                            VOL_PERIOD=20, CANDLES_ABOVE=3, CROSS_LOOKBACK=5, PIVOT_LOOKBACK=20):
        df = self.df.copy()
        for col in ["close", "open", "high", "low", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        if df.empty or "close" not in df.columns:
            return {"symbol": self.symbol, "reason": "No data or missing close column"}

        # Indicators
        close = df["close"].values
        df["ema_short"] = talib.EMA(close, timeperiod=EMA_SHORT)
        df["ema_long"] = talib.EMA(close, timeperiod=EMA_LONG)
        df["rsi"] = talib.RSI(close, timeperiod=RSI_PERIOD)
        df["signed_vol"] = df.apply(lambda row: row["volume"] if row["close"] > row["open"] else -row["volume"], axis=1)
        df["signed_vol_avg"] = df["signed_vol"].rolling(window=VOL_PERIOD).mean()
        df["vol_avg"] = df["signed_vol_avg"]

        # Recent crossover
        # Sanity check
        min_rows = max(EMA_LONG, VOL_PERIOD, CANDLES_ABOVE, PIVOT_LOOKBACK) + 5
        if len(df) < min_rows:
            return {"symbol": self.symbol, "reason": f"Insufficient data (< {min_rows} rows)"}

        last = df.iloc[-1]
        prev = df.iloc[-2]
        recent = df.tail(CANDLES_ABOVE)

        # --- Recent crossover logic ---
        cross_idx = None
        for i in range(1, CROSS_LOOKBACK + 1):
            if (df["ema_short"].iloc[-i] > df["ema_long"].iloc[-i]) and \
               (df["ema_short"].iloc[-i-1] <= df["ema_long"].iloc[-i-1]):
                cross_idx = i
                break
        recent_cross = cross_idx is not None

        # Count how many recent closes are above EMA_LONG
        count_above = (recent["close"] > recent["ema_long"]).sum()
        closes_above_long = count_above >= len(recent) / 2  # at least half

        rsi_curr = last["rsi"]
        rsi_ok = not pd.isna(rsi_curr) and rsi_curr < 85

        # --- Pivot Calculation (using previous candle) ---
        if {"high", "low", "close"}.issubset(df.columns):
            prev_high = float(prev["high"])
            prev_low = float(prev["low"])
            prev_close = float(prev["close"])

            # Classic Pivot
            pivot_classic = (prev_high + prev_low + prev_close) / 3
            r1_classic = 2 * pivot_classic - prev_low
            s1_classic = 2 * pivot_classic - prev_high
            r2_classic = pivot_classic + (prev_high - prev_low)
            s2_classic = pivot_classic - (prev_high - prev_low)
            r3_classic = prev_high + 2 * (pivot_classic - prev_low)
            s3_classic = prev_low - 2 * (prev_high - pivot_classic)

            # Fibonacci Pivot
            pivot_fib = pivot_classic  # same central point
            rng = prev_high - prev_low
            r1_fib = pivot_fib + (rng * 0.382)
            r2_fib = pivot_fib + (rng * 0.618)
            r3_fib = pivot_fib + (rng * 1.000)
            s1_fib = pivot_fib - (rng * 0.382)
            s2_fib = pivot_fib - (rng * 0.618)
            s3_fib = pivot_fib - (rng * 1.000)
        else:
            pivot_classic = r1_classic = s1_classic = r2_classic = s2_classic = r3_classic = s3_classic = None
            pivot_fib = r1_fib = s1_fib = r2_fib = s2_fib = r3_fib = s3_fib = None

        # --- Signal conditions ---
        if recent_cross and closes_above_long and rsi_ok:
            entry_price = float(last["close"])
            stoploss = float(last["ema_long"])
            exit_plan = "Exit if EMAShort < EMALong or Close < EMALong"

            # --- If last candle is bearish (signed volume negative) → WAIT for retrace ---
            if last["signed_vol"] <= 0:
                return {
                    "symbol": self.symbol,
                    "date": str(last.name) if hasattr(last, "name") else str(last.get("date", "")),
                    "close": self.safe_number(entry_price),
                    "ema_short": self.safe_number(last["ema_short"]),
                    "ema_long": self.safe_number(last["ema_long"]),
                    "rsi": float(last["rsi"]) if not pd.isna(last["rsi"]) else None,
                    "signal": "Bullish Crossover",
                    "confirmed": "WAIT",
                    "entry": None,
                    "sl": None,
                    "note": "Last candle shows selling pressure → Wait for retrace before entry"
                }

            # --- Position sizing by signed volume ---
            vol_ok = last["signed_vol"] > last["signed_vol_avg"] if not pd.isna(last["signed_vol_avg"]) else False
            strong_vol = vol_ok and (last["signed_vol"] >= last["signed_vol_avg"] * 1.5)

            if strong_vol:
                position_sizing = "FULL"
                qty_message = "🚀 Strong bullish demand → FULL Qty"
            elif vol_ok:
                position_sizing = "MEDIUM"
                qty_message = "✅ Decent bullish demand → MEDIUM Qty"
            else:
                position_sizing = "SMALL"
                qty_message = "⚠️ Weak bullish demand → SMALL Qty"

            # --- Adaptive Targets ---
            try:
                targets, note = self.calculate_targets(df, last, entry_price)
                if not targets or len(targets) < 3:
                    raise ValueError("Target calculation failed")
                target1, target2, target3 = targets[:3]
            except Exception as e:
                return {"symbol": self.symbol, "reason": f"Target calculation error: {e}"}

            date_str = str(last.name) if hasattr(last, "name") else str(last.get("date", ""))

            return {
        "symbol": self.symbol,
        "date": date_str,
        "close": self.safe_number(entry_price),
        "ema_short": self.safe_number(round(last["ema_short"], 2)),
        "ema_long": self.safe_number(round(last["ema_long"], 2)),
        "rsi": self.safe_number(last["rsi"]),
        "signal": "Bullish Crossover",
        "confirmed": "BUY",
        "entry": self.safe_number(entry_price),
        "sl": self.safe_number(stoploss),
        "target1": self.safe_number(round(target1, 2) if target1 else None),
        "target2": self.safe_number(round(target2, 2) if target2 else None),
        "target3": self.safe_number(round(target3, 2) if target3 else None),

        # Classic Pivot
        "pivot_classic": self.safe_number(round(pivot_classic, 2) if pivot_classic else None),
        "r1_classic": self.safe_number(round(r1_classic, 2) if r1_classic else None),
        "r2_classic": self.safe_number(round(r2_classic, 2) if r2_classic else None),
        "r3_classic": self.safe_number(round(r3_classic, 2) if r3_classic else None),
        "s1_classic": self.safe_number(round(s1_classic, 2) if s1_classic else None),
        "s2_classic": self.safe_number(round(s2_classic, 2) if s2_classic else None),
        "s3_classic": self.safe_number(round(s3_classic, 2) if s3_classic else None),

        # Fibonacci Pivot
        "pivot_fib": self.safe_number(round(pivot_fib, 2) if pivot_fib else None),
        "r1_fib": self.safe_number(round(r1_fib, 2) if r1_fib else None),
        "r2_fib": self.safe_number(round(r2_fib, 2) if r2_fib else None),
        "r3_fib": self.safe_number(round(r3_fib, 2) if r3_fib else None),
        "s1_fib": self.safe_number(round(s1_fib, 2) if s1_fib else None),
        "s2_fib": self.safe_number(round(s2_fib, 2) if s2_fib else None),
        "s3_fib": self.safe_number(round(s3_fib, 2) if s3_fib else None),

        "crossed_days_ago": cross_idx,
        "exit_plan": exit_plan,
        "position_sizing": position_sizing,
        "qty_message": qty_message,
        "note": note,
    }   
      
        reason = self.build_rejection_reason( df, last, prev, recent, CROSS_LOOKBACK)
        return {"symbol": self.symbol, "reason": reason or "Conditions not met"}

    # ---------------------------
    # Bollinger Band Momentum Check
    # ---------------------------
    def bollinger_momentum(self, period=30, stddev=2):
        df = self.df.copy()
        if df.empty or "close" not in df.columns:
            return {"symbol": self.symbol, "signal": "No Bollinger Signal"}

        close = df["close"].values
        df["bb_upper"], df["bb_middle"], df["bb_lower"] = talib.BBANDS(close, timeperiod=period,
                                                                      nbdevup=stddev, nbdevdn=stddev, matype=0)
        df["rsi"] = talib.RSI(close, timeperiod=13)
        last = df.iloc[-1]


        if last["close"] > last["bb_upper"] and last["rsi"] > 60:

            entry = self.safe_number(round(last["close"], 2))
            sl = self.safe_number(round(last["bb_middle"], 2))
            upper = self.safe_number(round(last["bb_upper"], 2))

            target1 = self.safe_number(round(entry + (entry - sl) * 0.5, 2))
            target2 = self.safe_number(round(entry + (entry - sl) * 1.0, 2))
            target3 = self.safe_number(round(entry + (entry - sl) * 1.5, 2))

            return {
                "symbol": self.symbol,
                "signal": "BB Bullish Breakout",
                "confirmed": "BUY",
                "entry": entry,
                "sl": sl,
                "target1": target1,
                "target2": target2,
                "target3": target3,
            }
        else:
            return {"symbol": self.symbol, "signal": "No Bollinger Signal"}

    # ---------------------------
    # Target Calculation
    # ---------------------------
    def calculate_targets(self, df, last, entry_price, swing_short=30, swing_long=90):
        valid_targets = []
        note = ""

        # Target 1 → Previous candle high
        prev_high = float(df.iloc[-2]["high"]) if len(df) > 1 and "high" in df.columns else None
        if prev_high and prev_high > entry_price:
            valid_targets.append(prev_high)

        # Filter bullish + strong volume candles
        if {"open", "close", "volume", "high"}.issubset(df.columns):
            avg_vol = df["volume"].mean()
            bullish_df = df[(df["close"] > df["open"]) & (df["volume"] > avg_vol)]
        else:
            bullish_df = df.copy()

        # Target 2 → Recent swing high (lookback 30 bullish candles)
        if not bullish_df.empty:
            t2 = bullish_df.tail(swing_short)["high"].max()
            if t2 > entry_price:
                valid_targets.append(t2)

        # Target 3 → Bigger swing high (lookback 90 bullish candles)
        if not bullish_df.empty:
            t3 = bullish_df.tail(swing_long)["high"].max()
            if t3 > entry_price:
                valid_targets.append(t3)

        # Fallback targets
        if not valid_targets:
            valid_targets = [entry_price * 1.02, entry_price * 1.04, entry_price * 1.06]
        else:
            if prev_high and prev_high <= entry_price and len(valid_targets) > 0:
                note = "⚠️ Possible retrace: Target 1 adjusted (prev high < entry)"

        targets = sorted(set(round(t, 2) for t in valid_targets))
        while len(targets) < 3:
            targets.append(round(targets[-1] * 1.03, 2))  # +3% increment

        # Enforce spacing rule (block size = 1.5% of entry)
        min_gap = 0.015
        spaced_targets = [targets[0]]
        for t in targets[1:]:
            if t < spaced_targets[-1] * (1 + min_gap):
                t = round(spaced_targets[-1] * (1 + min_gap), 2)
            spaced_targets.append(t)

        return spaced_targets[:3], note

    # ---------------------------
    # Build Rejection Reason
    # ---------------------------
    def build_rejection_reason(self, df, last, prev, recent, CROSS_LOOKBACK=5):
        reasons = []
        # EMA crossover check
        cross_found = False
        for i in range(1, CROSS_LOOKBACK + 1):
            if (df["ema_short"].iloc[-i] > df["ema_long"].iloc[-i]) and \
               (df["ema_short"].iloc[-i-1] <= df["ema_long"].iloc[-i-1]):
                cross_found = True
                break
        if not cross_found:
            reasons.append(f"No recent EMA crossover (last {CROSS_LOOKBACK} candles)")

        # Close vs EMA_LONG
        if not all(recent["close"] > recent["ema_long"]):
            reasons.append(f"Not all last {len(recent)} closes above EMA_LONG")

        # RSI check
        rsi_curr = last["rsi"]
        rsi_prev = df.iloc[-2]["rsi"] if not pd.isna(df.iloc[-2]["rsi"]) else None
        if pd.isna(rsi_curr):
            reasons.append("RSI not available")
        else:
            if rsi_curr >= 85:
                reasons.append(f"RSI too high ({rsi_curr:.2f})")
            elif rsi_prev is not None and rsi_curr < rsi_prev:
                reasons.append(f"RSI losing momentum (falling from {rsi_prev:.2f} to {rsi_curr:.2f})")

        # Volume check
        if last["volume"] <= last["vol_avg"]:
            reasons.append("Volume not supportive")

        return f"{self.symbol} → " + "; ".join(reasons) if reasons else None

    # ---------------------------
    # Safe Number Formatter
    # ---------------------------
    def safe_number(self, val):
        try:
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return "N/A"
            return float(val)
        except Exception:
            return "N/A"    

    # ---------------------------
    # EMA-style Formatter
    # ---------------------------
    def format_signals_daily(self, signals, trade_date):
        if not signals:
            return f"📅 Swing Trade Report — {trade_date}\n⚠️ No signals generated.\n" + "═" * 60 + "\n"

        summary = (
            f"📅 Swing Trade Report — {trade_date}\n"
            f"📈 {len(signals)} Signal(s): {', '.join(sig['symbol'] for sig in signals)}\n\n"
        )

        buy_signals = [s for s in signals if s.get("confirmed") == "BUY"]
        retrace_signals = [s for s in signals if s.get("confirmed") == "WAIT" and "selling pressure" in (s.get("note") or "")]

        details = []
        for i, sig in enumerate(buy_signals, start=1):
            block = f"""📊 Setup {i}
- Symbol: {sig['symbol']}
- Date: {trade_date}
- Close: {self.safe_number(sig.get('close'))}
- EMA Short: {self.safe_number(sig.get('ema_short'))}
- EMA Long: {self.safe_number(sig.get('ema_long'))}
- RSI: {self.safe_number(sig.get('rsi'))}
- Signal: ✅ {sig['signal']} → {sig['confirmed']}

🎯 Trade Plan
- Entry: {self.safe_number(sig.get('entry'))}
- Stoploss: {self.safe_number(sig.get('sl'))}
- Target 1: {self.safe_number(sig.get('target1'))}
- Target 2: {self.safe_number(sig.get('target2'))}
- Target 3: {self.safe_number(sig.get('target3'))}
- Exit Plan: {sig.get('exit_plan', 'N/A')}

📌 Position Sizing Advice: {sig.get('qty_message', '')}
"""
            details.append(block.strip())

        trade_plan_section = ("\n" + "-" * 60 + "\n").join(details) if details else "⚠️ No confirmed BUY setups today."

        retrace_section = ""
        if retrace_signals:
            retrace_blocks = []
            for sig in retrace_signals:
                block = f"""- Symbol: {sig['symbol']}
- Date: {trade_date}
- Close: {self.safe_number(sig.get('close'))}
- EMA Short: {self.safe_number(sig.get('ema_short'))}
- EMA Long: {self.safe_number(sig.get('ema_long'))}
- RSI: {self.safe_number(sig.get('rsi'))}
- Signal: ✅ {sig['signal']} → {sig['confirmed']}

📌 Position Sizing Advice: {sig.get('qty_message', '')}
Special Note: {sig.get('note', '')}
"""
                retrace_blocks.append(block.strip())

            retrace_section = "\n\n" + "=" * 60 + "\n\n" + "📉 Retrace Watchlist (Wait for bullish confirmation):\n" + ("\n" + "-" * 60 + "\n").join(retrace_blocks)

        return summary + trade_plan_section + retrace_section + "\n" + "═" * 60 + "\n"

    # ---------------------------
    # BB-style Formatter
    # ---------------------------
    def format_signals_bb_daily(self, signals, trade_date):
        if not signals:
            return f"📅 Swing Trade Report — {trade_date}\n⚠️ No BB signals.\n" + "═" * 60 + "\n"

        summary = (
            f"📅 BB Swing Trade Report — {trade_date}\n"
            f"📈 {len(signals)} Signal(s): {', '.join(sig['symbol'] for sig in signals)}\n\n"
        )

        buy_signals = [s for s in signals if s.get("confirmed") == "BUY" and "BB" in s.get("signal", "")]
        retrace_signals = [s for s in signals if s.get("confirmed") != "BUY"]

        details = []
        for i, sig in enumerate(buy_signals, start=1):
            block = f"""📊 Setup {i} - Symbol: {sig['symbol']} - Date: {trade_date} - Close: {self.safe_number(sig.get('close'))}
- Signal: ✅ {sig['signal']} → {sig['confirmed']}
🎯 Trade Plan - Entry: {self.safe_number(sig.get('entry'))} - Stoploss: {self.safe_number(sig.get('sl'))}
- Target 1: {self.safe_number(sig.get('target1'))} - Target 2: {self.safe_number(sig.get('target2'))} - Target 3: {self.safe_number(sig.get('target3'))}
📌 Position Sizing Advice: {sig.get('qty_message', '')}
- Note: {sig.get('note', '')}
"""
            details.append(block.strip())

        trade_plan_section = ("\n" + "-" * 60 + "\n").join(details) if details else "⚠️ No confirmed BB setups today."

        retrace_section = ""
        if retrace_signals:
            retrace_blocks = []
            for sig in retrace_signals:
                block = f"""- Symbol: {sig['symbol']} - Date: {trade_date} - Reason: {sig.get('reason', '')}
"""
                retrace_blocks.append(block.strip())

            retrace_section = "\n\n" + "=" * 60 + "\n\n" + "📉 Rejected / Waitlist:\n" + ("\n" + "-" * 60 + "\n").join(retrace_blocks)

        return summary + trade_plan_section + retrace_section + "\n" + "═" * 60 + "\n"
