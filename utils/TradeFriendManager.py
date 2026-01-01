# utils/TradeFriendManager.py

import logging
from core.watchlist_engine import WatchlistEngine
from core.TradeFriendDecisionRunner import TradeFriendDecisionRunner
from core.TradeFriendSwingMonitor import TradeFriendSwingTradeMonitor

logger = logging.getLogger(__name__)


class TradeFriendManager:
    """
    Orchestrator for TradeFriend flow.
    Triggered via Dashboard buttons.
    """

    # ---------------- Daily Scan ----------------
    def tf_daily_scan(self):
        logger.info("📊 TradeFriend daily scan started")
        engine = WatchlistEngine()
        engine.run()
        logger.info("✅ TradeFriend daily scan completed")

    # ---------------- Morning Confirmation ----------------
    def tf_morning_confirm(self, capital: float):
        logger.info("🚀 TradeFriend morning confirmation started")
        runner = TradeFriendDecisionRunner()
        runner.run(capital=capital)
        logger.info("✅ TradeFriend morning confirmation completed")

    # ---------------- Trade Monitoring ----------------
    def tf_monitor(self):
        logger.info("🔁 TradeFriend swing monitoring started")
        monitor = TradeFriendSwingTradeMonitor()
        monitor.run()
        logger.info("✅ TradeFriend swing monitoring completed")
