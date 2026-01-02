from db.TradeFriendSettingsRepo import TradeFriendSettingsRepo


class TradeFriendPositionSizer:
    """
    PURPOSE:
    - Centralized position sizing logic
    - Reads capital & risk from settings DB
    - NO API
    - NO UI
    """

    def __init__(self):
        """
        Loads settings automatically
        """
        self.settings = TradeFriendSettingsRepo()

    # -------------------------------------------------
    # CORE RISK-BASED POSITION SIZE
    # -------------------------------------------------
    def calculate(self, entry: float, sl: float) -> dict:
        """
        Calculate position sizing based on risk %

        Returns:
        {
            qty,
            risk_amount,
            per_unit_risk,
            position_value
        }
        """

        if entry <= 0 or sl <= 0:
            raise ValueError("Entry and SL must be positive")

        per_unit_risk = abs(entry - sl)
        if per_unit_risk == 0:
            raise ValueError("Entry and SL cannot be the same")

        capital = self.settings.capital()
        risk_pct = self.settings.risk_percent()

        risk_amount = (capital * risk_pct) / 100.0
        qty = int(risk_amount / per_unit_risk)

        if qty <= 0:
            raise ValueError("Calculated quantity is zero")

        position_value = qty * entry

        return {
            "qty": qty,
            "risk_amount": round(risk_amount, 2),
            "per_unit_risk": round(per_unit_risk, 2),
            "position_value": round(position_value, 2),
        }

    # -------------------------------------------------
    # SAFE QTY ONLY (FOR QUICK CHECKS)
    # -------------------------------------------------
    def calculate_qty(self, entry: float, sl: float) -> int:
        """
        Lightweight qty calculation
        """

        if entry <= 0 or sl <= 0:
            return 0

        per_unit_risk = abs(entry - sl)
        if per_unit_risk == 0:
            return 0

        capital = self.settings.capital()
        risk_pct = self.settings.risk_percent()

        risk_amount = capital * (risk_pct / 100.0)
        qty = int(risk_amount / per_unit_risk)

        return max(qty, 0)
