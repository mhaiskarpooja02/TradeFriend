import logging
from utils.logger import get_logger
from core.TradeFriendDataProvider import TradeFriendDataProvider
from db.TradeFriendDatabase import TradeFriendDatabase
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from datetime import date
from config.TradeFriendConfig import (
    PAPER_TRADE,
    ENABLE_PARTIAL_BOOKING,
    PARTIAL_BOOK_RR,
    PARTIAL_BOOK_PERCENT,
    SL_ON_CLOSE,
    PARTIAL_BOOK_RR,
    HARD_EXIT_R_MULTIPLE,
    TRAIL_ATR_MULTIPLE
)

logger = get_logger(__name__)


class TradeFriendSwingTradeMonitor:
    """
    PURPOSE:
    - Monitor OPEN swing trades
    - Handle SL / Partial / Target
    - Paper mode only
    """

    def __init__(self, paper_trade=True):
        self.paper_trade = PAPER_TRADE


        # 🔌 Shared infra
        self.provider = TradeFriendDataProvider()
        self.db = TradeFriendDatabase()
        self.trade_repo = TradeFriendTradeRepo()

    def run(self):
        """
        Called every X minutes during market hours
        """
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

    # -------------------------------------------------
    # CORE TRADE MANAGEMENT LOGIC
    # -------------------------------------------------
    def _process_trade(self, trade):
        """
        trade is sqlite3.Row (NOT dict)
        Access ONLY using trade["column"]
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
    
        trailing_sl = float(trade["trailing_sl"]) if trade["trailing_sl"] is not None else sl
        hold_mode = int(trade["hold_mode"]) if trade["hold_mode"] is not None else 0
        entry_day = trade["entry_day"]
    
        logger.info(f"📡 Monitoring {symbol} | Status={status} | Qty={qty}")
    
        # -----------------------------
        # 1️⃣ FETCH LTP
        # -----------------------------
        ltp = self.provider.get_ltp(symbol)
        if ltp is None:
            logger.warning(f"{symbol} → LTP not available")
            return
    
        risk = entry - sl
        today = date.today().isoformat()
    
        # -----------------------------
        # 2️⃣ EMERGENCY HARD EXIT
        # -----------------------------
        if ltp <= entry - (risk * HARD_EXIT_R_MULTIPLE):
            logger.warning(f"{symbol} → EMERGENCY EXIT")
            self.trade_repo.close_trade(trade["id"], "EMERGENCY_EXIT")
            return
    
        # -----------------------------
        # 3️⃣ STOP LOSS LOGIC
        # -----------------------------
        active_sl = max(sl, trailing_sl)
    
        if ltp <= active_sl:
        
            # ENTRY DAY → IMMEDIATE SL
            if entry_day == today:
                logger.info(f"{symbol} → SL hit on entry day")
                self.trade_repo.close_trade(trade["id"], "SL_HIT")
                return
    
            # HOLD MODE → DAILY CLOSE SL
            if hold_mode == 1 and SL_ON_CLOSE:
                daily_close = self.provider.get_last_close(symbol)
                if daily_close is not None and daily_close < active_sl:
                    logger.info(f"{symbol} → SL on close")
                    self.trade_repo.close_trade(trade["id"], "SL_CLOSE_BASED")
                return
    
            logger.info(f"{symbol} → SL HIT")
            self.trade_repo.close_trade(trade["id"], "SL_HIT")
            return
    
        # -----------------------------
        # 4️⃣ PARTIAL PROFIT @ 1R
        # -----------------------------
        one_r_price = entry + (risk * PARTIAL_BOOK_RR)
    
        if status == "OPEN" and ltp >= one_r_price:
            partial_qty = qty // 2
    
            if partial_qty > 0:
                logger.info(f"{symbol} → Partial booking @ {one_r_price}")
                self.trade_repo.partial_exit(
                    trade_id=trade["id"],
                    exit_qty=partial_qty
                )
                self.trade_repo.enable_hold_mode(trade["id"])
            return
    
        # -----------------------------
        # 5️⃣ TRAILING SL (AFTER PARTIAL)
        # -----------------------------
        if hold_mode == 1:
            atr = self.provider.get_atr(symbol, period=14)
            if atr:
                new_trailing_sl = ltp - (atr * TRAIL_ATR_MULTIPLE)
    
                if new_trailing_sl > trailing_sl:
                    logger.info(f"{symbol} → Trail SL to {new_trailing_sl}")
                    self.trade_repo.update_sl(
                        trade_id=trade["id"],
                        new_sl=new_trailing_sl
                    )
    
        # -----------------------------
        # 6️⃣ FINAL TARGET
        # -----------------------------
        if ltp >= target:
            logger.info(f"{symbol} → TARGET HIT")
            self.trade_repo.close_trade(trade["id"], "TARGET_HIT")
            return