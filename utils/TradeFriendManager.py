# utils/TradeFriendManager.py

import logging
from core.TradeFriendDecisionRunner import TradeFriendDecisionRunner
from core.watchlist_engine import WatchlistEngine

from core.TradeFriendSwingMonitor import TradeFriendSwingTradeMonitor
from core.TradeFriendSwingTriggerEngine import TradeFriendSwingTriggerEngine
from db.TradeFriendSettingsRepo import TradeFriendSettingsRepo

logger = logging.getLogger(__name__)


class TradeFriendManager:
    """
    Orchestrator for TradeFriend flow.
    Triggered via Dashboard buttons.
    """

    # ---------------- Daily Scan ----------------
    def tf_daily_scan(self, mode: str):
        logger.info(f"📊 TradeFriend Daily scan started | Mode={mode}")
        engine = WatchlistEngine()
        engine.run()
        logger.info("✅ TradeFriend Daily scan completed")

    # ---------------- Morning Confirmation ----------------
    def tf_morning_confirm(self, capital: float, mode: str):
        logger.info(f"🚀 TradeFriend Morning confirmation started | Mode={mode}")

        # # 👉 scorer can be simple for now
        # scorer = None  # or DummyScorer()

        # runner = TradeFriendDecisionRunner()
        # runner.run()

        # logger.info("✅ TradeFriend Morning confirmation completed")

    # ---------------- Trade Monitoring ----------------
    def tf_monitor(self):
        logger.info("🔁 TradeFriend swing monitoring started")
        monitor = TradeFriendSwingTradeMonitor()
        monitor.run()
        logger.info("✅ TradeFriend swing monitoring completed")

    # ---------------- Trade Execution ----------------
    def tf_trigger_engine(self):
        """
        Phase-2 Trigger Engine
        - READY → OPEN
        - No decision logic
        - No plans
        """
        logger.info("🚀 Trigger Engine invoked")

        settings = TradeFriendSettingsRepo().fetch()

        engine = TradeFriendSwingTriggerEngine(
            capital=settings["available_swing_capital"],
            paper_trade=settings["trade_mode"] == "PAPER"
        )
        engine.run()
    # ------------------------
    # New: Decision Runner
    # ------------------------
    def tf_decision_runner(self):
        """
        Wrapper to run DecisionRunner phase manually or via scheduler.
        """
        logger.info("🧠 TradeFriend DecisionRunner started")
        runner = TradeFriendDecisionRunner()
        runner.run()
        logger.info("✅ TradeFriend DecisionRunner completed")