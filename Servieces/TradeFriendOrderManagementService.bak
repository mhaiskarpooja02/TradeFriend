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
    - Execute ENTRY orders only
    - Persist broker executions
    - Broker-agnostic, retry-safe
    - PnL-agnostic (IMPORTANT)
    """

    def __init__(self):
        self.repo = TradeFriendBrokerTradeRepo()
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
        RETURNS:
        [
            {
                broker,
                broker_trade_id,
                filled_qty,
                avg_price,
                broker_order_id
            }
        ]
        """

        executions: list[dict] = []

        # -------------------------------------------------
        # PAPER MODE
        # -------------------------------------------------
        if PAPER_TRADE:
            broker_trade_id = self.repo.insert_broker_trade(
                trade_id=trade_id,
                broker="PAPER",
                order_mode="PAPER",
                symbol=symbol,
                leg_type="ENTRY",
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

            self.repo.update_broker_trade_success(
                broker_trade_id=broker_trade_id,
                broker_order_id=f"PAPER-{broker_trade_id}",
                response_payload={
                    "filled_qty": qty,
                    "avg_price": price
                }
            )

            executions.append({
                "broker": "PAPER",
                "broker_trade_id": broker_trade_id,
                "filled_qty": qty,
                "avg_price": price,
                "broker_order_id": f"PAPER-{broker_trade_id}"
            })

            return executions

        # -------------------------------------------------
        # LIVE MODE
        # -------------------------------------------------
        executions += self._try_angel(trade_id, symbol, qty, side)
        executions += self._try_dhan(trade_id, symbol, qty, side)

        return executions

    # =====================================================
    # ANGEL ENTRY
    # =====================================================
    def _try_angel(self, trade_id, symbol, qty, side):
        executions = []

        if not self.angel.is_enabled():
            return executions

        broker_trade_id = self.repo.insert_broker_trade(
            trade_id=trade_id,
            broker="ANGEL",
            order_mode="LIVE",
            symbol=symbol,
            leg_type="ENTRY",
            side=side,
            qty=qty,
            order_type="MARKET"
        )

        try:
            order = self.angel.place_order(symbol, qty, side)
            if not order or not order.get("order_id"):
                raise Exception("Angel rejected order")

            fill = self.angel.wait_for_fill(order["order_id"])

            self.repo.update_broker_trade_success(
                broker_trade_id,
                broker_order_id=order["order_id"],
                response_payload=fill
            )

            executions.append({
                "broker": "ANGEL",
                "broker_trade_id": broker_trade_id,
                "filled_qty": fill["filled_qty"],
                "avg_price": fill["avg_price"],
                "broker_order_id": order["order_id"]
            })

        except Exception as e:
            self.repo.update_broker_trade_failure(
                broker_trade_id,
                str(e)
            )
            logger.error(f"[ANGEL ENTRY FAILED] {symbol} → {e}")

        return executions

    # =====================================================
    # DHAN ENTRY
    # =====================================================
    def _try_dhan(self, trade_id, symbol, qty, side):
        executions = []

        if not self.dhan.is_enabled():
            return executions

        broker_trade_id = self.repo.insert_broker_trade(
            trade_id=trade_id,
            broker="DHAN",
            order_mode="LIVE",
            symbol=symbol,
            leg_type="ENTRY",
            side=side,
            qty=qty,
            order_type="MARKET"
        )

        try:
            order = self.dhan.place_order(symbol, qty, side)
            if not order or not order.get("order_id"):
                raise Exception("Dhan rejected order")

            fill = self.dhan.wait_for_fill(order["order_id"])

            self.repo.update_broker_trade_success(
                broker_trade_id,
                broker_order_id=order["order_id"],
                response_payload=fill
            )

            executions.append({
                "broker": "DHAN",
                "broker_trade_id": broker_trade_id,
                "filled_qty": fill["filled_qty"],
                "avg_price": fill["avg_price"],
                "broker_order_id": order["order_id"]
            })

        except Exception as e:
            self.repo.update_broker_trade_failure(
                broker_trade_id,
                str(e)
            )
            logger.error(f"[DHAN ENTRY FAILED] {symbol} → {e}")

        return executions
