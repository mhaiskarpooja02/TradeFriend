# Servieces/TradeFriendOrderManagementService.py

from utils.logger import get_logger
from db.TradeFriendBrokerTradeRepo import TradeFriendBrokerTradeRepo
from config.TradeFriendConfig import PAPER_TRADE

from brokers.tradefriend_dhan_order_adapter import TradeFriendDhanOrderAdapter
from brokers.tradefriend_angel_order_adapter import TradeFriendAngelOrderAdapter

logger = get_logger(__name__)


class TradeFriendOrderManagementService:
    """
    PURPOSE:
    - Execute entry orders via brokers
    - Maintain broker_trade lifecycle
    - Multi-broker, retry-safe, audit-perfect
    """

    def __init__(self):
        self.repo = TradeFriendBrokerTradeRepo()

        # Broker adapters
        self.dhan = TradeFriendDhanOrderAdapter()
        self.angel = TradeFriendAngelOrderAdapter()

    # =====================================================
    # ENTRY EXECUTION
    # =====================================================
    def place_entry_order(
        self,
        trade_id: int,
        symbol: str,
        qty: int,
        side: str,
        price: float
    ) -> list[dict]:
        """
        RETURNS: list of executions
        [
            {
                broker,
                filled_qty,
                avg_price,
                broker_order_id
            }
        ]
        """

        executions = []

        # PAPER MODE → SIMULATE SINGLE BROKER
        if PAPER_TRADE:
            broker_trade_id = self.repo.log_attempt(
                trade_id=trade_id,
                broker="PAPER",
                order_mode="PAPER",
                symbol=symbol,
                side=side,
                qty=qty,
                order_type="MARKET",
                request_payload={
                    "symbol": symbol,
                    "qty": qty,
                    "side": side,
                    "price": price
                }
            )

            self.repo.log_success(
                broker_trade_id=broker_trade_id,
                broker_order_id=f"PAPER-{broker_trade_id}",
                response_payload={
                    "filled_qty": qty,
                    "avg_price": price
                }
            )

            executions.append({
                "broker": "PAPER",
                "filled_qty": qty,
                "avg_price": price,
                "broker_order_id": f"PAPER-{broker_trade_id}"
            })

            return executions

        # LIVE MODE → MULTI BROKER
        executions += self._try_angel(trade_id, symbol, qty, side)
        executions += self._try_dhan(trade_id, symbol, qty, side)

        return executions

    # =====================================================
    # BROKER ROUTERS
    # =====================================================
    def _try_angel(self, trade_id, symbol, qty, side):
        executions = []

        if not self.angel.is_enabled():
            return executions

        broker_trade_id = self.repo.log_attempt(
            trade_id=trade_id,
            broker="ANGEL",
            order_mode="LIVE",
            symbol=symbol,
            side=side,
            qty=qty,
            order_type="MARKET"
        )

        try:
            order = self.angel.place_order(symbol, qty, side)
            if not order or not order.get("order_id"):
                raise Exception("Angel rejected order")

            fill = self.angel.wait_for_fill(order["order_id"])

            self.repo.log_success(
                broker_trade_id,
                broker_order_id=order["order_id"],
                response_payload=fill
            )

            executions.append({
                "broker": "ANGEL",
                "filled_qty": fill["filled_qty"],
                "avg_price": fill["avg_price"],
                "broker_order_id": order["order_id"]
            })

        except Exception as e:
            self.repo.log_failure(broker_trade_id, str(e))

        return executions

    def _try_dhan(self, trade_id, symbol, qty, side):
        executions = []

        if not self.dhan.is_enabled():
            return executions

        broker_trade_id = self.repo.log_attempt(
            trade_id=trade_id,
            broker="DHAN",
            order_mode="LIVE",
            symbol=symbol,
            side=side,
            qty=qty,
            order_type="MARKET"
        )

        try:
            order = self.dhan.place_order(symbol, qty, side)
            if not order or not order.get("order_id"):
                raise Exception("Dhan rejected order")

            fill = self.dhan.wait_for_fill(order["order_id"])

            self.repo.log_success(
                broker_trade_id,
                broker_order_id=order["order_id"],
                response_payload=fill
            )

            executions.append({
                "broker": "DHAN",
                "filled_qty": fill["filled_qty"],
                "avg_price": fill["avg_price"],
                "broker_order_id": order["order_id"]
            })

        except Exception as e:
            self.repo.log_failure(broker_trade_id, str(e))

        return executions
