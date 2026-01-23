# core/WatchlistEngine.py

from datetime import datetime, timedelta
import time
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from config.TradeFriendConfig import (
    REQUEST_DELAY_SEC,
    ERROR_COOLDOWN_SEC,
    SWING_PLAN_EXPIRY_DAYS
)

from core.TradeFriendDataProvider import TradeFriendDataProvider
from core.TradeFriendInitialScanReportService import (
    TradeFriendDailyScanReportService
)

from strategy.TradeFriendScanner import TradeFriendScanner
from strategy.TradeFriendSwingEntryPlanner import TradeFriendSwingEntryPlanner
from core.TradeFriendConfidenceScorer import TradeFriendConfidenceScorer

from db.tradefindinstrument_db import TradeFindDB
from db.TradeFriendWatchlistRepo import TradeFriendWatchlistRepo
from db.TradeFriendSwingPlanRepo import TradeFriendSwingPlanRepo
from db.TradeFriendTradeRepo import TradeFriendTradeRepo

from reports.TradeFriendInitialScanCsvExporter import (
    TradeFriendInitialScanCsvExporter
)
from reports.TradeFriendInitialScanPdfGenerator import (
    TradeFriendInitialScanPdfGenerator
)

from utils.logger import get_logger

logger = get_logger(__name__)

STATE_FILE = "control/tradefriend_run_state.json"


class WatchlistEngine:
    """
    RESPONSIBILITY:
    - Daily symbol scan
    - Create / update SWING PLANS (PLANNED state)
    - Confidence calculated ONLY at scan time
    - NO execution
    - NO capital logic
    """

    def __init__(self):
        self.instrument_db = TradeFindDB()
        self.provider = TradeFriendDataProvider()

        self.watchlist_repo = TradeFriendWatchlistRepo()
        self.swing_plan_repo = TradeFriendSwingPlanRepo()
        self.trade_repo = TradeFriendTradeRepo()

        self.confidence_scorer = TradeFriendConfidenceScorer()

        # Hard API throttle (broker-safe)
        self.api_semaphore = threading.Semaphore(2)

    # ==================================================
    # STATE MANAGEMENT
    # ==================================================

    def _load_state(self):
        if not os.path.exists(STATE_FILE):
            return {
                "daily_scan": {"last_run_date": None, "force_run": False}
            }

        with open(STATE_FILE, "r") as f:
            return json.load(f)

    def _save_state(self, state):
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)

    def _can_run_today(self) -> bool:
        state = self._load_state()
        today = datetime.now().strftime("%Y-%m-%d")

        daily = state["daily_scan"]
        if daily.get("force_run"):
            logger.warning("⚠ Daily scan FORCE enabled")
            return True

        return daily.get("last_run_date") != today

    def _mark_done_today(self):
        state = self._load_state()
        state["daily_scan"]["last_run_date"] = (
            datetime.now().strftime("%Y-%m-%d")
        )
        state["daily_scan"]["force_run"] = False
        self._save_state(state)

    # ==================================================
    # SYMBOL SCAN (THREAD SAFE)
    # ==================================================

    def _scan_symbol_safe(
        self,
        row,
        traded_symbols,
        scan_date,
        valid,
        rejected,
        skipped
    ):
        symbol = row["symbol"]

        try:
            logger.info(f"{symbol} → Scan started")

            # -------------------------------
            # DATA FETCH (THROTTLED)
            # -------------------------------
            with self.api_semaphore:
                time.sleep(REQUEST_DELAY_SEC)
                df = self.provider.get_daily_data(
                    trading_symbol=row["trading_symbol"],
                    token=row["token"]
                )

            if df is None or df.empty:
                rejected.append({"symbol": symbol, "reason": "No data"})
                return

            # -------------------------------
            # READY LTP VALIDATION
            # -------------------------------
            ltp = self._validate_symbol_ltp_ready(row, rejected)
            if ltp is None:
                return

            # -------------------------------
            # STRATEGY SCAN
            # -------------------------------
            signal = TradeFriendScanner(df, symbol).scan()
            if not signal:
                rejected.append({"symbol": symbol, "reason": "No setup"})
                return

            # -------------------------------
            # ENTRY PLAN
            # -------------------------------
            plan = TradeFriendSwingEntryPlanner(
                df=df,
                symbol=symbol,
                strategy=signal["strategy"]
            ).build_plan()

            if not plan:
                rejected.append({"symbol": symbol, "reason": "Plan build failed"})
                return

            # -------------------------------
            # CONFIDENCE SCORING (SCAN TIME)
            # -------------------------------
            vol_avg = df["volume"].rolling(20).mean().iloc[-1]

            try:
                target = float(plan.get("target") or plan.get("target1") or 0)
                entry = float(plan["entry"])
                sl = float(plan["sl"])
                rr = abs((target - entry) / (entry - sl))
            except Exception:
                rr = 0

            scan_context = {
                "htf_trend": signal.get("bias"),
                "location": signal.get("strategy"),
                "rsi": float(df["rsi"].iloc[-1]),
                "volume_ratio": (
                    df["volume"].iloc[-1] / vol_avg
                    if vol_avg and vol_avg > 0 else 0
                ),
                "rr": rr
            }

            confidence = self.confidence_scorer.score(scan_context)

            logger.info(
                f"📊 {symbol} | confidence={confidence} | rr={rr:.2f}"
            )

            # -------------------------------
            # DUPLICATE TRADE GUARD
            # -------------------------------
            if symbol in traded_symbols:
                skipped.append({"symbol": symbol, "reason": "Already traded"})
                return

            # -------------------------------
            # WATCHLIST UPSERT
            # -------------------------------
            self.watchlist_repo.upsert({
                "symbol": symbol,
                "strategy": signal["strategy"],
                "bias": signal.get("bias"),
                "score": confidence
            })

            # -------------------------------
            # PLAN METADATA (LIFECYCLE)
            # -------------------------------
            plan.update({
                "direction": signal.get("direction", "BUY"),
                "order_type": signal.get("order_type", "MARKET"),
                "trade_type": "SWING",
                "carry_forward": 1,
                "product_type": "CNC",

                # confidence (CRITICAL)
                "confidence": confidence,

                # lifecycle
                "status": "PLANNED",
                "created_at": scan_date,
                "expires_at": (
                    datetime.now()
                    + timedelta(days=SWING_PLAN_EXPIRY_DAYS)
                ).strftime("%Y-%m-%d")
            })

            # -------------------------------
            # PLAN UPSERT (BETTER ENTRY ONLY)
            # -------------------------------
            existing = self.swing_plan_repo.get_active_plan(symbol)

            if existing:
                old_entry = float(existing["entry"])
                new_entry = float(plan["entry"])

                if plan["direction"] == "BUY" and new_entry >= old_entry:
                    skipped.append({"symbol": symbol, "reason": "Worse entry"})
                    return

                self.swing_plan_repo.update_plan(
                    plan_id=existing["id"],
                    new_plan=plan
                )
            else:
                self.swing_plan_repo.save_plan(plan)

            # -------------------------------
            # VALID RESULT
            # -------------------------------
            valid.append({
                "symbol": symbol,
                "strategy": signal["strategy"],
                "bias": signal.get("bias"),
                "direction": plan["direction"],
                "entry": plan["entry"],
                "sl": plan["sl"],
                "target": plan.get("target") or plan.get("target1"),
                "confidence": confidence,
                "scan_date": scan_date
            })

            time.sleep(REQUEST_DELAY_SEC)

        except Exception as e:
            logger.exception(f"{symbol} failed: {e}")
            time.sleep(ERROR_COOLDOWN_SEC)

    # ==================================================
    # MAIN RUN
    # ==================================================

    def run(self):
        if not self._can_run_today():
            logger.info("⏭ Daily scan skipped (already executed)")
            return

        logger.info("📊 Daily Watchlist Scan started")

        scan_date = datetime.now().strftime("%Y-%m-%d")
        valid, rejected, skipped = [], [], []

        traded_symbols = set(self.trade_repo.get_all_symbols())

        self.watchlist_repo.delete_untriggered_older_than(days=7)
        self.swing_plan_repo.delete_orphan_plans()

        symbols = self.instrument_db.get_active()
        if not symbols:
            logger.warning("No active symbols found")
            return

        logger.info(f"🔍 Scanning {len(symbols)} symbols")

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [
                executor.submit(
                    self._scan_symbol_safe,
                    row,
                    traded_symbols,
                    scan_date,
                    valid,
                    rejected,
                    skipped
                )
                for row in symbols
            ]

            for f in as_completed(futures):
                f.result()

        self._generate_reports(scan_date, valid, rejected, skipped)
        self._mark_done_today()

        logger.info("✅ Daily Watchlist Scan completed")

    # ==================================================
    # REPORTS
    # ==================================================

    def _generate_reports(self, scan_date, valid, rejected, skipped):
        try:
            csv_path = f"reports/daily_scan/scan_{scan_date}.csv"
            pdf_path = f"reports/daily_scan/scan_{scan_date}.pdf"

            TradeFriendInitialScanCsvExporter().export(valid, csv_path)
            TradeFriendInitialScanPdfGenerator().generate(
                scan_date=scan_date,
                rows=valid,
                score_cutoff=7,
                output_path=pdf_path
            )

            TradeFriendDailyScanReportService.send_email(
                scan_date=scan_date,
                scan_results=valid,
                attachments=[csv_path, pdf_path]
            )

            logger.info(
                f"📨 Scan Summary → "
                f"VALID={len(valid)} | "
                f"REJECTED={len(rejected)} | "
                f"SKIPPED={len(skipped)}"
            )

        except Exception as e:
            logger.exception(f"Report generation failed: {e}")

    # ==================================================
    # LTP VALIDATION
    # ==================================================

    def _validate_symbol_ltp_ready(self, row: dict, rejected: list) -> float | None:
        symbol = row["symbol"]

        try:
            logger.info(f"🔎 READY LTP check | {symbol}")

            ltp = self.provider.get_ltp_byLtp(symbol)

            if ltp is None or not isinstance(ltp, (int, float)) or ltp <= 0:
                rejected.append({
                    "symbol": symbol,
                    "reason": "Invalid LTP at READY stage"
                })
                return None

            return ltp

        except Exception as e:
            logger.error(f"❌ READY LTP error | {symbol} | {e}")
            rejected.append({
                "symbol": symbol,
                "reason": "LTP validation error"
            })
            return None
