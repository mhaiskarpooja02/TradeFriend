# core/TradeFriendSwingTradeMonitor.py

from utils.logger import get_logger
from core.TradeFriendDataProvider import TradeFriendDataProvider
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from Servieces.TradeFriendExitOrderService import TradeFriendExitOrderService
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
    PURPOSE:
    - Monitor OPEN / PARTIAL swing trades
    - Detect exit conditions
    - Delegate execution & finalization to Exit OMS
    """

    def __init__(self):
        self.provider = TradeFriendDataProvider()
        self.trade_repo = TradeFriendTradeRepo()
        self.exit_oms = TradeFriendExitOrderService()

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
                logger.exception(
                    f"SwingTradeMonitor failed for {trade['symbol']}: {e}"
                )

    # ==================================================
    # PROCESS SINGLE TRADE
    # ==================================================
    def _process_trade(self, trade: dict):
        symbol = trade["symbol"]
        entry = float(trade["entry"])
        sl = float(trade["sl"])
        target = float(trade["target"])
        remaining_qty = trade["qty"]
       
        trailing_sl = float(trade["trailing_sl"] or sl)
        hold_mode = int(trade["hold_mode"] or 0)

        if remaining_qty <= 0:
           logger.warning(f"{symbol} → No remaining qty, skipping")
           return

        ltp = self.provider.get_ltp_byLtp(symbol)
        if ltp is None:
            logger.warning(f"{symbol} → LTP not available")
            return

        risk = entry - sl

        # ==================================================
        # 1️⃣ EMERGENCY HARD EXIT
        # ==================================================
        if ltp <= entry - (risk * HARD_EXIT_R_MULTIPLE):
            self._exit(trade, "EMERGENCY_EXIT", remaining_qty, ltp)
            return

        # ==================================================
        # 2️⃣ STOP LOSS LOGIC
        # ==================================================
        active_sl = max(sl, trailing_sl)
        sl_buffer_price = active_sl * (1 + SL_BUFFER_PCT)

        if ltp <= active_sl:
            self._exit(trade, "SL_HIT", remaining_qty, ltp)
            return

        if ltp <= sl_buffer_price:
            self._exit(trade, "SL_BUFFER_EXIT", remaining_qty, ltp)
            return

        # ==================================================
        # 3️⃣ PARTIAL PROFIT @ 1R
        # ==================================================
        if ENABLE_PARTIAL_BOOKING and hold_mode == 0:
            one_r_price = entry + (risk * PARTIAL_BOOK_RR)

             # 🎯 TARGET HIT → FULL EXIT (no partial)
            if ltp >= target:
                if remaining_qty > 0:
                    self._exit(trade, "TARGET_HIT", remaining_qty, ltp)
                return

            if ltp >= one_r_price:
                partial_qty = remaining_qty // 2
                if partial_qty > 0:
                    self._exit(trade, "PARTIAL_EXIT", partial_qty, ltp)
                return

        # ==================================================
        # 4️⃣ TRAILING SL (AFTER PARTIAL)
        # ==================================================
        if hold_mode == 1:
            atr = self.provider.get_atr(symbol, period=14)
            if atr:
                new_trailing_sl = ltp - (atr * TRAIL_ATR_MULTIPLE)
                if new_trailing_sl > trailing_sl:
                    self.trade_repo.update_sl(trade["id"], new_trailing_sl)

        # ==================================================
        # 5️⃣ FINAL TARGET
        # ==================================================
        if ltp >= target:

            logger.info(f"🔍 MONITOR | {trade['symbol']} | "f"LTP={ltp} | SL={trade['sl']} | TARGET={trade['target']} | " f"STATUS={trade['status']} | REM_QTY={trade['remaining_qty']}")
            self._exit(trade, "TARGET_HIT", remaining_qty, ltp)

    # ==================================================
    # SINGLE EXIT GATE (DELEGATE ONLY)
    # ==================================================
    def _exit(self, trade: dict, reason: str, qty: int, price: float):
        symbol = trade["symbol"]
        
        # if not self.provider.is_market_open():
        #     self.trade_repo.mark_exit_pending(trade["id"], reason)
        #     logger.warning(f"{symbol} → Exit deferred (market closed)")
        #     return

        # logger.info(
        #     f"🚪 EXIT SIGNAL | {symbol} | Reason={reason} | Qty={qty}"
        # )

        
        self.exit_oms.place_exit_order(
            trade_id=trade["id"],
            symbol=symbol,
            exit_qty=qty,
            exit_reason=reason,
            exit_price=price
        )
