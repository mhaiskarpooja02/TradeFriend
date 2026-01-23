# core/TradeFriendDecisionEngine.py

from utils.logger import get_logger
from core.TradeFriendPositionSizer import TradeFriendPositionSizer
from core.TradeFriendRiskManager import TradeFriendRiskManager

logger = get_logger(__name__)


class TradeFriendDecisionEngine:
    """
    PURE DECISION ENGINE
    --------------------
    - Validate PLANNED swing plans
    - Apply sizing & risk rules
    - RETURN decision only
    - ❌ No DB writes
    - ❌ No lifecycle mutation
    """

    def __init__(self, trade_repo):
        self.trade_repo = trade_repo
        self.sizer = TradeFriendPositionSizer()
        self.risk_manager = TradeFriendRiskManager()

    def evaluate(self, plan: dict) -> dict:
        symbol = plan["symbol"]

        logger.info(f"🧠 DecisionEngine | Evaluating {symbol}")

        # --------------------------------------------------
        # BASIC VALIDATION
        # --------------------------------------------------
        entry = float(plan["entry"])
        sl = float(plan["sl"])
        target = float(plan.get("target1") or plan.get("target") or 0)
        confidence = int(plan.get("confidence", 0))

        if entry <= 0 or sl <= 0 or entry <= sl:
            return self._reject("Invalid price structure")

        if confidence < 6:
            return self._reject("Low confidence")

        if self.trade_repo.has_open_trade(symbol):
            return self._reject("Duplicate active trade")

        # --------------------------------------------------
        # POSITION SIZING
        # --------------------------------------------------
        try:
            sizing = self.sizer.calculate(entry_price=entry)
        except Exception as e:
            logger.exception("Sizing failed")
            return self._reject(f"Sizing error: {e}")

        qty = int(sizing["qty"])
        position_value = float(sizing["position_value"])

        if qty <= 0:
            return self._reject("Qty resolved to zero")

        # --------------------------------------------------
        # RISK CHECK
        # --------------------------------------------------
        allowed, reason, _ = self.risk_manager.can_take_trade(
            trade_repo=self.trade_repo,
            position_value=position_value,
            entry_price=entry
        )

        if not allowed:
            return self._reject(f"Risk blocked: {reason}")

        # --------------------------------------------------
        # APPROVED → RETURN TRADE PAYLOAD
        # --------------------------------------------------
        return {
            "decision": "APPROVED",
            "reason": "OK",
            "trade": {
                "symbol": symbol,
                "entry": entry,
                "sl": sl,
                "target": target,
                "qty": qty,
                "position_value": position_value,
                "confidence": confidence,
                "source_plan_id": plan["id"]
            }
        }

    def _reject(self, reason: str) -> dict:
        return {
            "decision": "REJECTED",
            "reason": reason,
            "trade": None
        }
