# Servieces/TradeFriendExitOrderService.py

import logging
from datetime import datetime

from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from db.TradeFriendTradeHistoryRepo import TradeFriendTradeHistoryRepo
from db.TradeFriendBrokerTradeRepo import TradeFriendBrokerTradeRepo
from db.TradeFriendOrderAuditRepo import TradeFriendOrderAuditRepo
from db.TradeFriendOrderConfigRepo import TradeFriendOrderConfigRepo

from brokers.tradefriend_dhan_order_adapter import TradeFriendDhanOrderAdapter
from brokers.tradefriend_angel_order_adapter import TradeFriendAngelOrderAdapter

logger = logging.getLogger(__name__)


class TradeFriendExitOrderService:
    """
    EXIT OMS
    --------
    - Validates trade
    - Executes PARTIAL / FINAL exit
    - Broker-agnostic
    - PAPER / LIVE aware
    - History-safe (always archives)
    """

    def __init__(self):
        self.trade_repo = TradeFriendTradeRepo()
        self.history_repo = TradeFriendTradeHistoryRepo()
        self.broker_trade_repo = TradeFriendBrokerTradeRepo()
        self.audit_repo = TradeFriendOrderAuditRepo()
        self.config_repo = TradeFriendOrderConfigRepo()

        self.brokers = {
            "DHAN": TradeFriendDhanOrderAdapter(),
            "ANGEL": TradeFriendAngelOrderAdapter()
        }

    # ==================================================
    # PUBLIC ENTRY
    # ==================================================
    def place_exit_order(
        self,
        trade_id: int,
        symbol: str,
        exit_qty: int,
        exit_reason: str,
        exit_price: float | None = None
    ) -> bool:

        logger.info(
            f"🚪 EXIT OMS | trade_id={trade_id} | symbol={symbol} | qty={exit_qty}"
        )

        # --------------------------------------------------
        # 1️⃣ FETCH & VALIDATE TRADE
        # --------------------------------------------------
        trade = self.trade_repo.fetch_by_id(trade_id)
        if not trade:
            logger.error(f"EXIT OMS → Trade not found: {trade_id}")
            return False

        if trade["symbol"] != symbol:
            logger.error(
                f"EXIT OMS → Symbol mismatch | DB={trade['symbol']} | REQ={symbol}"
            )
            return False

        remaining_qty = int(trade["remaining_qty"])
        if exit_qty <= 0 or exit_qty > remaining_qty:
            logger.error(
                f"{symbol} → Invalid exit qty {exit_qty} (remaining {remaining_qty})"
            )
            return False

        side = "SELL" if trade["side"] == "BUY" else "BUY"
        ltp = exit_price or trade.get("ltp")

        # --------------------------------------------------
        # 2️⃣ ORDER MODE
        # --------------------------------------------------
        cfg = self.config_repo.get()
        order_mode = cfg["order_mode"]

        audit_id = self.audit_repo.log_attempt(
            trade_id=trade_id,
            symbol=symbol,
            broker="EXIT_OMS",
            order_mode=order_mode,
            side=side,
            qty=exit_qty
        )

        # --------------------------------------------------
        # 3️⃣ PAPER MODE
        # --------------------------------------------------
        if order_mode == "PAPER":
            self._finalize_exit(trade, exit_qty, exit_reason, ltp)
            self.audit_repo.log_result(audit_id, status="SKIPPED", error_message="PAPER")
            return True

        # --------------------------------------------------
        # 4️⃣ LIVE MODE (BEST EFFORT)
        # --------------------------------------------------
        success = False
        broker_trades = self.broker_trade_repo.fetch_active_positions(trade_id)

        for bt in broker_trades or []:
            adapter = self.brokers.get(bt["broker"])
            if not adapter:
                continue

            result = adapter.place_order(
                symbol=symbol,
                qty=exit_qty,
                side=side
            )

            if result:
                success = True
                self.broker_trade_repo.insert_broker_trade(
                    trade_id=trade_id,
                    broker=bt["broker"],
                    symbol=symbol,
                    side="EXIT",
                    qty=exit_qty,
                    price=ltp,
                    broker_order_id=result.get("broker_order_id"),
                    active=False
                )
                break

        self.audit_repo.log_result(
            audit_id,
            status="SUCCESS" if success else "FAILED"
        )

        # --------------------------------------------------
        # 5️⃣ FINALIZE ALWAYS
        # --------------------------------------------------
        self._finalize_exit(trade, exit_qty, exit_reason, ltp)
        return True

    # ==================================================
    # INTERNAL FINALIZER
    # ==================================================
    def _finalize_exit(
        self,
        trade: dict,
        exit_qty: int,
        exit_reason: str,
        exit_price: float
    ):
        trade_id = trade["id"]
        symbol = trade["symbol"]

        remaining = trade["remaining_qty"]

        # ----------------------------
        # PARTIAL EXIT
        # ----------------------------
        if exit_qty < remaining:
            new_remaining = self.trade_repo.mark_partial_exit(
                trade_id,
                exit_qty,
                exit_price
            )

            logger.info(
                f"🟡 PARTIAL EXIT | {symbol} | Qty={exit_qty} | Remaining={new_remaining}"
            )
            return

        # ----------------------------
        # FINAL EXIT
        # ----------------------------
        self.trade_repo.close_and_archive(
            trade_id,
            exit_price,
            exit_reason
        )

        logger.info(
            f"🔴 FINAL EXIT | {symbol} | Reason={exit_reason}"
        )
