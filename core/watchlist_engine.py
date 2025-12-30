import logging
from core.TradeFriendDataProvider import TradeFriendDataProvider
from db.TradeFriendDatabase import TradeFriendDatabase
from strategy.TradeFriendScanner import TradeFriendScanner
from db.tradefindinstrument_db import TradeFindDB
from db.TradeFriendWatchlistRepo  import TradeFriendWatchlistRepo
from config.TradeFriendConfig import REQUEST_DELAY_SEC, ERROR_COOLDOWN_SEC
from strategy.TradeFriendSwingEntryPlanner import TradeFriendSwingEntryPlanner
from db.TradeFriendSwingPlanRepo import TradeFriendSwingPlanRepo
from utils.logger import get_logger
import time

logger = get_logger(__name__)

class WatchlistEngine:
    """
    PURPOSE:
    - Run daily after market close
    - Scan all active symbols
    - Store swing candidates into watchlist table
    """

    def run(self):
        logger.info(" Watchlist Engine started")

        db = TradeFindDB()
        symbols = db.get_active()

        tf_db = TradeFriendDatabase()
        swing_plan_repo = TradeFriendSwingPlanRepo(tf_db)
        
        if not symbols:
            logger.warning("No active symbols found")
            return

        provider = TradeFriendDataProvider()

        # ✅ DB OBJECT PASSED CORRECTLY
         # 2️⃣ WRITE TO tradefriend DB
        tf_db = TradeFriendDatabase()
        watchlist_repo = TradeFriendWatchlistRepo(tf_db)

        for row in symbols:
            symbol = row["symbol"]

            logger.info(f"Processing symbol: {symbol}")

            try:
                df = provider.get_daily_data(trading_symbol=row["trading_symbol"],token=row["token"])

                if df is None or df.empty:
                    logger.warning(f"{symbol} → No daily data")
                    continue

                logger.info(f"🔍 Scanner START | {symbol}")

                scanner = TradeFriendScanner(df, symbol)
                signal = scanner.scan()

                logger.info(f"🔍 Scanner END | {symbol} | signal={bool(signal)}")

                if signal:
                    watchlist_repo.upsert(signal)

                    planner = TradeFriendSwingEntryPlanner(
                        df=df,
                        symbol=signal["symbol"],
                        strategy=signal["strategy"]
                    )

                    plan = planner.build_plan()

                    if plan:
                        swing_plan_repo.save_plan(plan)


                logger.info(f"{symbol} → Added to watchlist ({signal['strategy']})")

                # ✅ NORMAL RATE LIMIT
                time.sleep(REQUEST_DELAY_SEC)

            except Exception as e:
                 logger.exception(f"Watchlist scan failed for {symbol}: {e}")

                 # 🚨 COOL DOWN AFTER ERROR
                 time.sleep(ERROR_COOLDOWN_SEC)
        logger.info(" Watchlist Engine completed")