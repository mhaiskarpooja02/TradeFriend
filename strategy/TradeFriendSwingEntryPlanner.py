import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class TradeFriendSwingEntryPlanner:
    """
    PURPOSE:
    - Convert a valid swing signal into a concrete trade plan
    - Pure logic class (NO DB, NO API)
    """

    def __init__(self, df: pd.DataFrame, symbol: str, strategy: str):
        self.df = df
        self.symbol = symbol
        self.strategy = strategy

    # --------------------------------------------------
    # PUBLIC API
    # --------------------------------------------------

    def build_plan(self):
        """
        Returns a swing trade plan dict or None
        """

        try:
            entry = self._calculate_entry()
            sl = self._calculate_sl(entry)
            target = self._calculate_target(entry, sl)

            if not self._is_valid_rr(entry, sl, target):
                logger.info(
                    f"{self.symbol} → RR not acceptable"
                )
                return None

            plan = {
                "symbol": self.symbol,
                "strategy": self.strategy,
                "entry": round(entry, 2),
                "sl": round(sl, 2),
                "target1": round(target, 2),
                "rr": round((target - entry) / (entry - sl), 2),
                "expiry_date": self._expiry_date()
            }

            return plan

        except Exception as e:
            logger.exception(
                f"Swing plan build failed for {self.symbol}: {e}"
            )
            return None

    # --------------------------------------------------
    # INTERNAL CALCULATIONS
    # --------------------------------------------------

    def _calculate_entry(self):
        """
        Default: next candle breakout above previous high
        """
        last = self.df.iloc[-1]
        return float(last["high"])

    def _calculate_sl(self, entry):
        """
        Default: recent swing low
        """
        recent_lows = self.df["low"].tail(5)
        return float(recent_lows.min())

    def _calculate_target(self, entry, sl):
        """
        Default: 1:2 RR
        """
        risk = entry - sl
        return entry + (2 * risk)

    def _is_valid_rr(self, entry, sl, target, min_rr=1.5):
        rr = (target - entry) / (entry - sl)
        return rr >= min_rr

    def _expiry_date(self, days=7):
        return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
