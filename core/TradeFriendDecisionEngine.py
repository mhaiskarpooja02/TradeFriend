# core/TradeFriendDecisionEngine.py

from utils.logger import get_logger
from core.TradeFriendPositionSizer import TradeFriendPositionSizer
from core.TradeFriendRiskManager import TradeFriendRiskManager

logger = get_logger(__name__)


class TradeFriendDecisionEngine:
    """
    PURPOSE:
    - Single authority for trade approval
    - Validates signal, sizing, confidence, and risk
    - Returns STRUCTURED decision (never raises to caller)
    """

    def __init__(self, trade_repo):
        # 🔒 Engine OWNS its collaborators
        self.trade_repo = trade_repo
        self.sizer = TradeFriendPositionSizer()
        self.risk_manager = TradeFriendRiskManager()

    # -------------------------------------------------
    # MAIN EVALUATION
    # -------------------------------------------------
    def evaluate(self, ltp: float, signal: dict) -> dict:
        """
        Always returns a decision dict:
        {
            decision: APPROVED | REJECTED,
            reason: str,
            confidence: int | None,
            trade: dict | None
        }
        """

        logger.info(
            f"DecisionEngine.evaluate() | ltp={ltp} | signal={signal}"
        )

        # -------------------------------
        # BASIC SIGNAL VALIDATION
        # -------------------------------
        symbol = signal.get("symbol")
        entry = signal.get("entry")
        confidence = int(signal.get("confidence") or 0)

        if not symbol or not entry or entry <= 0 or not ltp or ltp <= 0:
            logger.error(
                f"Invalid signal | symbol={symbol} | entry={entry} | ltp={ltp}"
            )
            return self._reject("Invalid signal data", confidence)

        logger.info(
            f"Evaluating trade | Symbol={symbol} | Entry={entry} | LTP={ltp} | Conf={confidence}"
        )

        # -------------------------------
        # 1️⃣ ENTRY PRICE VALIDATION
        # -------------------------------
        tolerance = 0.003  # 0.3%
        if abs(ltp - entry) / entry > tolerance:
            return self._reject("Price moved", confidence)

        # -------------------------------
        # 2️⃣ CONFIDENCE CHECK
        # -------------------------------
        if confidence < 6:
            return self._reject("Low confidence", confidence)

        # -------------------------------
        # 3️⃣ POSITION SIZING
        # -------------------------------
        try:
            sizing = self.sizer.calculate(entry_price=entry)
        except Exception as e:
            logger.exception(f"Sizing failed | {symbol}")
            return self._reject(f"Sizing failed: {e}", confidence)

        qty = int(sizing.get("qty", 0))
        position_value = float(sizing.get("position_value", 0))

        if qty <= 0:
            return self._reject("Qty resolved to zero (disabled / capped)", confidence)

        # -------------------------------
        # 4️⃣ RISK MANAGER
        # -------------------------------
        allowed, reason, _ = self.risk_manager.can_take_trade(
            trade_repo=self.trade_repo,
            position_value=position_value,
            entry_price=entry
        )

        if not allowed:
            return self._reject(f"Risk blocked: {reason}", confidence)

        # -------------------------------
        # 5️⃣ APPROVE & SAVE TRADE
        # -------------------------------
        trade = {
            **signal,
            "qty": qty,
            "confidence": confidence,
            "position_value": position_value,
            "status": "OPEN"
        }

        self.trade_repo.save_trade(trade)

        logger.info(
            f"✅ Trade APPROVED | {symbol} | Qty={qty} | PosValue={position_value}"
        )

        return {
            "decision": "APPROVED",
            "reason": "OK",
            "confidence": confidence,
            "trade": trade
        }

    # -------------------------------------------------
    # INTERNAL HELPERS
    # -------------------------------------------------
    def _reject(self, reason: str, confidence: int | None) -> dict:
        logger.info(f"❌ Trade REJECTED | Reason={reason}")
        return {
            "decision": "REJECTED",
            "reason": reason,
            "confidence": confidence,
            "trade": None
        }
