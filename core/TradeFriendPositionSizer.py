# core/TradeFriendPositionSizer.py

from utils.logger import get_logger
from db.TradeFriendSettingsRepo import TradeFriendSettingsRepo

logger = get_logger(__name__)


class TradeFriendPositionSizer:
    """
    PURPOSE:
    - Calculate trade quantity using PRICE → FIXED QTY slabs
    - Enforce per-trade & available swing capital limits
    - Fully amount-based (no % risk logic)
    """

    def __init__(self):
        self.settings_repo = TradeFriendSettingsRepo()

    # -------------------------------------------------
    # MAIN
    # -------------------------------------------------
    def calculate(self, entry_price: float) -> dict:
        """
        Always returns a dict:
        {
            qty: int,
            entry: float,
            position_value: float
        }
        """

        if not entry_price or entry_price <= 0:
            raise ValueError("Invalid entry price")

        # 🔒 HARD NORMALIZATION (fixes sqlite3.Row forever)
        raw_settings = self.settings_repo.fetch()
        settings = dict(raw_settings) if raw_settings else {}

        logger.info(
            f"PositionSizer.calculate() | Entry={entry_price} | Settings={settings}"
        )

        # -----------------------------
        # 1️⃣ BASE QTY FROM PRICE SLABS
        # -----------------------------
        base_qty = self._qty_by_price(entry_price, settings)

        if base_qty <= 0:
            logger.info(
                f"Qty disabled by price slabs | Entry={entry_price}"
            )
            return self._zero_qty(entry_price)

        # -----------------------------
        # 2️⃣ APPLY CAPITAL LIMITS
        # -----------------------------
        qty = base_qty

        max_per_trade = float(settings.get("max_per_trade_capital") or 0)
        available_capital = float(settings.get("available_swing_capital") or 0)

        if max_per_trade > 0:
            cap_qty = int(max_per_trade / entry_price)
            qty = min(qty, cap_qty)

        if available_capital > 0:
            cap_qty = int(available_capital / entry_price)
            qty = min(qty, cap_qty)

        if qty <= 0:
            logger.info(
                f"Qty capped to zero | Entry={entry_price} | "
                f"MaxTradeCap={max_per_trade} | AvailCap={available_capital}"
            )
            return self._zero_qty(entry_price)

        position_value = round(qty * entry_price, 2)

        return {
            "qty": int(qty),
            "entry": float(entry_price),
            "position_value": position_value
        }

    # -------------------------------------------------
    # PRICE → QTY SLABS
    # -------------------------------------------------
    def _qty_by_price(self, price: float, settings: dict) -> int:
        """
        Highest matching slab wins
        """

        slabs = [
            (2000, settings.get("qty_gt_2000", 0)),
            (1500, settings.get("qty_gt_1500", 0)),
            (1000, settings.get("qty_gt_1000", 0)),
            (700,  settings.get("qty_gt_700", 0)),
            (500,  settings.get("qty_gt_500", 0)),
            (200,  settings.get("qty_gt_200", 0)),
            (100,  settings.get("qty_gt_100", 0)),
        ]

        for min_price, qty in slabs:
            try:
                qty = int(qty or 0)
            except Exception:
                qty = 0

            if price >= min_price and qty > 0:
                return qty

        return 0

    # -------------------------------------------------
    # ZERO-QTY SAFE RETURN
    # -------------------------------------------------
    def _zero_qty(self, entry_price: float) -> dict:
        return {
            "qty": 0,
            "entry": float(entry_price),
            "position_value": 0.0
        }
