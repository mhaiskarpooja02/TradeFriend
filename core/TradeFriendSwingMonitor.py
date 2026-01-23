# core/TradeFriendSwingTradeMonitor.py

import logging
from datetime import date

from utils.logger import get_logger
from core.TradeFriendDataProvider import TradeFriendDataProvider
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from Servieces.TradeFriendOrderManagementService import TradeFriendOrderManagementService
from config.TradeFriendConfig import (
    ENABLE_PARTIAL_BOOKING,
    PARTIAL_BOOK_RR,
    SL_BUFFER_PCT,
    HARD_EXIT_R_MULTIPLE,
    TRAIL_ATR_MULTIPLE
)

logger = get_logger(__name__)


class TradeFriendSwingTradeMonitor:
    """
    Monitor swing trades:
    - Exit logic: Emergency, SL, Soft SL, Partial, Target
    - Trailing SL
    - OMS execution (paper/live)
    - Wait-based exit if market closed
    """

    def __init__(self, paper_trade=True):
        self.paper_trade = paper_trade
        self.provider = TradeFriendDataProvider()
        self.trade_repo = TradeFriendTradeRepo()
        self.oms = TradeFriendOrderManagementService()

    # ==================================================
    # PUBLIC ENTRY
    # ==================================================
    def run(self):
        open_trades = self.trade_repo.fetch_open_trades()
        if not open_trades:
            return

        for trade in open_trades:
            try:
                self._process_trade(trade)
            except Exception as e:
                logger.exception(f"Trade monitor failed for {trade['symbol']}: {e}")

    # ==================================================
    # SINGLE EXIT GATE
    # ==================================================
    def _finalize_trade(self, trade, reason, ltp=None):
        symbol = trade["symbol"]

        if ltp is None:
            ltp = self.provider.get_ltp_byLtp(symbol)

        # Check market open
        if not self.provider.is_market_open():
            self.trade_repo.mark_exit_pending(trade["id"], reason)
            logger.warning(f"{symbol} → Exit deferred (market closed)")
            return

        # Decide execution type
        order_type, price = self._decide_exit_execution(reason, ltp)

        # Place order via OMS
        order = self.oms.place_exit_order(
            trade_id=trade["id"],
            symbol=symbol,
            qty=trade["qty"],
            side="SELL",
            order_type=order_type,
            price=price,
            broker=None if self.paper_trade else self.oms.get_broker()
        )

        if not order:
            logger.error(f"{symbol} → Exit order failed")
            return

        self.trade_repo.close_and_archive(
            trade_row=trade,
            exit_price=order["avg_price"],
            exit_reason=reason
        )

        logger.info(f"✅ Trade CLOSED | {symbol} | Reason={reason}")

    # ==================================================
    # PROCESS SINGLE TRADE
    # ==================================================
    def _process_trade(self, trade):
        symbol = trade["symbol"]
        entry = float(trade["entry"])
        sl = float(trade["sl"])
        target = float(trade["target"])
        qty = int(trade["qty"])
        status = trade["status"]

        trailing_sl = float(trade["trailing_sl"]) if trade["trailing_sl"] else sl
        hold_mode = int(trade["hold_mode"] or 0)

        ltp = self.provider.get_ltp_byLtp(symbol)
        if ltp is None:
            logger.warning(f"{symbol} → LTP not available")
            return

        risk = entry - sl

        # 1️⃣ EMERGENCY HARD EXIT
        if ltp <= entry - (risk * HARD_EXIT_R_MULTIPLE):
            logger.warning(f"{symbol} → EMERGENCY EXIT")
            self._finalize_trade(trade, "EMERGENCY_EXIT", ltp)
            return

        # 2️⃣ STOP LOSS LOGIC
        active_sl = max(sl, trailing_sl)
        sl_buffer_price = active_sl * (1 + SL_BUFFER_PCT)

        if ltp <= active_sl:
            logger.info(f"{symbol} → HARD SL HIT | ltp={ltp} | sl={active_sl}")
            self._finalize_trade(trade, "SL_HIT", ltp)
            return

        if ltp <= sl_buffer_price:
            logger.warning(f"{symbol} → SOFT SL EXIT | ltp={ltp} | buffer_sl={sl_buffer_price}")
            self._finalize_trade(trade, "SL_BUFFER_EXIT", ltp)
            return

        # 3️⃣ PARTIAL PROFIT @ 1R
        if ENABLE_PARTIAL_BOOKING and status == "OPEN":
            one_r_price = entry + (risk * PARTIAL_BOOK_RR)
            if ltp >= one_r_price:
                partial_qty = qty // 2
                if partial_qty > 0:
                    logger.info(f"{symbol} → Partial booking @ {one_r_price}")
                    self.trade_repo.partial_exit(trade["id"], partial_qty)
                    self.trade_repo.enable_hold_mode(trade["id"])
                return

        # 4️⃣ TRAILING SL (AFTER PARTIAL)
        if hold_mode == 1:
            atr = self.provider.get_atr(symbol, period=14)
            if atr:
                new_trailing_sl = ltp - (atr * TRAIL_ATR_MULTIPLE)
                if new_trailing_sl > trailing_sl:
                    logger.info(f"{symbol} → Trail SL to {new_trailing_sl}")
                    self.trade_repo.update_sl(trade["id"], new_trailing_sl)

        # 5️⃣ FINAL TARGET
        if ltp >= target:
            logger.info(f"{symbol} → TARGET HIT")
            self._finalize_trade(trade, "TARGET_HIT", ltp)
            return

    # ==================================================
    # DECIDE EXIT EXECUTION TYPE
    # ==================================================
    def _decide_exit_execution(self, reason, ltp):
        if reason in ("EMERGENCY_EXIT", "SL_HIT", "SL_BUFFER_EXIT"):
            return "MARKET", None
        if reason in ("TARGET_HIT", "PARTIAL_EXIT"):
            return "LIMIT", ltp
        return "MARKET", None
