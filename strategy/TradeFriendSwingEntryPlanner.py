# core/TradeFriendSwingEntryPlanner.py

import pandas as pd
from datetime import datetime, timedelta
import logging
from db.TradeFriendSettingsRepo import TradeFriendSettingsRepo

logger = logging.getLogger(__name__)


class TradeFriendSwingEntryPlanner:
    """
    PURPOSE:
    - Convert a valid swing signal into a concrete trade plan
    - Fully settings-driven for FIXED mode
    - TRADITIONAL mode uses implicit RR = 1:2
    - Pure logic class (NO DB writes, NO API calls)
    """

    def __init__(self, df: pd.DataFrame, symbol: str, strategy: str):
        self.df = df
        self.symbol = symbol
        self.strategy = strategy
        self.settings_repo = TradeFriendSettingsRepo()

    # --------------------------------------------------
    # PUBLIC
    # --------------------------------------------------
    def build_plan(self) -> dict | None:
        try:
            entry = self._calculate_entry()
            sl = self._calculate_sl(entry)
            target = self._calculate_target(entry, sl)

            if entry <= sl:
                logger.warning(f"{self.symbol} → Invalid SL structure")
                return None

            rr = round((target - entry) / (entry - sl), 2)

            plan = {
                "symbol": self.symbol,
                "strategy": self.strategy,
                "entry": round(entry, 2),
                "sl": round(sl, 2),
                "target": round(target, 2),
                "rr": rr,
                "expiry_date": self._expiry_date()
            }

            logger.info(
                f"✅ Swing plan built | {self.symbol} | "
                f"Entry={plan['entry']} SL={plan['sl']} Target={plan['target']} RR={rr}"
            )

            return plan

        except Exception as e:
            logger.exception(f"Swing plan build failed for {self.symbol}: {e}")
            return None

    # --------------------------------------------------
    # ENTRY
    # --------------------------------------------------
    def _calculate_entry(self) -> float:
        """
        Default: breakout above previous candle high
        """
        last = self.df.iloc[-1]
        entry = float(last["high"])
        logger.debug(f"{self.symbol} → Entry calculated: {entry}")
        return entry

    # --------------------------------------------------
    # SL
    # --------------------------------------------------
    def _calculate_sl(self, entry: float) -> float:
        settings = dict(self.settings_repo.fetch())  # ✅ HARD NORMALIZATION

        mode = (settings.get("target_sl_mode") or "TRADITIONAL").upper()
        logger.debug(f"{self.symbol} → SL mode: {mode}")

        if mode == "TRADITIONAL":
            recent_lows = self.df["low"].tail(5)
            sl = float(recent_lows.min())
            return sl

        if mode == "FIXED":
            sl_pct = float(settings.get("fixed_sl_percent", 2.0))
            return entry * (1 - sl_pct / 100)

        raise ValueError(f"Invalid target_sl_mode: {mode}")

    # --------------------------------------------------
    # TARGET
    # --------------------------------------------------
    def _calculate_target(self, entry: float, sl: float) -> float:
        settings = dict(self.settings_repo.fetch())  # ✅ HARD NORMALIZATION

        mode = (settings.get("target_sl_mode") or "TRADITIONAL").upper()
        logger.debug(f"{self.symbol} → Target mode: {mode}")

        if mode == "TRADITIONAL":
            risk = entry - sl
            return entry + (2 * risk)

        if mode == "FIXED":
            tgt_pct = float(settings.get("fixed_target_percent", 4.0))
            return entry * (1 + tgt_pct / 100)

        raise ValueError(f"Invalid target_sl_mode: {mode}")

    # --------------------------------------------------
    # EXPIRY
    # --------------------------------------------------
    def _expiry_date(self, days: int = 7) -> str:
        return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
