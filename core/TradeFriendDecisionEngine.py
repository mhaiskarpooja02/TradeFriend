# core/TradeFriendDecisionEngine.py

from utils.logger import get_logger
from core.TradeFriendPositionSizer import TradeFriendPositionSizer
from core.TradeFriendRiskManager import TradeFriendRiskManager

logger = get_logger(__name__)


class TradeFriendDecisionEngine:
    """
    PURPOSE (PHASE-1 ONLY):
    - Decide whether a swing plan is VALID for today
    - Capital + confidence gate ONLY
    - NO execution, NO tolerance, NO OMS
    """

    def __init__(self, trade_repo):
        self.trade_repo = trade_repo
        self.sizer = TradeFriendPositionSizer()
        self.risk_manager = TradeFriendRiskManager()

    # =====================================================
    # MAIN EVALUATION
    # =====================================================
    def evaluate(self, signal: dict) -> dict:
        """
        Returns:
        {
            decision: APPROVED | REJECTED,
            reason: str,
            confidence: int,
            trade: dict | None
        }
        """

        logger.info(f"DecisionEngine.evaluate | signal={signal}")

        # -------------------------------
        # BASIC VALIDATION
        # -------------------------------
        symbol = signal.get("symbol")
        entry = float(signal.get("entry", 0))
        sl = float(signal.get("sl", 0))
        target = float(signal.get("target", 0))
        confidence = int(signal.get("confidence", 0))

        if not symbol or entry <= 0 or sl <= 0 or entry <= sl:
            return self._reject("Invalid price structure", confidence)

        if confidence < 6:
            return self._reject("Low confidence", confidence)
        
        # Inside evaluate()
        if self.trade_repo.has_open_trade(symbol):
            return self._reject("Duplicate: Active trade exists", confidence)

        # -------------------------------
        # POSITION SIZING (PLANNED)
        # -------------------------------
        try:
            sizing = self.sizer.calculate(entry_price=entry)
        except Exception as e:
            logger.exception("Position sizing failed")
            return self._reject(f"Sizing error: {e}", confidence)

        qty = int(sizing.get("qty", 0))
        position_value = float(sizing.get("position_value", 0))

        if qty <= 0:
            return self._reject("Qty resolved to zero", confidence)

        # -------------------------------
        # CAPITAL / RISK CHECK
        # -------------------------------
        allowed, reason, _ = self.risk_manager.can_take_trade(
            trade_repo=self.trade_repo,
            position_value=position_value,
            entry_price=entry
        )

        if not allowed:
            return self._reject(f"Risk blocked: {reason}", confidence)

        # -------------------------------
        # APPROVE (NO EXECUTION)
        # -------------------------------
        trade = {
            "symbol": symbol,
            "entry": entry,
            "sl": sl,
            "target": target,
            "qty": qty,     
            "filled_qty": 0,
            "avg_entry": None,
            "position_value": position_value,
            "confidence": confidence,
            "status": "READY",     # 🔒 PHASE-1 OUTPUT
            "triggered": 0
        }

        logger.info(f"✅ Trade APPROVED (READY) | {symbol}")

        return {
            "decision": "APPROVED",
            "reason": "OK",
            "confidence": confidence,
            "trade": trade
        }

    # =====================================================
    # INTERNAL
    # =====================================================
    def _reject(self, reason: str, confidence: int) -> dict:
        logger.info(f"❌ Trade REJECTED | {reason}")
        return {
            "decision": "REJECTED",
            "reason": reason,
            "confidence": confidence,
            "trade": None
        }
