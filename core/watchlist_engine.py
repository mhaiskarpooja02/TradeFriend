from datetime import datetime
import logging
import time
from core.TradeFriendDataProvider import TradeFriendDataProvider
from db.TradeFriendDatabase import TradeFriendDatabase
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from reports.TradeFriendInitialScanCsvExporter import TradeFriendInitialScanCsvExporter
from reports.TradeFriendInitialScanPdfGenerator import TradeFriendInitialScanPdfGenerator
from strategy.TradeFriendScanner import TradeFriendScanner
from db.tradefindinstrument_db import TradeFindDB
from db.TradeFriendWatchlistRepo import TradeFriendWatchlistRepo
from config.TradeFriendConfig import REQUEST_DELAY_SEC, ERROR_COOLDOWN_SEC
from strategy.TradeFriendSwingEntryPlanner import TradeFriendSwingEntryPlanner
from db.TradeFriendSwingPlanRepo import TradeFriendSwingPlanRepo
from core.TradeFriendInitialScanReportService import TradeFriendDailyScanReportService
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

        scan_date = datetime.now().strftime("%Y-%m-%d")
        scan_results = []   # 🔹 Phase-6 collector

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

                # 🔹 Phase-6: capture ONLY persisted symbols
                scan_results.append({
                    "symbol": signal["symbol"],
                    "strategy": signal.get("strategy"),
                    "bias": signal.get("bias"),
                    "score": signal.get("score"),
                    "entry": signal.get("entry"),
                    "sl": signal.get("sl"),
                    "target": signal.get("target"),
                    "scan_date": scan_date
                })
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
        
        # ==================================================
        # 🔹 PHASE-6 — INITIAL SCAN REPORT
        # ==================================================
        try:
            csv_path = f"reports/daily_scan/scan_{scan_date}.csv"
            pdf_path = f"reports/daily_scan/scan_{scan_date}.pdf"
    
            TradeFriendInitialScanCsvExporter().export(
                rows=scan_results,
                output_path=csv_path
            )
    
            TradeFriendInitialScanPdfGenerator().generate(
                scan_date=scan_date,
                rows=scan_results,
                score_cutoff=7,
                output_path=pdf_path
            )
    
            logger.info("📨 Daily scan report generated (CSV + PDF)")

            # 🔹 Phase-6 Report
            TradeFriendDailyScanReportService.send_email(
                scan_date=scan_date,
                scan_results=scan_results,
                attachments=[csv_path, pdf_path]
            )
    
        except Exception as e:
            logger.exception(f"Scan report generation failed: {e}")

        logger.info("✅ Daily Watchlist Scan completed")