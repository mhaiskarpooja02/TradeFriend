import json
from datetime import datetime
from dhanhq import dhanhq
from brokers.base_client import BaseBrokerClient
from config.settings import client_id, access_token
from utils.logger import get_logger, get_order_logger

logger = get_logger(__name__)
order_logger = get_order_logger()

class DhanClient(BaseBrokerClient):
    def __init__(self):
        """
        Initialize Dhan client using credentials from settings.py
        """
        try:
            self.dhan = dhanhq(client_id, access_token)
            logger.info("Dhan broker client initialized successfully.")
        except Exception as e:
            logger.error(f"Error initializing Dhan client: {e}", exc_info=True)
            raise

    # ---------------------------------------------------------
    # ORDER FUNCTIONS
    # ---------------------------------------------------------
    def place_order(self, security_id: str, qty: int, tag: str = None) -> bool:
        """
        Wrapper to place a SELL order in Dhan using standard defaults.
        Fully compatible with Dhan SDK signature.
        Logs request and response with timestamps.

        Args:
            security_id (str): The security ID to sell.
            qty (int): Quantity to sell.
            tag (str): Optional correlation ID for tracking.

        Returns:
            bool: True if order placed successfully, False otherwise.
        """
        try:
            # Fixed default parameters
            transaction_type = "SELL"
            exchange_segment = "NSE_EQ"
            order_type = "MARKET"
            product_type = "INTRADAY"
            price = 0
            trigger_price = 0
            disclosed_quantity = 0
            after_market_order = False
            validity = "DAY"
            amo_time = "OPEN"
            bo_profit_value = None
            bo_stop_loss_Value = None
            should_slice = False

            order_payload = {
                "security_id": security_id,
                "qty": qty,
                "transaction_type": transaction_type,
                "exchange_segment": exchange_segment,
                "order_type": order_type,
                "product_type": product_type,
                "price": price,
                "trigger_price": trigger_price,
                "disclosed_quantity": disclosed_quantity,
                "after_market_order": after_market_order,
                "validity": validity,
                "amo_time": amo_time,
                "bo_profit_value": bo_profit_value,
                "bo_stop_loss_Value": bo_stop_loss_Value,
                "tag": tag
            }

            order_logger.info(f"[{datetime.now().isoformat()}] Dhan order request payload: {order_payload}")

            # Call the SDK
            response = self.dhan.place_order(
                security_id=security_id,
                exchange_segment=exchange_segment,
                transaction_type=transaction_type,
                quantity=qty,
                order_type=order_type,
                product_type=product_type,
                price=price,
                trigger_price=trigger_price,
                disclosed_quantity=disclosed_quantity,
                after_market_order=after_market_order,
                validity=validity,
                amo_time=amo_time,
                bo_profit_value=bo_profit_value,
                bo_stop_loss_Value=bo_stop_loss_Value,
                tag=tag
            )

            order_logger.info(f"[{datetime.now().isoformat()}] Dhan order response: {response}")

            # Check response success
            if response and isinstance(response, dict) and response.get("status") == "success":
                order_logger.info(f"Dhan order placed successfully: sid={security_id}, qty={qty}")
                return True
            else:
                order_logger.warning(f"Dhan order not successful: sid={security_id}, qty={qty}, response={response}")
                return False

        except Exception as e:
            logger.error(f"Dhan place_order error: {e}", exc_info=True)
            return False

    # ---------------------------------------------------------
    # HOLDINGS
    # ---------------------------------------------------------
    def get_holdings(self):
        """Fetch and return holdings safely."""
        try:
            response = self.dhan.get_holdings()
            logger.debug(f"Raw holdings API response: {response}")

            if not response or not isinstance(response, dict):
                logger.warning("Holdings API returned empty or invalid response.")
                return []

            holdings = response.get("data", [])
            if not holdings:
                logger.info("Holdings list is empty.")
                return []

            logger.info(f"Fetched {len(holdings)} holdings from API.")
            return holdings

        except Exception as e:
            logger.error(f"get_holdings error: {e}", exc_info=True)
            return []
