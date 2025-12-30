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
    HARD_EXIT_R_MULTIPLE
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
        self.trade_repo = TradeFriendTradeRepo(self.db)

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
        symbol = trade["symbol"]
        entry = float(trade["entry"])
        sl = float(trade["sl"])
        target = float(trade["target"])
        qty = int(trade["qty"])
        status = trade["status"]
        hold_mode = trade.get("hold_mode", 0)
        entry_day = trade.get("entry_day")

        # -----------------------------
        # 1️⃣ FETCH LTP
        # -----------------------------
        ltp = self.provider.get_ltp(symbol)
        if not ltp:
            return

        risk = entry - sl
        today = date.today().isoformat()

        # -----------------------------
        # 2️⃣ EMERGENCY HARD EXIT (gap / crash)
        # -----------------------------
        if ltp <= entry - (risk * HARD_EXIT_R_MULTIPLE):
            self.trade_repo.close_trade(
                trade_id=trade["id"],
                status="EMERGENCY_EXIT"
            )
            logger.warning(f" EMERGENCY EXIT | {symbol}")
            return

        # -----------------------------
        # 3️⃣ STOP LOSS LOGIC (swing-safe)
        # -----------------------------
        if ltp <= sl:

            # ENTRY DAY → always immediate SL
            if entry_day == today:
                self.trade_repo.close_trade(
                    trade_id=trade["id"],
                    status="SL_HIT"
                )
                logger.info(f" SL HIT (ENTRY DAY) | {symbol}")
                return

            # HOLD MODE → close-based SL
            if hold_mode == 1 and SL_ON_CLOSE:
                candle_close = self.provider.get_last_close(symbol)
                if candle_close < sl:
                    self.trade_repo.close_trade(
                        trade_id=trade["id"],
                        status="SL_CLOSE_BASED"
                    )
                    logger.info(f" SL ON CLOSE | {symbol}")
                return

            # Normal SL
            self.trade_repo.close_trade(
                trade_id=trade["id"],
                status="SL_HIT"
            )
            logger.info(f" SL HIT | {symbol}")
            return

        # -----------------------------
        # 4️⃣ PARTIAL PROFIT @ 1R
        # -----------------------------
        one_r_price = entry + (risk * PARTIAL_BOOK_RR)

        if status == "OPEN" and ltp >= one_r_price:
            partial_qty = qty // 2

            if partial_qty > 0:
                self.trade_repo.partial_exit(
                    trade_id=trade["id"],
                    exit_price=one_r_price,
                    exit_qty=partial_qty
                )

                # Enable swing hold mode after partial
                self.trade_repo.enable_hold_mode(trade["id"])

                logger.info(
                    f" PARTIAL BOOKED | {symbol} | "
                    f"{partial_qty} @ {one_r_price}"
                )
            return

        # -----------------------------
        # 5️⃣ FINAL TARGET
        # -----------------------------
        if ltp >= target:
            self.trade_repo.close_trade(
                trade_id=trade["id"],
                status="TARGET_HIT"
            )
            logger.info(f" TARGET HIT | {symbol}")
            return
