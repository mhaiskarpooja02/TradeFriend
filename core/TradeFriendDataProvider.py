import pandas as pd
from datetime import datetime, timedelta
from brokers.angel_client import AngelClient, getltp
from utils.symbol_resolver import SymbolResolver
from utils.logger import get_logger

logger = get_logger(__name__)


class TradeFriendDataProvider:
    def __init__(self):
        self.broker = AngelClient()
         # Initialize available brokers (best-effort)
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

    # --------------------------------------------------
    # CORE FETCH (ONLY source of data)
    # --------------------------------------------------
    def _fetch(self, trading_symbol: str, token: str):
        if not token:
            logger.warning(f"No token for {trading_symbol}")
            return None

        df = self.broker.get_historical_data(
            symbol=trading_symbol,
            token=token
        )

        if df is None or df.empty:
            return None

        return self._normalize_ohlc(df)

    # --------------------------------------------------
    # DAILY FETCH (Swing)
    # --------------------------------------------------
    def fetch_daily(self, trading_symbol: str, token: str):
        return self._fetch(trading_symbol, token)

    # --------------------------------------------------
    # 🔧 NORMALIZER (CRITICAL)
    # --------------------------------------------------
    def _normalize_ohlc(self, df, symbol=None):
        import pandas as pd
    
        df = df.copy()
    
        # 🔍 DEBUG LOG (ONCE PER SYMBOL)
        if df is None or df.empty:
            logger.error(f"{symbol} → Empty DF received from broker")
            return None
    
        logger.debug(
            f"{symbol} → Raw DF columns: {list(df.columns)} | index={type(df.index)}"
        )
    
        # -----------------------------
        # 1️⃣ Resolve datetime column
        # -----------------------------
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
    
        elif "timestamp" in df.columns:
            df["date"] = pd.to_datetime(df["timestamp"])
    
        elif "datetime" in df.columns:
            df["date"] = pd.to_datetime(df["datetime"])
    
        elif isinstance(df.index, pd.DatetimeIndex):
            df["date"] = df.index
    
        else:
            logger.error(
                f"{symbol} → No datetime column found. Columns={list(df.columns)}"
            )
            return None   # ⛔ do NOT raise
    
        df.set_index("date", inplace=True)
    
        # -----------------------------
        # 2️⃣ Normalize OHLCV
        # -----------------------------
        rename_map = {
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
        }
    
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    
        required = ["open", "high", "low", "close"]
        missing = [c for c in required if c not in df.columns]
    
        if missing:
            logger.error(
                f"{symbol} → Missing OHLC columns: {missing} | Available={list(df.columns)}"
            )
            return None
    
        # -----------------------------
        # 3️⃣ Coerce numeric
        # -----------------------------
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
    
        df.dropna(subset=["open", "high", "low", "close"], inplace=True)
    
        if df.empty:
            logger.error(f"{symbol} → DF empty after normalization")
            return None
    
        return df
    
    
    
    def get_ltp(self, resolved_symbol: dict):
        """
        resolved_symbol = {
            exchange, symbol, token
        }
        """
        try:
            logger.warning(f"Calling get ltp {resolved_symbol}")
            resolved = self.resolver.resolve_symbol(resolved_symbol)
            logger.warning(f"Calling get ltp {resolved_symbol}")
            data = getltp(resolved)
            return data
        except Exception as e:
            logger.error(
                f"LTP fetch failed for {resolved_symbol}: {e}"
            )
            return None

