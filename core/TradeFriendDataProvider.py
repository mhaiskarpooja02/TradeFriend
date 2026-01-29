import time
import pandas as pd
from datetime import datetime, timedelta
from brokers.angel_client import AngelClient, getltp,init_client
from utils.symbol_resolver import SymbolResolver
from utils.logger import get_logger
from config.TradeFriendConfig import ERROR_COOLDOWN_SEC, MAX_RETRIES, REQUEST_DELAY_SEC, RETRY_DELAY
from datetime import datetime, time as dtime

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
        self._ltp_cache = {}
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
    # is_market_open
    # --------------------------------------------------
    def is_market_open(self) -> bool:
        now = datetime.now().time()

        market_open = dtime(9, 15)
        market_close = dtime(15, 30)

        is_open = market_open <= now <= market_close

        logger.debug(
            "🕒 Market check | now=%s | open=%s",
            now.strftime("%H:%M"),
            is_open
        )

        return is_open

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
    

    def get_ltp_byLtp(self, symbol: str, allow_pre_market_fetch: bool = False):
       logger.info(
           f"📡 get_ltp CALLED | symbol={symbol} | allow_pre_market={allow_pre_market_fetch}"
       )

       now = time.time()
       cached = self._ltp_cache.get(symbol)

       # -----------------------------
       # 🛑 Market closed handling
       # -----------------------------
    #    if not self.is_market_open() and not allow_pre_market_fetch:
    #        if cached:
    #            logger.debug(
    #                f"📦 LTP cache hit (market closed) | {symbol} → {cached[0]}"
    #            )
    #            return cached[0]

    #        logger.warning(f"⚠️ No cached LTP (market closed) | {symbol}")
    #        return None

       # -----------------------------
       # ⏱ Cache valid?
       # -----------------------------
       if cached:
           ltp, ts = cached
           age = now - ts

           if age < (REQUEST_DELAY_SEC * 60):
               logger.debug(
                   f"📦 LTP cache hit | {symbol} → {ltp} (age {int(age)}s)"
               )
               return ltp

       # -----------------------------
       # 📡 Fetch fresh LTP (allowed)
       # -----------------------------
       for attempt in range(1, MAX_RETRIES + 1):
           try:
               self._throttle()

               resolved = self.resolver.resolve_symbol(symbol)
               if not resolved:
                   logger.warning(f"⚠️ Symbol resolution failed | {symbol}")
                   return cached[0] if cached else None

               ltp = getltp(resolved)

               if ltp is None:
                   logger.warning(f"⚠️ LTP unavailable | {symbol}")
                   return cached[0] if cached else None

               ltp = float(ltp)

               self._ltp_cache[symbol] = (ltp, now)
               return ltp

           except RuntimeError:
               logger.warning(f"🚫 Broker cooldown | {symbol}")
               return cached[0] if cached else None

           except Exception as e:
               logger.warning(
                   f"⚠️ LTP attempt {attempt}/{MAX_RETRIES} failed | "
                   f"symbol={symbol} | error={e}"
               )

               if attempt < MAX_RETRIES:
                   time.sleep(RETRY_DELAY)
               else:
                   logger.error(f"⛔ LTP failed after retries | {symbol}")
                   return cached[0] if cached else None
    
    
   
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