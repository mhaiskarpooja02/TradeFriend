import logging
from brokers.angel_client import init_client
from db.tradefindinstrument_db import TradeFindDB
from db.TradeFriendOrderAuditRepo import TradeFriendOrderAuditRepo

logger = logging.getLogger(__name__)


class TradeFriendAngelOrderAdapter:
    """
    PURPOSE:
    - Prepare OMS → Angel payload
    - Resolve token via TradeFindDB
    - Execute via AngelClient
    - Perform full order audit
    """

    BROKER_NAME = "ANGEL"

    EXCHANGE = "NSE"
    PRODUCT = "INTRADAY"
    VARIETY = "NORMAL"
    ORDER_TYPE = "MARKET"
    DURATION = "DAY"

    def __init__(self):
        self.client = init_client()  # ✅ reuse singleton
        self.instrument_repo = TradeFindDB()
        self.audit_repo = TradeFriendOrderAuditRepo()

    # --------------------------------------------------
    # PLACE ORDER (OMS ENTRY)
    # --------------------------------------------------
    def place_order(
        self,
        trade_id: int,
        symbol: str,
        qty: int,
        side: str = "BUY",
        order_mode: str = "LIVE"
    ) -> bool:

        if qty <= 0:
            logger.error(f"Invalid qty for {symbol}: {qty}")
            return False

        # --------------------------------------------------
        # RESOLVE SYMBOL → TOKEN
        # --------------------------------------------------
        resolved = self.instrument_repo.resolve_active_symbol(symbol)
        if not resolved:
            logger.error(f"Angel token not found for {symbol}")
            return False

        # --------------------------------------------------
        # PREPARE PAYLOAD
        # --------------------------------------------------
        payload = {
            "variety": self.VARIETY,
            "tradingsymbol": resolved["symbol"],
            "symboltoken": resolved["token"],
            "transactiontype": side,
            "exchange": self.EXCHANGE,
            "ordertype": self.ORDER_TYPE,
            "producttype": self.PRODUCT,
            "duration": self.DURATION,
            "price": 0,
            "quantity": qty,
        }

        # --------------------------------------------------
        # AUDIT → ATTEMPT
        # --------------------------------------------------
        audit_id = self.audit_repo.log_attempt(
            trade_id=trade_id,
            symbol=symbol,
            broker=self.BROKER_NAME,
            order_mode=order_mode,
            side=side,
            qty=qty,
            resolved_id=resolved["token"],
            exchange=self.EXCHANGE,
            product=self.PRODUCT,
            order_type=self.ORDER_TYPE,
            request_payload=payload
        )

        # --------------------------------------------------
        # EXECUTE
        # --------------------------------------------------
        try:
            order_id = self.client.place_order(payload)

            self.audit_repo.log_result(
                audit_id=audit_id,
                status="SUCCESS",
                broker_order_id=order_id,
                response_payload={"order_id": order_id}
            )

            logger.info(
                f"✅ ANGEL ORDER | {symbol} | Qty={qty} | OrderID={order_id}"
            )
            return True

        except Exception as e:
            self.audit_repo.log_result(
                audit_id=audit_id,
                status="FAILED",
                error_message=str(e)
            )

            logger.exception(f"❌ ANGEL ORDER FAILED | {symbol}")
            return False
