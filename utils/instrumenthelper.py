# instrument_helper.py

import time
import random
import json
import sqlite3
from brokers.angel_client import AngelClient
from utils.logger import get_logger

logger = get_logger(__name__)

MAX_RETRIES = 3
BASE_DELAY = 0.6    # seconds (Angel safe)
JITTER = 0.25       # random jitter


class InstrumentHelper:
    """
    Helper class to fetch tradingsymbols from AngelClient (broker)
    and ensure inputs and outputs are always safe.
    """

    def __init__(self):
        self.broker = AngelClient()

    # ------------------------------------------------------
    # 🔒 INTERNAL: normalize symbol input
    # ------------------------------------------------------
    def _normalize_symbol(self, symbol):
        """
        Ensures symbol is always a string.
        Accepts:
            - str
            - sqlite3.Row (expects 'symbol' key)
            - dict (expects 'symbol' key)
        """
        if isinstance(symbol, str):
            return symbol.strip()

        if isinstance(symbol, sqlite3.Row):
            return str(symbol["symbol"]).strip()

        if isinstance(symbol, dict):
            return str(symbol.get("symbol", "")).strip()

        raise TypeError(f"Invalid symbol type passed: {type(symbol)}")

    # ------------------------------------------------------
    # 🚀 SAFE SEARCH METHOD
    # ------------------------------------------------------
    def search_symbol(self, exchange: str, symbol):
        """
        Angel API safe search with:
        - input normalization
        - rate limiting
        - retry + backoff
        - JSON safety
        """

        try:
            symbol = self._normalize_symbol(symbol)
        except Exception as e:
            logger.error(f"Symbol normalization failed: {e}")
            return {}

        if not symbol:
            logger.error("Empty symbol after normalization")
            return {}

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # ⏳ Throttle
                time.sleep(BASE_DELAY + random.uniform(0, JITTER))

                logger.info(f"Searching symbol {symbol} in Angel API...")

                result = self.broker.search_symbol(exchange, symbol)

                # ❌ No response
                if not result:
                    logger.warning(f"No response for {symbol}")
                    return {}

                # 🧠 Angel sometimes returns JSON string
                if isinstance(result, str):
                    try:
                        result = json.loads(result)
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON response for {symbol}")
                        return {}

                # ❌ Rate-limit detection
                message = str(result).lower()
                if "access denied" in message or "rate" in message:
                    raise RuntimeError("Angel API rate limited")

                logger.info(f"Processed result for '{symbol}': {result}")
                return result

            except Exception as e:
                logger.warning(
                    f"Search failed for {symbol} "
                    f"(Attempt {attempt}/{MAX_RETRIES}): {e}"
                )

                # ⏳ Exponential backoff
                time.sleep((BASE_DELAY * attempt) + random.uniform(0, JITTER))

        logger.error(f"Search failed permanently for {symbol}")
        return {}
