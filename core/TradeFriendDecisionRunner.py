# core/TradeFriendDecisionRunner.py

from datetime import datetime
import time

from const.PlanStatus import PlanStatus
from core.TradeFriendDecisionEngine import TradeFriendDecisionEngine
from db.TradeFriendSwingPlanRepo import TradeFriendSwingPlanRepo
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from db.TradeFriendSettingsRepo import TradeFriendSettingsRepo
from reports.MorningConfirmReport import MorningConfirmReport
from reports.MorningConfirmPdfBuilder import MorningConfirmPdfBuilder
from config.TradeFriendConfig import REQUEST_DELAY_SEC

from utils.logger import get_logger
logger = get_logger(__name__)


class TradeFriendDecisionRunner:
    """
    Phase-1C: Decision Runner (FINAL)
    --------------------------------
    - Evaluates PLANNED + HOLD plans
    - APPROVED → READY trade
    - HOLD → retry until expiry
    - REJECTED → terminal
    - EXPIRED → auto-clean
    """

    def __init__(self, ltp_provider=None):
        self.swing_plan_repo = TradeFriendSwingPlanRepo()
        self.trade_repo = TradeFriendTradeRepo()
        self.settings_repo = TradeFriendSettingsRepo()
        self.ltp_provider = ltp_provider

        s = self.settings_repo.fetch()
        self.trade_mode = self.settings_repo.get_trade_mode()
        self.capital = s["available_swing_capital"] or 0

        self.report = MorningConfirmReport(
            mode=self.trade_mode,
            capital=self.capital
        )

    # ==================================================
    # MAIN ENTRY
    # ==================================================
    def run(self):
        logger.info("🧠 DecisionRunner started")

        # Expire old plans
        self.swing_plan_repo.expire_old_plans()

        # Fetch active plans
        plans = self.swing_plan_repo.fetch_active_plans()
        if not plans:
            logger.info("No PLANNED plans found")
            return

        # Initialize unified decision engine
        engine = TradeFriendDecisionEngine(self.trade_repo)

        for plan_row in plans:
            plan = dict(plan_row)  # convert Row → dict
            symbol = plan.get("symbol")

            try:
                result = engine.evaluate(plan)

                if result["decision"] == PlanStatus.APPROVED:
                    trade = result["trade"]
                    trade["side"] = plan.get("direction", "BUY") 
                    self.trade_repo.save_trade({**trade, "status": "READY"})
                    self.swing_plan_repo.mark_decision(plan["id"], PlanStatus.APPROVED)
                    self.report.add(
                        symbol=symbol, ltp=None, entry=trade["entry"], sl=trade["sl"],
                        target=trade["target"], decision=MorningConfirmReport.DECISION_APPROVED,
                        reason="Approved", qty=trade["qty"],
                        position_value=trade["qty"] * trade["entry"],
                        confidence=trade.get("confidence")
                    )

                elif result["decision"] == PlanStatus.HOLD:
                    self.swing_plan_repo.mark_decision(plan["id"], PlanStatus.HOLD)
                    self.report.add(
                        symbol=symbol, ltp=None, entry=plan["entry"], sl=plan["sl"],
                        target=plan.get("target1") or plan.get("target"),
                        decision=MorningConfirmReport.DECISION_SKIPPED,
                        reason=f"HOLD: {result['reason']}"
                    )

                else:  # REJECTED
                    self.swing_plan_repo.mark_decision(plan["id"], PlanStatus.REJECTED)
                    self.report.add(
                        symbol=symbol, ltp=None, entry=plan["entry"], sl=plan["sl"],
                        target=plan.get("target1") or plan.get("target"),
                        decision=MorningConfirmReport.DECISION_REJECTED,
                        reason=result["reason"]
                    )

            except Exception as e:
                logger.exception(f"Decision failed for {symbol}")
                self.swing_plan_repo.mark_decision(plan["id"], PlanStatus.REJECTED)
                self.report.add(
                    symbol=symbol, ltp=None, entry=plan.get("entry"), sl=plan.get("sl"),
                    target=plan.get("target1") or plan.get("target"),
                    decision=MorningConfirmReport.DECISION_REJECTED,
                    reason=str(e)
                )

            time.sleep(REQUEST_DELAY_SEC)

        # Generate PDF reports
        self._generate_reports()

    # ==================================================
    # REPORT OUTPUT
    # ==================================================
    def _generate_reports(self):
        if self.report.is_empty():
            logger.info("No report data generated")
            return

        pdf = MorningConfirmPdfBuilder()

        if self.report.has_approved():
            pdf.build(
                title="✅ Approved Trades",
                rows=self.report.approved(),
                filename_suffix="approved",
                mode=self.trade_mode,
                capital=self.capital
            )

        if self.report.has_rejected():
            pdf.build(
                title="❌ Rejected Trades",
                rows=self.report.rejected(),
                filename_suffix="rejected",
                mode=self.trade_mode,
                capital=self.capital
            )

        if self.report.has_skipped():
            pdf.build(
                title="⏸ Held Trades",
                rows=self.report.skipped(),
                filename_suffix="hold",
                mode=self.trade_mode,
                capital=self.capital
            )
