# core/TradeFriendScheduler.py

import time
import threading
import logging
from datetime import datetime, time as dtime

from core.TradeFriendDecisionRunner import TradeFriendDecisionRunner
from core.TradeFriendMorningConfirmRunner import TradeFriendMorningConfirmRunner
from core.TradeFriendSwingMonitor import TradeFriendSwingTradeMonitor
from db.TradeFriendTradeRepo import TradeFriendTradeRepo

logger = logging.getLogger(__name__)


class TradeFriendScheduler:
    """
    MASTER TIME ORCHESTRATOR
    ------------------------
    - Owns ALL time logic
    - Calls manager ONLY for business actions
    - Minute protected
    """

    def __init__(self, manager, trade_mode=None):
        self.manager = manager
        self.trade_mode = trade_mode

        self.trade_repo = TradeFriendTradeRepo()
        self.morning_runner = TradeFriendMorningConfirmRunner(
            trade_repo=self.trade_repo
        )

        self._running = False
        self._thread = None

        # 🔒 Phase memory
        self._last_scan_date = None
        self._last_trigger_minute = None
        self._decision_done_date = None

    # ==================================================
    # LIFECYCLE
    # ==================================================
    def start(self):
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._loop,
            daemon=True
        )
        self._thread.start()

        logger.info("🕒 TradeFriend Scheduler started")

    def stop(self):
        self._running = False

    # ==================================================
    # TIME HELPERS
    # ==================================================
    def _now(self):
        return datetime.now()

    def _time(self):
        return self._now().time()

    def _today(self):
        return self._now().strftime("%Y-%m-%d")

    def _minute_key(self):
        return self._now().strftime("%Y-%m-%d %H:%M")
    
    def _five_minute_key(self):
        now = self._now()
        minute_bucket = (now.minute // 5) * 5
        return now.strftime(f"%Y-%m-%d %H:{minute_bucket:02d}")


    def _in_range(self, start: dtime, end: dtime):
        t = self._time()
        return start <= t <= end

    # ==================================================
    # TIME WINDOWS (SINGLE SOURCE OF TRUTH)
    # ==================================================
    def is_daily_scan_time(self):
        return self._in_range(dtime(7, 0), dtime(8, 45))

    def is_decision_runner_time(self):
        return self._in_range(dtime(9, 15), dtime(9, 20))

    def is_morning_confirm_time(self):
        return self._in_range(dtime(9, 17), dtime(9, 32))

    def is_trigger_engine_time(self):
        return self._in_range(dtime(9, 16), dtime(15, 25))

    # ==================================================
    # MAIN LOOP
    # ==================================================
    def _loop(self):
        while self._running:
            try:
                now = self._time()
                today = self._today()
                minute_key = self._five_minute_key()

                # ----------------------------------------------
                # ⛔ BEFORE MARKET PREP
                # ----------------------------------------------
                if now < dtime(7, 0):
                    time.sleep(60)
                    continue

                # ----------------------------------------------
                # 1️⃣ DAILY SCAN (ONCE)
                # ----------------------------------------------
                if self.is_daily_scan_time():
                    if self._last_scan_date != today:
                        logger.info("📅 Running daily scan")
                        self.manager.tf_daily_scan(self._get_trade_mode())
                        self._last_scan_date = today

                # ----------------------------------------------
                # 1.5️⃣ DECISION RUNNER (ONCE)
                # ----------------------------------------------
                if self.is_decision_runner_time():
                    # if self._decision_done_date != today:
                        logger.info("🧠 Running DecisionRunner (once)")
                        runner = TradeFriendDecisionRunner()
                        runner.run()
                        self._decision_done_date = today

                # ----------------------------------------------
                # 2️⃣ MORNING CONFIRM
                # ----------------------------------------------
                if self.is_morning_confirm_time():
                    self.morning_runner.run()

                # ----------------------------------------------
                # 3️⃣ TRIGGER ENGINE + SWING MONITOR
                #    (Minute-protected, all day)
                # ----------------------------------------------
                if self.is_trigger_engine_time():
                    if self._last_trigger_minute != minute_key:

                        # ---- ENTRY ENGINE ----
                        self.manager.tf_trigger_engine()

                        # ---- EXIT / MONITOR ----
                        monitor = TradeFriendSwingTradeMonitor(
                            paper_trade=(self._get_trade_mode() == "PAPER")
                        )
                        monitor.run()

                        self._last_trigger_minute = minute_key

            except Exception:
                logger.exception("Scheduler execution failed")

            time.sleep(30)

    # ==================================================
    # TRADE MODE RESOLUTION
    # ==================================================
    def _get_trade_mode(self):
        """
        Always fetch dynamically (UI / DB driven)
        """
        try:
            return self.manager.settings_repo.get_trade_mode()
        except Exception:
            logger.warning("⚠️ Failed to fetch trade mode, defaulting to PAPER")
            return "PAPER"
        
        # ==================================================
    # 🔥 MANUAL ORCHESTRATION (SINGLE ENTRY POINT)
    # ==================================================
    def run_manual(self, mode="FULL", force=False):
        """
        Manual override runner.

        mode:
            - DECISION → DecisionRunner only
            - MORNING  → MorningConfirm only
            - FULL     → Decision → Morning → Trigger/Monitor

        force:
            - Ignore day-level guards
        """

        logger.warning(f"🛠️ Manual run triggered | mode={mode} | force={force}")

        today = self._today()

        # ----------------------------------
        # 1️⃣ DECISION RUNNER
        # ----------------------------------
        if mode in ("DECISION", "FULL"):
            if force or self._decision_done_date != today:
                logger.info("🧠 [MANUAL] Running DecisionRunner")
                runner = TradeFriendDecisionRunner()
                runner.run()
                self._decision_done_date = today
            else:
                logger.info("⏭️ [MANUAL] DecisionRunner already executed")

        # ----------------------------------
        # 2️⃣ MORNING CONFIRM
        # ----------------------------------
        if mode in ("MORNING", "FULL"):
            logger.info("🌅 [MANUAL] Running Morning Confirm")
            self.morning_runner.run()

        # ----------------------------------
        # 3️⃣ TRIGGER + MONITOR (OPTIONAL)
        # ----------------------------------
        if mode == "FULL":
            logger.info("⚡ [MANUAL] Running Trigger Engine + Monitor")

            self.manager.tf_trigger_engine()

            monitor = TradeFriendSwingTradeMonitor(
                paper_trade=(self._get_trade_mode() == "PAPER")
            )
            monitor.run()

        logger.warning(f"✅ Manual run completed | mode={mode}")

