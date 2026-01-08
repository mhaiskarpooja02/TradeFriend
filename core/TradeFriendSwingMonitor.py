import logging
from datetime import date
from utils.logger import get_logger
from core.TradeFriendDataProvider import TradeFriendDataProvider
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from config.TradeFriendConfig import (
    PAPER_TRADE,
    ENABLE_PARTIAL_BOOKING,
    PARTIAL_BOOK_RR,
    SL_ON_CLOSE,
    HARD_EXIT_R_MULTIPLE,
    TRAIL_ATR_MULTIPLE
)

logger = get_logger(__name__)


class TradeFriendSwingTradeMonitor:
    """
    PURPOSE:
    - Monitor OPEN / PARTIAL swing trades
    - Handle SL / Partial / Target / Emergency
    - Single terminal exit gate
    """

    def __init__(self, paper_trade=True):
        self.paper_trade = PAPER_TRADE
        self.provider = TradeFriendDataProvider()
        self.trade_repo = TradeFriendTradeRepo()

    # =====================================================
    # PUBLIC ENTRY
    # =====================================================
    def run(self):
        open_trades = self.trade_repo.fetch_open_trades()
        if not open_trades:
            return

        for trade in open_trades:
            try:
                self._process_trade(trade)
            except Exception as e:
                logger.exception(
                    f"Trade monitor failed for {trade['symbol']}: {e}"
                )

    # =====================================================
    # SINGLE EXIT GATE (VERY IMPORTANT)
    # =====================================================
    def _finalize_trade(self, trade, reason: str, exit_price: float | None = None):
        """
        Single exit point for ALL terminal trade outcomes
        """
        symbol = trade["symbol"]

        if exit_price is None:
            exit_price = self.provider.get_ltp(symbol)

        self.trade_repo.close_and_archive(
            trade=trade,
            exit_price=exit_price,
            exit_reason=reason
        )

        logger.info(f"✅ Trade CLOSED | {symbol} | Reason={reason}")

    # =====================================================
    # CORE LOGIC
    # =====================================================
    def _process_trade(self, trade):
        """
        trade is sqlite3.Row → access ONLY via trade["col"]
        """

        # -----------------------------
        # BASIC FIELDS
        # -----------------------------
        symbol = trade["symbol"]
        entry = float(trade["entry"])
        sl = float(trade["sl"])
        target = float(trade["target"])
        qty = int(trade["qty"])
        status = trade["status"]

        trailing_sl = float(trade["trailing_sl"]) if trade["trailing_sl"] else sl
        hold_mode = int(trade["hold_mode"] or 0)
        entry_day = trade["entry_day"]

        logger.info(f"📡 Monitoring {symbol} | Status={status} | Qty={qty}")

        # -----------------------------
        # FETCH LTP
        # -----------------------------
        ltp = self.provider.get_ltp(symbol)
        if ltp is None:
            logger.warning(f"{symbol} → LTP not available")
            return

        risk = entry - sl
        today = date.today().isoformat()

        # =================================================
        # 1️⃣ EMERGENCY HARD EXIT
        # =================================================
        if ltp <= entry - (risk * HARD_EXIT_R_MULTIPLE):
            logger.warning(f"{symbol} → EMERGENCY EXIT")
            self._finalize_trade(trade, "EMERGENCY_EXIT", ltp)
            return

        # =================================================
        # 2️⃣ STOP LOSS LOGIC
        # =================================================
        active_sl = max(sl, trailing_sl)

        if ltp <= active_sl:

            # Entry-day immediate SL
            if entry_day == today:
                logger.info(f"{symbol} → SL hit on entry day")
                self._finalize_trade(trade, "SL_HIT", ltp)
                return

            # Hold mode → SL on daily close
            if hold_mode == 1 and SL_ON_CLOSE:
                daily_close = self.provider.get_last_close(symbol)
                if daily_close is not None and daily_close < active_sl:
                    logger.info(f"{symbol} → SL on close")
                    self._finalize_trade(trade, "SL_CLOSE_BASED", daily_close)
                    return

            logger.info(f"{symbol} → SL HIT")
            self._finalize_trade(trade, "SL_HIT", ltp)
            return

        # =================================================
        # 3️⃣ PARTIAL PROFIT @ 1R
        # =================================================
        if ENABLE_PARTIAL_BOOKING and status == "OPEN":
            one_r_price = entry + (risk * PARTIAL_BOOK_RR)

            if ltp >= one_r_price:
                partial_qty = qty // 2
                if partial_qty > 0:
                    logger.info(f"{symbol} → Partial booking @ {one_r_price}")
                    self.trade_repo.partial_exit(trade["id"], partial_qty)
                    self.trade_repo.enable_hold_mode(trade["id"])
                return

        # =================================================
        # 4️⃣ TRAILING SL (AFTER PARTIAL)
        # =================================================
        if hold_mode == 1:
            atr = self.provider.get_atr(symbol, period=14)
            if atr:
                new_trailing_sl = ltp - (atr * TRAIL_ATR_MULTIPLE)
                if new_trailing_sl > trailing_sl:
                    logger.info(f"{symbol} → Trail SL to {new_trailing_sl}")
                    self.trade_repo.update_sl(trade["id"], new_trailing_sl)

        # =================================================
        # 5️⃣ FINAL TARGET
        # =================================================
        if ltp >= target:
            logger.info(f"{symbol} → TARGET HIT")
            self._finalize_trade(trade, "TARGET_HIT", ltp)
            return
