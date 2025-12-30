import pandas as pd
from datetime import datetime, timedelta
from brokers.angel_client import AngelClient
from utils.symbol_resolver import SymbolResolver
from utils.logger import get_logger

logger = get_logger(__name__)


class TradeFriendDataProvider:
    def __init__(self):
        self.broker = AngelClient()
        if getattr(self.broker, "smart_api", None) is None:
            raise Exception("Broker login failed")

        self.resolver = SymbolResolver()

    def get_daily_data(self, trading_symbol, token):
        """
        Used by scanners (run once daily)
        """
        return self._fetch(trading_symbol, token)

    def get_intraday_data(self, symbol, interval="15m", days=5):
        """
        Used for next-day confirmation (15-min candle)
        """
        return self._fetch(symbol, interval=interval, days=days)

    def _fetch(self, trading_symbol, token):
        # mapping = self.resolver.resolve_symbol_tradefinder(symbol)
        # if not mapping:
        #     return None

        # trading_symbol = mapping.get("trading_symbol")
        # token = mapping.get("token")
        if not token:
            return None

        df = self.broker.get_historical_data(symbol=trading_symbol,token= token)

        if df is None or df.empty:
            return None

        return self._normalize(df)

    def _normalize(self, df: pd.DataFrame):
        """
        Ensure strategy-safe dataframe
        """
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]

        required = ["open", "high", "low", "close", "volume"]
        if not all(c in df.columns for c in required):
            return None

        df = df.sort_index()
        df = df.dropna()
        return df
