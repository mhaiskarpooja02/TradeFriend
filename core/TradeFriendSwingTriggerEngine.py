# core/TradeFriendSwingTriggerEngine.py

from datetime import date
from utils.logger import get_logger, get_order_logger
from core.TradeFriendDataProvider import TradeFriendDataProvider
from Servieces.TradeFriendOrderManagementService import TradeFriendOrderManagementService
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from db.TradeFriendSwingPlanRepo import TradeFriendSwingPlanRepo

from config.TradeFriendConfig import (
    ENTRY_TOLERANCE,
    PARTIAL_ENTRY_ENABLED,
    PARTIAL_ENTRY_QTY,
)

logger = get_logger(__name__)
order_logger = get_order_logger()


class TradeFriendSwingTriggerEngine:
    """
    PURPOSE:
    - Monitor READY swing trades
    - Validate strict entry window
    - Trigger entry via OMS (paper/live)
    - Persist broker-wise fills
    """

    def __init__(self, capital: float):
        self.capital = capital

        self.provider = TradeFriendDataProvider()
        self.trade_repo = TradeFriendTradeRepo()
        self.plan_repo = TradeFriendSwingPlanRepo()
        self.oms = TradeFriendOrderManagementService()

    # =====================================================
    # PUBLIC ENTRY
    # =====================================================
    def run(self):
        logger.info("📡 Swing Trigger Engine started")

        ready_trades = self.trade_repo.fetch_ready_trades()
        if not ready_trades:
            logger.info("No READY trades to monitor")
            return

        for trade in ready_trades:
            try:
                self._process_trade(dict(trade))
            except Exception as e:
                logger.exception(
                    f"Trigger failed | {trade.get('symbol')} | {e}"
                )

        logger.info("✅ Swing Trigger Engine completed")

    # =====================================================
    # PROCESS SINGLE TRADE
    # =====================================================
    def _process_trade(self, trade: dict):
        trade_id = trade["id"]
        symbol = trade["symbol"]

        entry = float(trade["entry"])
        planned_qty = int(trade["qty"])
        filled_qty = int(trade.get("filled_qty") or 0)

        logger.info(
            f"⏳ ENTRY MONITOR | {symbol} | "
            f"Filled={filled_qty}/{planned_qty}"
        )

        # -------------------------------
        # FETCH LTP
        # -------------------------------
        ltp = self.provider.get_ltp(symbol)
        if not ltp or ltp <= 0:
            logger.warning(f"{symbol} → Invalid LTP")
            return

        # -------------------------------
        # STRICT ENTRY VALIDATION
        # -------------------------------
        tolerance = entry * ENTRY_TOLERANCE

        if ltp < entry:
            logger.info(f"{symbol} → LTP below entry ({ltp} < {entry})")
            return

        if ltp > entry + tolerance:
            reason = f"Missed entry | LTP={ltp}"
            logger.warning(f"{symbol} → {reason}")
            self.trade_repo.invalidate_trade(trade_id, reason)
            return

        logger.info(f"🚀 ENTRY WINDOW HIT | {symbol} | LTP={ltp}")

        # -------------------------------
        # QTY DECISION
        # -------------------------------
        remaining_qty = planned_qty - filled_qty
        if remaining_qty <= 0:
            return

        if PARTIAL_ENTRY_ENABLED and filled_qty == 0:
            qty_to_place = min(PARTIAL_ENTRY_QTY, remaining_qty)
        else:
            qty_to_place = remaining_qty

        # -------------------------------
        # PLACE ENTRY VIA OMS
        # -------------------------------
        executions = self.oms.place_entry_order(
            trade_id=trade_id,
            symbol=symbol,
            qty=qty_to_place,
            side="BUY",
            price=ltp
        )

        if not executions:
            logger.warning(f"{symbol} → OMS rejected entry")
            return

        # -------------------------------
        # PROCESS EXECUTIONS
        # -------------------------------
        total_filled = 0
        weighted_price = 0.0

        for ex in executions:
            broker = ex["broker"]
            qty = ex["filled_qty"]
            price = ex["avg_price"]

            total_filled += qty
            weighted_price += qty * price

            # Persist broker ownership
            self.trade_repo.log_broker_entry(
                trade_id=trade_id,
                broker=broker,
                qty=qty,
                price=price,
                broker_order_id=ex["broker_order_id"]
            )

            order_logger.info(
                f"[ENTRY] {symbol} | {broker} | "
                f"qty={qty} | price={price}"
            )

        avg_price = round(weighted_price / total_filled, 2)

        # -------------------------------
        # UPDATE AGGREGATE TRADE STATE
        # -------------------------------
        self.trade_repo.update_entry_fill(
            trade_id=trade_id,
            fill_qty=total_filled,
            fill_price=avg_price
        )

        new_filled_qty = filled_qty + total_filled

        # -------------------------------
        # FULLY FILLED
        # -------------------------------
        if new_filled_qty >= planned_qty:
            self.trade_repo.mark_open(
                trade_id=trade_id,
                avg_entry=avg_price,
                entry_day=date.today().isoformat()
            )

            self.plan_repo.mark_triggered_by_trade(trade_id)

            logger.info(
                f"✅ ENTRY COMPLETE | {symbol} | "
                f"Qty={new_filled_qty}/{planned_qty}"
            )

        else:
            logger.info(
                f"➗ PARTIAL ENTRY | {symbol} | "
                f"{new_filled_qty}/{planned_qty}"
            )
