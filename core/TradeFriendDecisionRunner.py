# core/TradeFriendDecisionRunner.py

from datetime import datetime
import time

from utils.logger import get_logger
from db.TradeFriendSwingPlanRepo import TradeFriendSwingPlanRepo
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from db.TradeFriendSettingsRepo import TradeFriendSettingsRepo
from core.TradeFriendDecisionEngine import TradeFriendDecisionEngine
from reports.MorningConfirmReport import MorningConfirmReport
from reports.MorningConfirmPdfBuilder import MorningConfirmPdfBuilder
from config.TradeFriendConfig import REQUEST_DELAY_SEC

logger = get_logger(__name__)


class TradeFriendDecisionRunner:
    """
    Phase-1C: Morning Confirm Engine (FINAL)

    PURPOSE:
    - Evaluate PLANNED swing trade plans
    - Apply hard business rules + duplicate prevention
    - Approve or reject plans
    - Lock swing_trade_plan as single source of truth
    - Save only READY trades
    - Generate Morning Confirm report & PDF
    """

    def __init__(self):
        self.swing_plan_repo = TradeFriendSwingPlanRepo()
        self.trade_repo = TradeFriendTradeRepo()
        self.settings_repo = TradeFriendSettingsRepo()

        # ------------------------------------------------
        # Dynamic mode and capital for report
        # ------------------------------------------------
        self.trade_mode = self.settings_repo.get_trade_mode()  # PAPER / LIVE
        s = self.settings_repo.fetch()
        self.available_swing_capital = s["available_swing_capital"] or 0

        self.report = MorningConfirmReport(
            mode=self.trade_mode,
            capital=self.available_swing_capital
        )

    # ==================================================
    # MAIN ENTRY
    # ==================================================
    def run(self):
        logger.info("🧠 DecisionRunner (Phase-1C) started")

        # 1️⃣ Expire old plans automatically
        self.swing_plan_repo.expire_old_plans()

        # 2️⃣ Fetch active PLANNED plans
        planned_plans = self.swing_plan_repo.fetch_active_plans()
        if not planned_plans:
            logger.info("No PLANNED swing plans found")
            return

        # 3️⃣ Dynamic active symbols set (prevent duplicates)
        active_symbols = self.trade_repo.get_all_symbols()

        approved = 0
        rejected = 0

        # 4️⃣ Process each plan
        for plan in planned_plans:
            try:
                decision, reason = self._evaluate(plan, active_symbols)

                if decision == "APPROVE":
                    self.swing_plan_repo.mark_decision(plan["id"], "APPROVED")
                    approved += 1

                    # Add symbol immediately to prevent duplicates in same run
                    active_symbols.add(plan["symbol"])

                else:
                    self.swing_plan_repo.mark_decision(plan["id"], "REJECTED")
                    rejected += 1

            except Exception as e:
                logger.exception(f"DecisionRunner failed for {plan['symbol']}: {e}")

            # Respect request delay to avoid API throttling
            time.sleep(REQUEST_DELAY_SEC)

        logger.info(
            f"✅ DecisionRunner completed → APPROVED={approved}, REJECTED={rejected}"
        )

        # 5️⃣ Generate report & PDF
        self._generate_reports()

    # ==================================================
    # DECISION LOGIC (HARD RULES + DUPLICATES)
    # ==================================================
    def _evaluate(self, plan, active_symbols):
        symbol = plan["symbol"]

        # ----------------------------
        # RULE 1: Duplicate trade
        # ----------------------------
        if symbol in active_symbols or self.trade_repo.has_open_trade(symbol):
            return "REJECT", "Duplicate: Active trade exists"

        # ----------------------------
        # RULE 2: Capital availability
        # ----------------------------
        s = self.settings_repo.fetch()

        per_trade_capital = s["max_per_trade_capital"] or 0
        available = s["available_swing_capital"] or 0

        if available < per_trade_capital:
            return "REJECT", "Insufficient swing capital"

        # ----------------------------
        # RULE 3: Max open swing trades
        # ----------------------------
        max_open = s["max_open_trades"] or 0
        open_trades = self.trade_repo.count_open_trades()

        if max_open and open_trades >= max_open:
            return "REJECT", "Max open swing trades reached"

        # ----------------------------
        # RULE 4: Expiry safety (SAFE)
        # ----------------------------
        expiry_date = self.safe_row_value(plan, "expiry_date")

        if expiry_date:
            today = datetime.now().date()
            expiry = datetime.fromisoformat(expiry_date).date()
            if expiry < today:
                return "REJECT", "Plan expired"

        # ----------------------------
        # RULE 5: Engine evaluation
        # ----------------------------
        engine = TradeFriendDecisionEngine(trade_repo=self.trade_repo)

        confidence = self.safe_row_value(plan, "confidence", 7)

        signal = {
            "symbol": symbol,
            "entry": float(plan["entry"]),
            "sl": float(plan["sl"]),
            "target": float(
                self.safe_row_value(plan, "target1")
                or self.safe_row_value(plan, "target")
                or 0
            ),
            "confidence": int(confidence),
        }

        result = engine.evaluate(signal)

        if result["decision"] == "APPROVED":
            self.trade_repo.save_trade(result["trade"])
            return "APPROVE", None

        return "REJECT", result["reason"]

    # ==================================================
    # safe_row_value
    # ==================================================
    @staticmethod
    def safe_row_value(row, key, default=None):
        """
        Safe accessor for sqlite3.Row
        """
        try:
            return row[key]
        except (KeyError, IndexError, TypeError):
            return default

    # ==================================================
    # REPORT GENERATION
    # ==================================================
    def _generate_reports(self):
        if self.report.is_empty():
            return

        pdf = MorningConfirmPdfBuilder()

        if self.report.approved():
            pdf.build(
                title="✅ Approved Trades (READY)",
                rows=self.report.approved(),
                filename_suffix="approved"
            )

        if self.report.rejected():
            pdf.build(
                title="❌ Rejected Trades",
                rows=self.report.rejected(),
                filename_suffix="rejected"
            )

        if self.report.skipped():
            pdf.build(
                title="⏸️ Skipped / Entry Not Triggered",
                rows=self.report.skipped(),
                filename_suffix="skipped"
            )
