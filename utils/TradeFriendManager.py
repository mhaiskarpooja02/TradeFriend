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

        runner = TradeFriendDecisionRunner(mode=mode,capital=capital)
        runner.run()

        logger.info("✅ TradeFriend Morning confirmation completed")

    # ---------------- Trade Monitoring ----------------
    def tf_monitor(self):
        logger.info("🔁 TradeFriend swing monitoring started")
        monitor = TradeFriendSwingTradeMonitor()
        monitor.run()
        logger.info("✅ TradeFriend swing monitoring completed")
