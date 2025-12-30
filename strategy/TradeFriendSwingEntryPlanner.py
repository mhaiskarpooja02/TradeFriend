import talib
from datetime import datetime, timedelta


class TradeFriendSwingEntryPlanner:
    """
    PURPOSE:
    - Create swing trade PLAN (not execution)
    - Uses DAILY timeframe only
    """

    def __init__(self, df, symbol, strategy):
        self.df = df.copy()
        self.symbol = symbol
        self.strategy = strategy

    def build_plan(self):
        df = self.df

        # ---------------- SAFETY CHECKS ----------------
        if df is None or df.empty or len(df) < 60:
            return None

        close = df["close"].astype(float)
        low = df["low"].astype(float)

        # ---------------- INDICATORS ----------------
        df["ema_20"] = talib.EMA(close, timeperiod=20)
        df["ema_50"] = talib.EMA(close, timeperiod=50)
        df["atr"] = talib.ATR(
            df["high"], df["low"], close, timeperiod=14
        )

        last = df.iloc[-1]

        # ---------------- TREND FILTER ----------------
        if last["close"] < last["ema_50"]:
            return None

        # ---------------- ENTRY LOGIC ----------------
        entry = round(last["close"], 2)

        # Stoploss: ATR based (swing safe)
        sl = round(entry - (last["atr"] * 1.5), 2)

        if sl >= entry:
            return None

        # Target: Fixed RR = 1:2
        risk = entry - sl
        target1 = round(entry + (risk * 2), 2)

        rr = round((target1 - entry) / risk, 2)

        # ---------------- EXPIRY LOGIC ----------------
        expiry_date = (datetime.now() + timedelta(days=7)).date()

        # ---------------- FINAL PLAN ----------------
        return {
            "symbol": self.symbol,
            "strategy": self.strategy,
            "entry": entry,
            "sl": sl,
            "target1": target1,
            "rr": rr,
            "expiry_date": expiry_date.isoformat()
        }
