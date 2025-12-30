# utils/TradeFriendManager.py

import logging
from core.watchlist_engine import WatchlistEngine
from core.TradeFriendDecisionRunner import TradeFriendDecisionRunner
from core.trade_manager import TradeManager
from core.TradeFriendSwingMonitor import TradeFriendSwingMonitor
from core.TradeFriendDataProvider import TradeFriendDataProvider
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from db.TradeFriendDatabase import TradeFriendDatabase

logger = logging.getLogger(__name__)


class TradeFriendManager:
    """
    Orchestrator for TradeFriend flow.
    Triggered manually via Dashboard buttons (for now).
    """

    def __init__(self):
        # Reuse existing TradeManager monitoring logic
        self.trade_manager = TradeManager()

    # ---------------- Daily Scan ----------------
    def tf_daily_scan(self):
        logger.info(" TradeFriend daily scan started")
        engine = WatchlistEngine()
        engine.run()
        logger.info(" TradeFriend daily scan completed")

    # ---------------- Morning Confirmation ----------------
    def tf_morning_confirm(self, capital):
        logger.info("🚀 TradeFriend morning confirmation started")
        runner = TradeFriendDecisionRunner(capital=capital)
        runner.run()
        logger.info(" TradeFriend morning confirmation completed")

    # ---------------- Trade Monitoring ----------------
    def tf_monitor(self):
        logger.info("👀 TradeFriend swing monitoring started")

        provider = TradeFriendDataProvider()
        db = TradeFriendDatabase()
        trade_repo = TradeFriendTradeRepo(db)

        monitor = TradeFriendSwingMonitor(
            provider=provider,
            trade_repo=trade_repo
        )
        monitor.run()

        logger.info(" TradeFriend swing monitoring completed")
