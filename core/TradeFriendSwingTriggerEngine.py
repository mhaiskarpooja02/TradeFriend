# core/TradeFriendSwingTriggerEngine.py

from datetime import date
from utils.logger import get_logger
from core.TradeFriendDataProvider import TradeFriendDataProvider
from Servieces.TradeFriendOrderManagementService import TradeFriendOrderManagementService
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from db.TradeFriendSwingPlanRepo import TradeFriendSwingPlanRepo
from brokers.dhan_client import DhanClient
from config.TradeFriendConfig import (
    ENTRY_TOLERANCE,
    PARTIAL_ENTRY_ENABLED,
    PARTIAL_ENTRY_QTY,
    PAPER_TRADE
)

logger = get_logger(__name__)


class TradeFriendSwingTriggerEngine:
    """
    PHASE-2 PURPOSE:
    - Monitor READY trades during market hours
    - Trigger entries ONLY when LTP >= entry and within tolerance
    - Supports partial entry
    - OMS owns execution (paper / live)
    """

    def __init__(self, capital: float, paper_trade: bool = PAPER_TRADE):
        self.capital = capital
        self.paper_trade = paper_trade

        self.provider = TradeFriendDataProvider()
        self.trade_repo = TradeFriendTradeRepo()
        self.plan_repo = TradeFriendSwingPlanRepo()

        self.oms = TradeFriendOrderManagementService()
        self.broker = None if paper_trade else DhanClient()

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
                    f"Trigger failed for {trade.get('symbol')}: {e}"
                )

        logger.info("✅ Swing Trigger Engine completed")

    # =====================================================
    # PROCESS SINGLE TRADE
    # =====================================================
    def _process_trade(self, trade: dict):
        trade_id = trade["id"]
        symbol = trade["symbol"]
        entry = float(trade["entry"])
        sl = float(trade["sl"])
        target = float(trade["target"])

        planned_qty = int(trade["qty"])              # ← from DecisionEngine
        filled_qty = int(trade.get("filled_qty") or 0)

        logger.info(
            f"⏳ Monitoring ENTRY | {symbol} | "
            f"Filled={filled_qty}/{planned_qty}"
        )

        # -------------------------------
        # FETCH LTP
        # -------------------------------
        ltp = self.provider.get_ltp(symbol)
        if ltp is None or ltp <= 0:
            logger.warning(f"{symbol} → Invalid LTP")
            return

        # -------------------------------
        # STRICT ENTRY VALIDATION
        # -------------------------------
        tolerance_price = entry * ENTRY_TOLERANCE

        # ❌ Never enter below entry
        if ltp < entry:
            logger.info(
                f"{symbol} → LTP below entry "
                f"({ltp} < {entry})"
            )
            return

        # ❌ Missed entry (price jumped too far)
        if ltp > entry + tolerance_price:
            logger.warning(
                f"{symbol} → Missed entry | LTP={ltp}"
            )
            self.trade_repo.invalidate_trade(
                trade_id,
                f"Missed entry | LTP={ltp}"
            )
            return

        logger.info(
            f"🚀 ENTRY WINDOW HIT | {symbol} | LTP={ltp}"
        )

        # -------------------------------
        # DETERMINE QTY TO PLACE
        # -------------------------------
        remaining_qty = planned_qty - filled_qty
        if remaining_qty <= 0:
            return

        if PARTIAL_ENTRY_ENABLED and filled_qty == 0:
            qty_to_place = min(PARTIAL_ENTRY_QTY, remaining_qty)
        else:
            qty_to_place = remaining_qty

        # -------------------------------
        # PLACE ORDER VIA OMS
        # -------------------------------
        order = self.oms.place_entry_order(
            trade_id=trade_id,
            symbol=symbol,
            qty=qty_to_place,
            side="BUY",
            price=ltp,
            broker=self.broker
        )

        if not order:
            logger.warning(f"{symbol} → OMS rejected order")
            return

        # -------------------------------
        # UPDATE FILL STATE
        # -------------------------------
        self.trade_repo.update_entry_fill(
            trade_id=trade_id,
            fill_qty=order["filled_qty"],
            fill_price=order["avg_price"]
        )

        new_filled_qty = filled_qty + order["filled_qty"]

        # -------------------------------
        # FULLY FILLED
        # -------------------------------
        if new_filled_qty >= planned_qty:
            self.trade_repo.mark_open(
                trade_id=trade_id,
                avg_entry=order["avg_price"],
                entry_day=date.today().isoformat()
            )

            self.plan_repo.mark_triggered_by_trade(trade_id)

            logger.info(
                f"✅ ENTRY COMPLETE | {symbol} | "
                f"Qty={new_filled_qty}"
            )

        else:
            logger.info(
                f"➗ PARTIAL ENTRY | {symbol} | "
                f"{new_filled_qty}/{planned_qty}"
            )
