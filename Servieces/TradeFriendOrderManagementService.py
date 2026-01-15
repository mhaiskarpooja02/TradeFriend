import logging
from db.TradeFriendOrderAuditRepo import TradeFriendOrderAuditRepo
from db.TradeFriendOrderConfigRepo import TradeFriendOrderConfigRepo

from brokers.tradefriend_dhan_order_adapter import TradeFriendDhanOrderAdapter
from brokers.tradefriend_angel_order_adapter import TradeFriendAngelOrderAdapter

logger = logging.getLogger(__name__)


class TradeFriendOrderManagementService:
    """
    PURPOSE:
    - Central OMS router
    - Reads broker behavior from DB
    - Sends orders to eligible brokers
    """

    def __init__(self):
        self.config_repo = TradeFriendOrderConfigRepo()

        # Initialize adapters (safe even if disabled)
        self.dhan = TradeFriendDhanOrderAdapter()
        self.angel = TradeFriendAngelOrderAdapter()
        self.audit_repo = TradeFriendOrderAuditRepo()

    # --------------------------------------------------
    # PUBLIC API
    # --------------------------------------------------
    def process_trade(self, trade_id, symbol, qty, side):
        cfg = self.config.get()
        mode = cfg["order_mode"]

        # -------- AUDIT: ATTEMPT --------
        audit_id = self.audit_repo.log_attempt(
            trade_id=trade_id,
            symbol=symbol,
            broker="OMS",
            order_mode=mode,
            side=side,
            qty=qty
        )

        # -------- PAPER MODE --------
        if mode == "PAPER":
            self.audit_repo.log_result(
                audit_id,
                status="SKIPPED",
                error="PAPER mode"
            )
            return True

        # -------- LIVE MODE --------
        results = []

        if cfg["angel_enabled"] and cfg["angel_auto_order"]:
            result = self.angel.place_order(symbol, qty, side)
            results.append(("ANGEL", result))

        if cfg["dhan_enabled"] and cfg["dhan_auto_order"]:
            result = self.dhan.place_order(symbol, qty, side)
            results.append(("DHAN", result))

        success = any(r[1] for r in results)

        self.audit_repo.log_result(
            audit_id,
            status="SUCCESS" if success else "FAILED"
        )

        return success
    
    # --------------------------------------------------
    # INTERNAL ROUTERS
    # --------------------------------------------------
    def _try_dhan(self, order, cfg) -> bool:
        if not (cfg["dhan_enabled"] and cfg["dhan_auto_order"]):
            return False

        max_qty = cfg.get("dhan_max_qty")
        if max_qty:
            order["qty"] = min(order["qty"], max_qty)

        return self.dhan.place_order(order)

    def _try_angel(self, order, cfg) -> bool:
        if not (cfg["angel_enabled"] and cfg["angel_auto_order"]):
            return False

        max_qty = cfg.get("angel_max_qty")
        if max_qty:
            order["qty"] = min(order["qty"], max_qty)

        return self.angel.place_order(order)
