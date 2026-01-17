import logging
from datetime import datetime

from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from db.TradeFriendBrokerTradeRepo import TradeFriendBrokerTradeRepo
from db.TradeFriendOrderAuditRepo import TradeFriendOrderAuditRepo
from db.TradeFriendOrderConfigRepo import TradeFriendOrderConfigRepo

from brokers.tradefriend_dhan_order_adapter import TradeFriendDhanOrderAdapter
from brokers.tradefriend_angel_order_adapter import TradeFriendAngelOrderAdapter

logger = logging.getLogger(__name__)


class TradeFriendExitOrderService:
    """
    PURPOSE:
    - Central EXIT OMS
    - Handles Partial / Final / SL exits    
    - Broker-agnostic
    - Qty-aware (remaining qty)
    """

    def __init__(self):
        self.trade_repo = TradeFriendTradeRepo()
        self.broker_trade_repo = TradeFriendBrokerTradeRepo()
        self.audit_repo = TradeFriendOrderAuditRepo()
        self.config_repo = TradeFriendOrderConfigRepo()

        self.dhan = TradeFriendDhanOrderAdapter()
        self.angel = TradeFriendAngelOrderAdapter()

    # =====================================================
    # PUBLIC API (ONLY WAY TO EXIT A TRADE)
    # =====================================================
    def place_exit_order(
        self,
        trade_id: int,
        exit_reason: str,
        exit_qty: int,
        exit_price: float | None = None
    ) -> bool:
        """
        Single exit gateway for ALL exits
        """

        trade = self.trade_repo.fetch_by_id(trade_id)
        if not trade:
            logger.error(f"Exit OMS → Trade not found: {trade_id}")
            return False

        symbol = trade["symbol"]
        side = "SELL" if trade["side"] == "BUY" else "BUY"

        remaining_qty = trade["remaining_qty"]
        if exit_qty <= 0 or exit_qty > remaining_qty:
            logger.error(
                f"{symbol} → Invalid exit qty {exit_qty} (remaining {remaining_qty})"
            )
            return False

        cfg = self.config_repo.get()
        mode = cfg["order_mode"]

        logger.warning(
            f"🚪 EXIT OMS | {symbol} | Qty={exit_qty} | Reason={exit_reason}"
        )

        # -------------------------------------------------
        # AUDIT: EXIT ATTEMPT
        # -------------------------------------------------
        audit_id = self.audit_repo.log_attempt(
            trade_id=trade_id,
            symbol=symbol,
            broker="OMS_EXIT",
            order_mode=mode,
            side=side,
            qty=exit_qty
        )

        # -------------------------------------------------
        # PAPER MODE
        # -------------------------------------------------
        if mode == "PAPER":
            self._finalize_exit(
                trade,
                exit_qty,
                exit_reason,
                exit_price or trade["ltp"]
            )

            self.audit_repo.log_result(
                audit_id,
                status="SKIPPED",
                error="PAPER MODE"
            )
            return True

        # -------------------------------------------------
        # LIVE MODE
        # -------------------------------------------------
        results = []

        if cfg.get("angel_enabled") and cfg.get("angel_auto_order"):
            result = self.angel.place_order(symbol, exit_qty, side)
            results.append(("ANGEL", result))

        if cfg.get("dhan_enabled") and cfg.get("dhan_auto_order"):
            result = self.dhan.place_order(symbol, exit_qty, side)
            results.append(("DHAN", result))

        success = any(r[1] for r in results)

        self.audit_repo.log_result(
            audit_id,
            status="SUCCESS" if success else "FAILED"
        )

        if not success:
            logger.error(f"{symbol} → EXIT FAILED")
            return False

        # -------------------------------------------------
        # FINALIZE EXIT (DB)
        # -------------------------------------------------
        self._finalize_exit(
            trade,
            exit_qty,
            exit_reason,
            exit_price
        )

        return True

    # =====================================================
    # INTERNAL FINALIZER (VERY IMPORTANT)
    # =====================================================
    def _finalize_exit(
        self,
        trade,
        exit_qty: int,
        exit_reason: str,
        exit_price: float | None
    ):
        """
        DB-level finalization
        """

        trade_id = trade["id"]
        symbol = trade["symbol"]

        remaining_qty = trade["remaining_qty"]
        new_remaining = remaining_qty - exit_qty

        exit_price = exit_price or trade["ltp"]

        # -----------------------------------------
        # Record broker trade
        # -----------------------------------------
        self.broker_trade_repo.insert({
            "trade_id": trade_id,
            "symbol": symbol,
            "side": "EXIT",
            "qty": exit_qty,
            "price": exit_price,
            "exit_reason": exit_reason,
            "timestamp": datetime.now().isoformat()
        })

        # -----------------------------------------
        # Update trade quantities
        # -----------------------------------------
        self.trade_repo.update_remaining_qty(
            trade_id,
            new_remaining
        )

        # -----------------------------------------
        # Partial Exit
        # -----------------------------------------
        if new_remaining > 0:
            self.trade_repo.mark_partial_exit(
                trade_id,
                exit_reason,
                exit_price
            )

            logger.info(
                f"🟡 PARTIAL EXIT | {symbol} | Qty={exit_qty} | Rem={new_remaining}"
            )
            return

        # -----------------------------------------
        # Full Exit
        # -----------------------------------------
        self.trade_repo.close_and_archive(
            trade,
            exit_price,
            exit_reason
        )

        logger.info(
            f"🔴 FINAL EXIT | {symbol} | Reason={exit_reason}"
        )
