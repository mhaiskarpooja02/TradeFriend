import time
import pandas as pd
from datetime import datetime, timedelta
from brokers.angel_client import AngelClient, getltp,init_client
from utils.symbol_resolver import SymbolResolver
from utils.logger import get_logger
from config.TradeFriendConfig import ERROR_COOLDOWN_SEC, MAX_RETRIES, REQUEST_DELAY_SEC, RETRY_DELAY

logger = get_logger(__name__)


class TradeFriendDataProvider:
    def __init__(self):
        logger.info("🚀 TradeFriendDataProvider initialized")

        
        self.broker = init_client()

        if getattr(self.broker, "smart_api", None) is None:
            logger.warning("⚠️ Broker not ready yet — will retry lazily")

        self.resolver = SymbolResolver()

        # REQUIRED STATE
        self._error_until = 0
        self._last_request_ts = 0

        logger.info("✅ DataProvider ready | throttle initialized")

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
    
    
    
    def get_ltp_byLtp(self, symbol: str):
       logger.info(f"📡 get_ltp CALLED | symbol={symbol}")
    
       for attempt in range(1, MAX_RETRIES + 1):
           try:
               self._throttle()
    
               resolved = self.resolver.resolve_symbol(symbol)
               if not resolved:
                   logger.warning(f"⚠️ Symbol resolution failed | {symbol}")
                   return 0.0
    
               ltp = getltp(resolved)
    
               # 🔑 KEY CHANGE
               if ltp is None:
                   logger.warning(
                       f"⚠️ LTP unavailable | symbol={symbol} | returning 0"
                   )
                   return 0.0
    
               return float(ltp)
    
           except RuntimeError as e:
               # Broker cooldown → do NOT retry
               logger.warning(f"🚫 Broker cooldown active | {symbol}")
               return 0.0
    
           except Exception as e:
               logger.warning(
                   f"⚠️ LTP attempt {attempt}/{MAX_RETRIES} failed | symbol={symbol} | error={e}"
               )
    
               if attempt < MAX_RETRIES:
                   time.sleep(RETRY_DELAY)
               else:
                   logger.error(
                       f"⛔ LTP failed after retries | symbol={symbol} | returning 0"
                   )
                   return 0.0


    def get_ltp(self, symbol: str):
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                self._throttle()

                resolved = self.resolver.resolve_symbol(symbol)
                if not resolved:
                    raise ValueError("Symbol resolution failed")

                response = getltp(resolved)

                if not response or not getattr(response, "ltpData", None):
                    raise ValueError("Empty LTP response")

                return float(response.ltpData.get("ltp"))

            except Exception as e:
                logger.warning(
                    f"LTP attempt {attempt}/{MAX_RETRIES} failed for {symbol}: {e}"
                )

                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                else:
                    self._error_until = time.time() + ERROR_COOLDOWN_SEC
                    logger.error(
                        f"⛔ LTP blocked for {symbol} | cooldown {ERROR_COOLDOWN_SEC}s"
                    )
                    return None


    def _throttle(self):
        now = time.time()

        logger.debug(
            "⏱ throttle check | now=%s | last=%s | error_until=%s",
            round(now, 2),
            round(self._last_request_ts, 2),
            round(self._error_until, 2)
        )

        # 🔴 Circuit breaker active
        if now < self._error_until:
            logger.warning("🚫 Broker cooldown active — blocking request")
            raise RuntimeError("Broker cooldown active")

        # ⏳ Rate limit
        elapsed = now - self._last_request_ts
        if elapsed < REQUEST_DELAY_SEC:
            sleep_time = REQUEST_DELAY_SEC - elapsed
            logger.debug("⏳ Rate limit sleep | %ss", round(sleep_time, 2))
            time.sleep(sleep_time)

        self._last_request_ts = time.time()
        logger.debug("✅ Throttle passed")