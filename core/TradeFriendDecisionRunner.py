# core/TradeFriendDecisionRunner.py

import time
from utils.logger import get_logger
from core.TradeFriendDataProvider import TradeFriendDataProvider
from db.TradeFriendSwingPlanRepo import TradeFriendSwingPlanRepo
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from core.TradeFriendPositionSizer import TradeFriendPositionSizer
from config.TradeFriendConfig import REQUEST_DELAY_SEC

logger = get_logger(__name__)


class TradeFriendDecisionRunner:
    """
    PURPOSE:
    - Convert PLANNED swing plans into OPEN trades
    """

    def __init__(self):
        self.plan_repo = TradeFriendSwingPlanRepo()
        self.trade_repo = TradeFriendTradeRepo()
        self.provider = TradeFriendDataProvider()
        self.position_sizer = TradeFriendPositionSizer()

    def run(self, capital: float):
        logger.info("🚀 Morning confirmation started")

        plans = self.plan_repo.fetch_active_plans()
        if not plans:
            logger.info("No planned trades found")
            return

        for plan in plans:
            try:
                self._process_plan(plan, capital)
                time.sleep(REQUEST_DELAY_SEC)
            except Exception as e:
                logger.exception(f"Decision failed for {plan['symbol']}: {e}")

        logger.info("✅ Morning confirmation completed")

    def _process_plan(self, plan, capital):
        symbol = plan["symbol"]
        entry = float(plan["entry"])
        sl = float(plan["sl"])

        logger.info(f"Checking trigger → {symbol}")

        ltp = self.provider.get_ltp(symbol)
        if ltp is None:
            logger.warning(f"{symbol} → LTP not available")
            return

        # 🔔 ENTRY TRIGGER
        if ltp < entry:
            logger.info(f"{symbol} → Entry not triggered")
            return

        qty = self.position_sizer.calculate_qty(
            capital=capital,
            entry=entry,
            sl=sl
        )

        # ===============================
        # 🎯 TARGET CALCULATION (FIX)
        # ===============================
        if "target" in plan:
            target = float(plan["target"])
        elif "target1" in plan:
            target = float(plan["target1"])
        elif "rr" in plan:
            rr = float(plan["rr"])
            target = entry + (entry - sl) * rr
        else:
            # Default RR = 2
            target = entry + (entry - sl) * 2

        target = round(target, 2)

        if qty <= 0:
            logger.warning(f"{symbol} → Qty zero")
            return

        trade = {
            "symbol": symbol,
            "entry": entry,
            "sl": sl,
            "target": target,
            "qty": qty,
            "confidence": 1
        }

        self.trade_repo.save_trade(trade)
        self.plan_repo.mark_triggered(plan["id"])

        logger.info(f"✅ Trade CREATED → {symbol} | Qty={qty}")
