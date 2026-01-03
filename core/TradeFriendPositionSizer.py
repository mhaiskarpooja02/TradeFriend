# core/TradeFriendPositionSizer.py

from db.TradeFriendSettingsRepo import TradeFriendSettingsRepo


class TradeFriendPositionSizer:
    """
    Calculates position size using absolute capital rules
    """

    def __init__(self):
        self.settings = TradeFriendSettingsRepo()

    def calculate(self, entry: float, sl: float) -> dict:
        if entry <= 0 or sl <= 0:
            raise ValueError("Invalid price")

        per_unit_risk = abs(entry - sl)
        if per_unit_risk == 0:
            raise ValueError("Entry and SL cannot be same")

        total_capital = self.settings.get("total_capital", float)
        swing_capital = self.settings.get("swing_capital_amount", float)
        per_trade_cap = self.settings.get("per_trade_capital_amount", float)
        risk_amount = self.settings.get("risk_amount_per_trade", float)

        # 🔒 Capital guards
        allowed_capital = min(per_trade_cap, swing_capital)

        qty_risk_based = int(risk_amount / per_unit_risk)
        qty_cap_based = int(allowed_capital / entry)

        qty = min(qty_risk_based, qty_cap_based)

        if qty <= 0:
            raise ValueError("Quantity resolved to zero")

        return {
            "qty": qty,
            "entry": entry,
            "sl": sl,
            "risk_amount": risk_amount,
            "position_value": round(qty * entry, 2),
            "per_unit_risk": round(per_unit_risk, 2)
        }

    def calculate_qty(self, entry: float, sl: float) -> int:
        try:
            return self.calculate(entry, sl)["qty"]
        except Exception:
            return 0
