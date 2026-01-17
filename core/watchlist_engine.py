from datetime import datetime
import time

from core.TradeFriendDataProvider import TradeFriendDataProvider
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
    - Daily market scan
    - Detect swing setups (Scanner)
    - Build executable plans (Planner = authority)
    - Persist trade INTENT into swing_trade_plans
    - Populate watchlist (IDEA ONLY)
    - Generate clean daily reports

    IMPORTANT:
    - No trading happens here
    - No OMS calls
    - This feeds Phase-1 Decision Runner & Phase-2 Trigger Engine
    """

    def __init__(self):
        self.instrument_db = TradeFindDB()
        self.provider = TradeFriendDataProvider()

        self.watchlist_repo = TradeFriendWatchlistRepo()
        self.swing_plan_repo = TradeFriendSwingPlanRepo()
        self.trade_repo = TradeFriendTradeRepo()

    # ==================================================
    # MAIN RUN
    # ==================================================
    def run(self):
        logger.info("📊 Daily Watchlist Scan started")

        scan_date = datetime.now().strftime("%Y-%m-%d")

        valid_rows = []
        rejected_rows = []
        skipped_rows = []

        traded_symbols = set(self.trade_repo.get_all_symbols())

        # ----------------------------
        # CLEANUP (SAFE)
        # ----------------------------
        self.watchlist_repo.delete_untriggered_older_than(days=7)
        self.swing_plan_repo.delete_orphan_plans()

        symbols = self.instrument_db.get_active()
        if not symbols:
            logger.warning("No active symbols found")
            return

        # ==================================================
        # SCAN LOOP
        # ==================================================
        for row in symbols:
            symbol = row["symbol"]

            try:
                logger.info(f"{symbol} → Scanner started")

                # ----------------------------
                # FETCH DATA
                # ----------------------------
                df = self.provider.get_daily_data(
                    trading_symbol=row["trading_symbol"],
                    token=row["token"]
                )

                if df is None or df.empty:
                    rejected_rows.append({
                        "symbol": symbol,
                        "reason": "No data"
                    })
                    continue

                # ----------------------------
                # SCANNER (SETUP DETECTION)
                # ----------------------------
                scanner = TradeFriendScanner(df, symbol)
                signal = scanner.scan()

                if not signal:
                    rejected_rows.append({
                        "symbol": symbol,
                        "reason": "No setup"
                    })
                    continue

                signal["score"] = int(signal.get("score") or 0)

                # ----------------------------
                # PLAN (FINAL AUTHORITY)
                # ----------------------------
                planner = TradeFriendSwingEntryPlanner(
                    df=df,
                    symbol=symbol,
                    strategy=signal["strategy"]
                )

                plan = planner.build_plan()
                if not plan:
                    rejected_rows.append({
                        "symbol": symbol,
                        "reason": "Plan build failed"
                    })
                    continue

                # ----------------------------
                # ALREADY TRADED CHECK
                # ----------------------------
                if symbol in traded_symbols:
                    skipped_rows.append({
                        "symbol": symbol,
                        "reason": "Already traded"
                    })
                    continue

                # ----------------------------
                # WATCHLIST (IDEA ONLY)
                # ----------------------------
                self.watchlist_repo.upsert({
                    "symbol": symbol,
                    "strategy": signal["strategy"],
                    "bias": signal.get("bias"),
                    "score": signal["score"]
                })

                # ----------------------------
                # 🔥 ATTACH TRADE INTENT
                # ----------------------------
                plan.update({
                    "direction": signal.get("direction", "BUY"),
                    "order_type": signal.get("order_type", "MARKET"),
                    "trade_type": "SWING",        # Phase-1 default
                    "carry_forward": 1,           # Swing = allowed
                    "product_type": "CNC"
                })

                # ----------------------------
                # SAVE / UPDATE SWING PLAN
                # ----------------------------
                existing_plan = self.swing_plan_repo.get_active_plan(symbol)

                if existing_plan:
                    old_entry = float(existing_plan["entry"])
                    new_entry = float(plan["entry"])

                    # LONG logic (BUY)
                    if plan["direction"] == "BUY" and new_entry >= old_entry:
                        skipped_rows.append({
                            "symbol": symbol,
                            "reason": "Worse entry than existing plan"
                        })
                        continue

                    # SHORT logic (future-ready)
                    if plan["direction"] == "SELL" and new_entry <= old_entry:
                        skipped_rows.append({
                            "symbol": symbol,
                            "reason": "Worse entry than existing plan"
                        })
                        continue

                    # ✅ Better plan → update
                    self.swing_plan_repo.update_plan(
                        plan_id=existing_plan["id"],
                        new_plan=plan
                    )

                else:
                    self.swing_plan_repo.save_plan(plan)

                # ----------------------------
                # REPORT ROW
                # ----------------------------
                valid_rows.append({
                    "symbol": symbol,
                    "strategy": signal["strategy"],
                    "bias": signal.get("bias"),
                    "direction": plan["direction"],
                    "order_type": plan["order_type"],
                    "entry": plan["entry"],
                    "sl": plan["sl"],
                    "target": plan.get("target") or plan.get("target1"),
                    "scan_date": scan_date
                })

                time.sleep(REQUEST_DELAY_SEC)

            except Exception as e:
                logger.exception(f"{symbol} failed: {e}")
                time.sleep(ERROR_COOLDOWN_SEC)

        # ==================================================
        # REPORT GENERATION
        # ==================================================
        self._generate_reports(
            scan_date=scan_date,
            valid_rows=valid_rows,
            rejected_rows=rejected_rows,
            skipped_rows=skipped_rows
        )

        logger.info("✅ Daily Watchlist Scan completed")

    # ==================================================
    # REPORTS
    # ==================================================
    def _generate_reports(self, scan_date, valid_rows, rejected_rows, skipped_rows):
        try:
            csv_path = f"reports/daily_scan/scan_{scan_date}.csv"
            pdf_path = f"reports/daily_scan/scan_{scan_date}.pdf"

            TradeFriendInitialScanCsvExporter().export(
                rows=valid_rows,
                output_path=csv_path
            )

            TradeFriendInitialScanPdfGenerator().generate(
                scan_date=scan_date,
                rows=valid_rows,
                score_cutoff=7,
                output_path=pdf_path
            )

            TradeFriendDailyScanReportService.send_email(
                scan_date=scan_date,
                scan_results=valid_rows,
                attachments=[csv_path, pdf_path]
            )

            logger.info(
                f"📨 Scan Summary → "
                f"VALID={len(valid_rows)} | "
                f"REJECTED={len(rejected_rows)} | "
                f"SKIPPED={len(skipped_rows)}"
            )

        except Exception as e:
            logger.exception(f"Scan report generation failed: {e}")
