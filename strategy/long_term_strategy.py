import pandas as pd
import numpy as np
from ta.momentum import StochRSIIndicator
from ta.trend import PSARIndicator, ADXIndicator
from strategy.base_strategy import BaseStrategy


class LongTermStrategy(BaseStrategy):
    """Enhanced long-term strategy: technical plan + adaptive risk options."""

    # ---------------------- Core Indicator Calculations ----------------------
    def tradingview_ema(self, series: pd.Series, length: int) -> pd.Series:
        return series.ewm(span=length, adjust=False).mean()

    def wave_trend(self, df, channel_length=10, average_length=21):
        hlc3 = (df['high'] + df['low'] + df['close']) / 3
        esa = hlc3.ewm(span=channel_length, adjust=False).mean()
        de = (hlc3 - esa).abs().ewm(span=channel_length, adjust=False).mean()
        ci = (hlc3 - esa) / (0.015 * de)
        wt = ci.ewm(span=average_length, adjust=False).mean()
        wt_signal = wt.rolling(4).mean()
        return float(round(wt.iloc[-1], 2)), float(round(wt_signal.iloc[-1], 2))

    def calculate_supports_resistances(self, df):
        cmp = float(df["close"].iloc[-1])
        supports = [float(round(cmp * 0.97, 0)), float(round(cmp * 0.93, 0))]
        supports = [s for s in supports if s < cmp]

        resistances = [float(round(cmp * 1.05, 0)), float(round(cmp * 1.10, 0)), float(round(cmp * 1.20, 0))]
        resistances = [r for r in resistances if r > cmp]

        return supports, resistances

    def generate_averaging_plan(self, cmp, qty, supports, buy_price):
        avg_plan = []
        current_qty = qty
        current_avg = float(buy_price)

        for lvl in supports:
            if lvl >= cmp:
                continue
            added_qty = qty
            new_total_qty = current_qty + added_qty
            new_avg = float((current_avg * current_qty + lvl * added_qty) / new_total_qty)
            avg_plan.append({
                "level": float(lvl),
                "added_qty": added_qty,
                "qty": new_total_qty,
                "new_avg": round(new_avg, 2)
            })
            current_qty = new_total_qty
            current_avg = new_avg

        return avg_plan

    # ---------------------- Main Analysis ----------------------
    def analyze(self) -> dict:
        df = self.df.copy()
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df["open"] = pd.to_numeric(df["open"], errors="coerce")
        cmp = float(df["close"].iloc[-1])

        # EMAs
        df["EMA9"] = self.tradingview_ema(df["close"], 9)
        df["EMA15"] = self.tradingview_ema(df["close"], 15)
        df["EMA21"] = self.tradingview_ema(df["close"], 21)
        ema9, ema15, ema21 = [round(float(df[e].iloc[-1]), 2) for e in ["EMA9", "EMA15", "EMA21"]]

        # ADX (trend strength)
        adx_indicator = ADXIndicator(df["high"], df["low"], df["close"], window=14)
        adx_value = round(float(adx_indicator.adx().iloc[-1]), 2)
        adx_strength = "Strong" if adx_value > 25 else "Weak"

        # StochRSI
        stochrsi = StochRSIIndicator(df["close"], window=14, smooth1=3, smooth2=3)
        stoch_rsi = round(float(stochrsi.stochrsi().iloc[-1]), 2)

        # Parabolic SAR
        psar = PSARIndicator(df["high"], df["low"], df["close"], step=0.02, max_step=0.2)
        psar_value = round(float(psar.psar().iloc[-1]), 2)
        psar_trend = "Bearish" if cmp < psar_value else "Bullish"

        # WaveTrend
        wt, wt_signal = self.wave_trend(df)
        wt_status = "Down" if wt < wt_signal else "Up"
        wt_oversold = wt < -60

        # Volume bias
        if "volume" in df.columns:
            df["avg_vol"] = df["volume"].rolling(20).mean()
            df["vol_dir"] = np.where(df["close"] > df["open"], "Bullish",
                                     np.where(df["close"] < df["open"], "Bearish", "Neutral"))
            df["vol_bias"] = np.where(
                (df["vol_dir"] == "Bullish") & (df["volume"] > df["avg_vol"]), "Bullish Accumulation",
                np.where((df["vol_dir"] == "Bearish") & (df["volume"] > df["avg_vol"]),
                         "Bearish Distribution", "Neutral")
            )
            volume_accumulation = df["vol_bias"].iloc[-1]
        else:
            volume_accumulation = "No volume data"

        # Supports / Resistances
        supports, resistances = self.calculate_supports_resistances(df)

        # Averaging plan
        avg_plan = self.generate_averaging_plan(cmp, self.qty, supports, self.buy_price)

        # Trend logic
        if cmp > ema9 > ema15 > ema21:
            trend = "Strong Bullish"
        elif cmp < ema9 < ema15 < ema21:
            trend = "Bearish"
        else:
            trend = "Sideways"

        # Targets
        targets = {
            "short_term": float(resistances[0]) if len(resistances) > 0 else None,
            "medium_term": float(resistances[1]) if len(resistances) > 1 else None,
            "long_term": float(resistances[2]) if len(resistances) > 2 else None,
        }

        risk_level = float(supports[-1]) if supports else cmp * 0.9
        risk = f"Close below {risk_level} → avoid averaging further"

        return {
            "symbol": self.symbol,
            "cmp": cmp,
            "buy_price": float(self.buy_price),
            "qty": self.qty,
            "trend": trend,
            "ema": {"EMA9": ema9, "EMA15": ema15, "EMA21": ema21},
            "adx": {"Value": adx_value, "Strength": adx_strength},
            "indicators": {
                "StochRSI": stoch_rsi,
                "WaveTrend": {"WT": wt, "Signal": wt_signal, "Status": wt_status, "Oversold": wt_oversold},
                "ParabolicSAR": {"Value": psar_value, "Trend": psar_trend},
                "VolumeAccumulation": volume_accumulation
            },
            "supports": supports,
            "resistances": resistances,
            "averaging_plan": avg_plan,
            "targets": targets,
            "risk": risk
        }

    # ---------------------- Adaptive Advice Plan ----------------------
    def advice_plan(self, report: dict) -> str:
        cmp = report["cmp"]
        buy_price = report["buy_price"]
        supports = report["supports"]
        resistances = report["resistances"]
        trend = report["trend"]
        wt_oversold = report["indicators"]["WaveTrend"]["Oversold"]
        psar_trend = report["indicators"]["ParabolicSAR"]["Trend"]
        adx_strength = report["adx"]["Strength"]

        sl = supports[-1] if supports else round(cmp * 0.93, 2)
        lines = ["", "💡 **Trade Management Options:**"]

        # Option 1 - Defensive
        if trend in ["Bearish", "Sideways"]:
            lines.append("\n**Option 1: Defensive / Capital Protection**")
            lines.append(f"If you don’t want to take further risk:")
            lines.append(f"- Keep Stop Loss = ₹{sl} (below last swing low).")
            lines.append(f"- If price closes above ₹{round(resistances[0], 2)} with good volume → add 2–3 qty near ₹{round((resistances[0]+cmp)/2, 2)} zone.")
            lines.append(f"- Exit partially at ₹{round(resistances[1], 2)} and trail stop to ₹{round(supports[0], 2)}.")

        # Option 2 - Averaging Plan
        if cmp < buy_price and supports:
            avg_zone = round(np.mean(supports[:1]), 2)
            lines.append("\n**Option 2: Averaging Strategy (Moderate Risk)**")
            lines.append(f"If you can hold for 3–5 weeks:")
            lines.append(f"- Buy 6 more qty near ₹{avg_zone} (support zone).")
            new_avg = round((buy_price + avg_zone) / 2, 2)
            lines.append(f"- New average ≈ ₹{new_avg}.")
            lines.append(f"- Next targets:")
            lines.append(f"  • T1: ₹{round(resistances[0], 2)} (EMA resistance)")
            lines.append(f"  • T2: ₹{buy_price} (break-even)")
            lines.append(f"  • T3: ₹{round(resistances[-1], 2)} (if trend reverses)")
            lines.append(f"- Keep SL = ₹{sl} (close basis)")

        # Option 3 - Long-term Fundamental Hold
        if wt_oversold or psar_trend == "Bearish" or adx_strength == "Weak":
            lines.append("\n**Option 3: Hold Only if Fundamentals Strong**")
            lines.append(f"If you are holding long-term (3+ months), and you’ve checked fundamentals:")
            lines.append(f"- Hold until price closes below ₹{sl}.")
            lines.append(f"- Use weekly chart — if price crosses 20EMA upward again, it confirms reversal.")

        return "\n".join(lines)

    # ---------------------- Report Formatting ----------------------
    def format_report(self, report: dict) -> str:
        lines = [
            f"📊 Long-Term Trade Plan — {report.get('symbol', '')}",
            f"CMP: {report['cmp']} | Buy Price: {report['buy_price']} | Qty: {report['qty']}",
            "",
            f"Trend: {report['trend']} | ADX: {report['adx']['Value']} ({report['adx']['Strength']})",
            f"EMA: {report['ema']}",
            "",
            "Indicators:",
            f"  StochRSI: {report['indicators']['StochRSI']}",
            f"  WaveTrend: WT={report['indicators']['WaveTrend']['WT']} | Signal={report['indicators']['WaveTrend']['Signal']} | Status={report['indicators']['WaveTrend']['Status']} | Oversold={report['indicators']['WaveTrend']['Oversold']}",
            f"  ParabolicSAR: {report['indicators']['ParabolicSAR']['Value']} ({report['indicators']['ParabolicSAR']['Trend']})",
            f"  Volume Accumulation: {report['indicators']['VolumeAccumulation']}",
            "",
            f"Supports: {report['supports']}",
            f"Resistances: {report['resistances']}",
            "",
            "➤ Averaging Plan:"
        ]

        if report["averaging_plan"]:
            for step in report["averaging_plan"]:
                lines.append(f"  - Add @ {step['level']} → New Avg {step['new_avg']} (Qty {step['qty']})")
        else:
            lines.append("  - No averaging suggested (CMP >= Buy Price)")

        lines.append("\n🎯 Targets:")
        for key, value in report["targets"].items():
            if value:
                lines.append(f"  - {key.replace('_', ' ').title()}: {value}")
        lines.append(f"⚠ Risk: {report['risk']}")

        # Add AI-style trade advice section
        return "\n".join(lines) + "\n" + self.advice_plan(report)
