import logging
from utils.logger import get_logger
from core.TradeFriendRiskManager import TradeFriendRiskManager
from config.TradeFriendConfig import CAPITAL

logger = get_logger(__name__)


class TradeFriendDecisionEngine:
    """
    PURPOSE:
    - Final decision before trade is created
    - Applies confidence, sizing, and risk guardrails
    """

    def __init__(self, scorer, sizer, trade_repo):
        self.scorer = scorer
        self.sizer = sizer
        self.trade_repo = trade_repo
        self.risk_manager = TradeFriendRiskManager()

    def evaluate(self, df, signal):
        """
        Returns trade dict if allowed, else None
        """

        # -----------------------------
        # 1️⃣ CONFIDENCE CHECK
        # -----------------------------
        confidence = self.scorer.score(df)

        if confidence < 6:
            logger.info(
                f" Trade rejected | Low confidence ({confidence}) | {signal['symbol']}"
            )
            return None

        # -----------------------------
        # 2️⃣ POSITION SIZING
        # -----------------------------
        qty = self.sizer.calculate_qty(
            capital=CAPITAL,
            entry=signal["entry"],
            sl=signal["sl"]
        )

        if qty <= 0:
            logger.info(
                f" Trade rejected | Qty zero | {signal['symbol']}"
            )
            return None

        # -----------------------------
        # 3️⃣ RISK MANAGER GATE (OPTION B)
        # -----------------------------
        allowed, reason = self.risk_manager.can_take_trade(
            trade_repo=self.trade_repo,
            entry=signal["entry"],
            qty=qty
        )

        if not allowed:
            logger.warning(
                f" Trade blocked by RiskManager | {signal['symbol']} | {reason}"
            )
            return None

        # -----------------------------
        # 4️⃣ CREATE TRADE OBJECT
        # -----------------------------
        trade = {
            **signal,
            "qty": qty,
            "confidence": confidence
        }

        # -----------------------------
        # 5️⃣ SAVE TRADE
        # -----------------------------
        self.trade_repo.save_trade(trade)

        logger.info(
            f" Trade approved | {signal['symbol']} | Qty={qty} | Conf={confidence}"
        )

        return trade
