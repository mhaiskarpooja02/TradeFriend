import logging
import time
from core.TradeFriendDataProvider import TradeFriendDataProvider
from db.TradeFriendDatabase import TradeFriendDatabase
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from strategy.TradeFriendScanner import TradeFriendScanner
from db.tradefindinstrument_db import TradeFindDB
from db.TradeFriendWatchlistRepo import TradeFriendWatchlistRepo
from config.TradeFriendConfig import REQUEST_DELAY_SEC, ERROR_COOLDOWN_SEC
from strategy.TradeFriendSwingEntryPlanner import TradeFriendSwingEntryPlanner
from db.TradeFriendSwingPlanRepo import TradeFriendSwingPlanRepo
from utils.logger import get_logger


logger = get_logger(__name__)


class WatchlistEngine:
    """
    PURPOSE:
    - Daily scan
    - Populate watchlist
    - Create swing plans
    """

    def __init__(self):
        self.instrument_db = TradeFindDB()
        self.provider = TradeFriendDataProvider()

        self.watchlist_repo = TradeFriendWatchlistRepo()
        self.swing_plan_repo = TradeFriendSwingPlanRepo()
        self.trade_repo = TradeFriendTradeRepo()

    def run(self):
        logger.info("📊 Daily Watchlist Scan started")

        watchlist_symbols = self.watchlist_repo.get_all_symbols()
        trade_symbols = self.trade_repo.get_all_symbols()

        # ✅ CLEANUP: stale & never-triggered watchlist entries
        self.watchlist_repo.delete_untriggered_older_than(days=7)
        self.swing_plan_repo.delete_orphan_plans()


        symbols = self.instrument_db.get_active()
        if not symbols:
            logger.warning("No active symbols found")
            return

        for row in symbols:
            symbol = row["symbol"]
             # ⛔ SKIP if already in Watchlist
            if symbol in watchlist_symbols:
                logger.info(f"{symbol} → Skipped (already in watchlist)")
                continue
            
            # ⛔ SKIP if already traded
            if symbol in trade_symbols:
                logger.info(f"{symbol} → Skipped (already traded)")
                continue


            logger.info(f"Processing {symbol}")

            try:
                df = self.provider.get_daily_data(
                    trading_symbol=row["trading_symbol"],
                    token=row["token"]
                )

                if df is None or df.empty:
                    logger.warning(f"{symbol} → No data")
                    continue

                scanner = TradeFriendScanner(df, symbol)
                signal = scanner.scan()

                if not signal:
                    logger.info(f"{symbol} → No setup")
                    time.sleep(REQUEST_DELAY_SEC)
                    continue

                # Save watchlist
                self.watchlist_repo.upsert(signal)

                # Build swing plan
                planner = TradeFriendSwingEntryPlanner(
                    df=df,
                    symbol=signal["symbol"],
                    strategy=signal["strategy"]
                )

                plan = planner.build_plan()
                if plan:
                    self.swing_plan_repo.save_plan(plan)

                logger.info(f"{symbol} → Watchlist + Plan saved")

                time.sleep(REQUEST_DELAY_SEC)

            except Exception as e:
                logger.exception(f"{symbol} failed: {e}")
                time.sleep(ERROR_COOLDOWN_SEC)

        logger.info("✅ Daily Watchlist Scan completed")