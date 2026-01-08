# core/TradeFriendDecisionRunner.py

import time
from utils.logger import get_logger
from core.TradeFriendDataProvider import TradeFriendDataProvider
from db.TradeFriendSwingPlanRepo import TradeFriendSwingPlanRepo
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from core.TradeFriendPositionSizer import TradeFriendPositionSizer
from core.TradeFriendDecisionEngine import TradeFriendDecisionEngine
from config.TradeFriendConfig import REQUEST_DELAY_SEC
from reports.MorningConfirmReport import MorningConfirmReport
from reports.MorningConfirmPdfBuilder import MorningConfirmPdfBuilder

logger = get_logger(__name__)


class TradeFriendDecisionRunner:
    """
    PURPOSE:
    - Validate swing plans in morning
    - Apply DecisionEngine (gap, sizing, confidence)
    - Generate Morning Confirm PDF
    """

    def __init__(self, mode: str, capital: float):
        self.plan_repo = TradeFriendSwingPlanRepo()
        self.trade_repo = TradeFriendTradeRepo()
        self.provider = TradeFriendDataProvider()
        self.position_sizer = TradeFriendPositionSizer()

        self.engine = TradeFriendDecisionEngine(
            trade_repo=self.trade_repo
        )

        self.report = MorningConfirmReport(mode, capital)

    # -------------------------------------------------
    # MAIN
    # -------------------------------------------------
    def run(self):
        logger.info("🚀 Morning confirmation started")

        plans = self.plan_repo.fetch_active_plans()
        if not plans:
            logger.info("No planned trades found")
            return

        for raw_plan in plans:
            try:
                self._process_plan(raw_plan)
                time.sleep(REQUEST_DELAY_SEC)
            except Exception as e:
                logger.exception(f"Decision failed: {e}")

        logger.info("✅ Morning confirmation completed")

        if not self.report.is_empty():
            pdf = MorningConfirmPdfBuilder()
            path = pdf.build(self.report)
            logger.info(f"📄 Morning Confirm Report generated → {path}")

    # -------------------------------------------------
    # PROCESS SINGLE PLAN
    # -------------------------------------------------
    def _process_plan(self, raw_plan):
        # ✅ HARD NORMALIZATION (fixes sqlite3.Row issues forever)
        plan = dict(raw_plan)

        symbol = plan["symbol"]
        entry = float(plan["entry"])
        sl = float(plan["sl"])

        target = float(
            plan.get("target")
            or plan.get("target1")
            or (entry + (entry - sl) * 2)
        )

        confidence = int(plan.get("confidence") or 7)

        logger.info(f"🔍 Checking → {symbol}")

        # -------------------------
        # FETCH LTP
        # -------------------------
        ltp = self.provider.get_ltp(symbol)

        if ltp is None or ltp <= 0:
            self.report.add(
                symbol, None, entry, sl, target,
                decision="SKIPPED",
                reason="LTP not available"
            )
            return

        # -------------------------
        # ENTRY CONDITION
        # -------------------------
        if ltp < entry:
            self.report.add(
                symbol, ltp, entry, sl, target,
                decision="SKIPPED",
                reason="Entry not triggered"
            )
            return

        # -------------------------
        # SIGNAL → DECISION ENGINE
        # -------------------------
        signal = {
            "symbol": symbol,
            "entry": entry,
            "sl": sl,
            "target": target,
            "confidence": confidence
        }

        result = self.engine.evaluate(
            ltp=ltp,
            signal=signal
        )

        # -------------------------
        # HANDLE RESULT
        # -------------------------
        cleansymbol = self.normalize_symbol(plan.get("symbol"))
        
        logger.info(f"Symbol normalized | raw={plan.get('symbol')} | clean={cleansymbol}")

        if result["decision"] == "APPROVED":
            trade = result["trade"]

            self.plan_repo.mark_triggered(plan["id"])

            self.report.add(
                cleansymbol,
                ltp, entry, sl, target,
                decision="APPROVED",
                reason="Trade created",
                qty=trade["qty"],
                position_value=trade["position_value"],
                confidence=result["confidence"]
            )
        else:
            self.report.add(
                cleansymbol, ltp, entry, sl, target,
                decision="REJECTED",
                reason=result["reason"],
                confidence=result["confidence"]
            )
   # -------------------------------------------------
    # normalize_symbol
    # -------------------------------------------------
    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        logger.info(f"Normalizing symbol → raw={symbol}")

        if not symbol:
            return ""

        return (
            symbol
            .replace("-EQ", "")
            .replace(".NS", "")
            .strip()
        )