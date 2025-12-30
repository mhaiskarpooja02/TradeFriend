# core/TradeFriendSwingTriggerEngine.py

import logging
from datetime import datetime
from core.TradeFriendDataProvider import TradeFriendDataProvider

logger = logging.getLogger(__name__)


class TradeFriendSwingTriggerEngine:
    """
    PURPOSE:
    - Monitor LTP during market hours
    - Trigger swing trade when entry price is hit
    - Supports PAPER trading initially
    """

    def __init__(
        self,
        swing_plan_repo,
        trade_repo,
        capital,
        paper_trade=True
    ):
        self.swing_plan_repo = swing_plan_repo
        self.trade_repo = trade_repo
        self.capital = capital
        self.paper_trade = paper_trade
        self.provider = TradeFriendDataProvider()

    # -----------------------------------
    # MAIN RUN METHOD
    # -----------------------------------
    def run(self):
        logger.info("📡 Swing Trigger Engine started")

        plans = self.swing_plan_repo.fetch_active_plans()

        if not plans:
            logger.info("No active swing plans")
            return

        for plan in plans:
            try:
                self._process_plan(plan)
            except Exception as e:
                logger.exception(
                    f"Trigger failed for {plan['symbol']}: {e}"
                )

        logger.info("✅ Swing Trigger Engine completed")

    # -----------------------------------
    # PROCESS SINGLE PLAN
    # -----------------------------------
    def _process_plan(self, plan):
        symbol = plan["symbol"]
        entry = float(plan["entry"])
        sl = float(plan["sl"])
        target = float(plan["target1"])

        # ---------------- EXPIRY CHECK ----------------
        if plan.get("expiry_date"):
            if plan["expiry_date"] < datetime.now().date().isoformat():
                logger.info(f"⌛ Plan expired | {symbol}")
                return

        # ---------------- FETCH LTP ----------------
        ltp = self.provider.get_ltp(symbol)

        if not ltp or ltp <= 0:
            logger.warning(f"{symbol} → Invalid LTP")
            return

        # ---------------- GAP FILTER ----------------
        risk = entry - sl
        if risk <= 0:
            logger.warning(f"{symbol} → Invalid risk")
            return

        # Skip if gap eats full RR
        if ltp > entry + risk:
            logger.warning(
                f"⚠️ GAP SKIP | {symbol} | LTP={ltp} Entry={entry}"
            )
            return

        # ---------------- ENTRY CONDITION ----------------
        if ltp < entry:
            logger.info(f"⏳ Waiting | {symbol} | LTP={ltp}")
            return

        logger.info(
            f"🚀 ENTRY HIT | {symbol} | LTP={ltp} ≥ Entry={entry}"
        )

        # ---------------- POSITION SIZING ----------------
        qty = self.sizer.calculate_qty(
            capital=self.capital,
            entry=entry,
            sl=sl
        )

        if qty <= 0:
            logger.warning(f"{symbol} → Qty zero, skipping")
            return

        # ---------------- SAVE TRADE ----------------
        trade = {
            "symbol": symbol,
            "entry": entry,
            "sl": sl,
            "target1": target,
            "qty": qty,
            "confidence": plan.get("rr", 0),
            "status": "PAPER" if self.paper_trade else "LIVE"
        }

        self.trade_repo.save_trade(trade)

        # ---------------- UPDATE PLAN STATUS ----------------
        self.swing_plan_repo.mark_triggered(plan["id"])

        logger.info(
            f"✅ SWING TRADE TRIGGERED | {symbol} | "
            f"Qty={qty} | Mode={'PAPER' if self.paper_trade else 'LIVE'}"
        )
