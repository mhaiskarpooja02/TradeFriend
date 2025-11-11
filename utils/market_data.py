# utils/market_data.py
from brokers.angel_client import AngelClient

class MarketData:
    _client = None

    @classmethod
    def _get_client(cls):
        if cls._client is None:
            cls._client = AngelClient()
        return cls._client

    @classmethod
    def get_ltp(cls, resolved_symbol):
        return cls._get_client().get_ltp(resolved_symbol)

    @classmethod
    def get_historical_data(cls, symbol, interval="15m", days=30):
        return cls._get_client().get_historical_data(symbol, interval, days)
