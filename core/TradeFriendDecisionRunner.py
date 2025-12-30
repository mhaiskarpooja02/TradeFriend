import logging
from core.TradeFriendDataProvider import TradeFriendDataProvider
from db.TradeFriendWatchlistRepo import TradeFriendWatchlistRepo
from core.TradeFriendDecisionEngine import TradeFriendDecisionEngine
from core.TradeFriendPositionSizer import TradeFriendPositionSizer
from strategy.TradeFriendEntry import TradeFriendEntry
from strategy.TradeFriendScoring import TradeFriendScoring
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from db.TradeFriendDatabase import TradeFriendDatabase

logger = logging.getLogger(__name__)


class TradeFriendDecisionRunner:
    """
    PURPOSE:
    - Morning execution engine
    - Confirms trades after first 15-min candle
    """

    def __init__(self, capital):
        self.capital = capital

        self.db = TradeFriendDatabase()
        self.provider = TradeFriendDataProvider()

        self.watchlist_repo = TradeFriendWatchlistRepo(self.db)
        self.trade_repo = TradeFriendTradeRepo(self.db)

        self.scorer = TradeFriendScoring()
        self.sizer = TradeFriendPositionSizer()

        self.decision_engine = TradeFriendDecisionEngine(
            scorer=self.scorer,
            sizer=self.sizer,
            trade_repo=self.trade_repo
        )

    def run(self):
        logger.info("🚀 Decision Runner started")

        watchlist = self.watchlist_repo.fetch_all()
        if not watchlist:
            logger.info("No watchlist symbols to evaluate")
            return

        for row in watchlist:
            symbol = row["symbol"]

            try:
                # 1️⃣ Fetch 15-min data
                df = self.provider.get_intraday_data(symbol, interval="15m")

                if df is None or df.empty or len(df) < 20:
                    continue

                # 2️⃣ Entry confirmation
                entry_strategy = TradeFriendEntry(df, symbol)
                signal = entry_strategy.confirm_entry()

                if not signal:
                    continue

                # 3️⃣ Final decision
                trade = self.decision_engine.evaluate(
                    df=df,
                    signal=signal,
                    capital=self.capital
                )

                if trade:
                    logger.info(
                        f"✅ TRADE CONFIRMED {symbol} | Qty {trade['qty']} | Confidence {trade['confidence']}"
                    )

            except Exception as e:
                logger.exception(f"Decision failed for {symbol}: {e}")

        logger.info("✅ Decision Runner completed")
