# instrument_helper.py

import pprint
import json
from brokers.angel_client import AngelClient
from utils.logger import get_logger

logger = get_logger(__name__)


class InstrumentHelper:
    """
    Helper class to fetch tradingsymbols from AngelClient (broker)
    and ensure results are always in consistent format.
    """

    def __init__(self):
        self.broker = AngelClient()

    def search_symbol(self, exchange: str, symbol: str):
        """
        Calls AngelClient's search_symbol and returns a list of dicts.

        Handles:
            - Single dict
            - List of dicts
            - JSON strings
            - Unexpected formats

        Args:
            exchange (str): Exchange name e.g., "NSE"
            symbol (str): Symbol to search

        Returns:
            list[dict]: List of tradingsymbol dictionaries
        """
        try:
            logger.debug(f"Searching symbol '{symbol}' on exchange '{exchange}'")
            result = self.broker.search_symbol(exchange, symbol)

            logger.debug(f"Processed result for '{symbol}': Result {(result)}")
            return result

        except Exception as e:
            logger.error(f"Error searching symbol '{symbol}' on {exchange}: {e}", exc_info=True)
            return []
