from utils.logger import get_logger
from core.TradeFriendRiskManager import TradeFriendRiskManager

logger = get_logger(__name__)


class TradeFriendDecisionEngine:
    """
    PURPOSE:
    - SINGLE ENTRY POINT for trade approval
    - Applies confidence, sizing, and risk guardrails
    """

    def __init__(self, scorer, sizer, trade_repo):
        self.scorer = scorer
        self.sizer = sizer
        self.trade_repo = trade_repo
        self.risk_manager = TradeFriendRiskManager()

    # -------------------------------------------------
    # MAIN EVALUATION
    # -------------------------------------------------
    def evaluate(self, df, signal: dict):
        """
        Returns trade dict if approved, else None

        signal must contain:
        - symbol
        - entry
        - sl
        - target
        """

        symbol = signal.get("symbol")

        # 1️⃣ CONFIDENCE CHECK
        confidence = self.scorer.score(df)
        if confidence < 6:
            logger.info(
                f"Trade rejected | Low confidence ({confidence}) | {symbol}"
            )
            return None

        # 2️⃣ POSITION SIZING (AMOUNT-BASED)
        try:
            sizing = self.sizer.calculate(
                entry=signal["entry"],
                sl=signal["sl"]
            )
        except Exception as e:
            logger.info(
                f"Trade rejected | Position sizing failed | {symbol} | {e}"
            )
            return None

        qty = sizing["qty"]
        position_value = sizing["position_value"]
        risk_amount = sizing["risk_amount"]

        if qty <= 0:
            logger.info(
                f"Trade rejected | Qty zero | {symbol}"
            )
            return None

        # 3️⃣ RISK MANAGER GATE
        allowed, reason = self.risk_manager.can_take_trade(
            trade_repo=self.trade_repo,
            position_value=position_value
        )

        if not allowed:
            logger.warning(
                f"Trade blocked by RiskManager | {symbol} | {reason}"
            )
            return None

        # 4️⃣ FINAL TRADE OBJECT
        trade = {
            **signal,
            "qty": qty,
            "confidence": confidence,
            "risk_amount": risk_amount,
            "position_value": position_value,
            "status": "OPEN"
        }

        # 5️⃣ SAVE TRADE
        self.trade_repo.save_trade(trade)

        logger.info(
            f"Trade approved | {symbol} | Qty={qty} | "
            f"PosValue={round(position_value, 2)} | Conf={confidence}"
        )

        return trade
