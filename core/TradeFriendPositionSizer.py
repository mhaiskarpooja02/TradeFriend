from db.TradeFriendSettingsRepo import TradeFriendSettingsRepo

class TradeFriendPositionSizer:
    """
    PURPOSE:
    - Calculate position size based on capital & risk
    - Uses TradeFriendSettingsRepo (single source of truth)
    - NO API
    - NO DB writes
    """

    def __init__(self):
        # Centralized settings
        self.settings = TradeFriendSettingsRepo()

    # --------------------------------------------------
    # CORE POSITION SIZING
    # --------------------------------------------------
    def calculate(self, entry: float, sl: float) -> dict:
        """
        Calculate qty using:
        Qty = (capital * risk%) / |entry - sl|
        """

        if entry <= 0 or sl <= 0:
            raise ValueError("Entry and SL must be positive")

        per_unit_risk = abs(entry - sl)
        if per_unit_risk == 0:
            raise ValueError("Entry and SL cannot be same")

        capital = self.settings.capital()          # ✅ function
        risk_pct = self.settings.risk_percent()    # ✅ function

        risk_amount = capital * (risk_pct / 100.0)

        qty = int(risk_amount / per_unit_risk)
        if qty <= 0:
            raise ValueError("Calculated quantity is zero")

        position_value = qty * entry

        return {
            "capital": round(capital, 2),
            "risk_percent": risk_pct,
            "risk_amount": round(risk_amount, 2),
            "per_unit_risk": round(per_unit_risk, 2),
            "qty": qty,
            "position_value": round(position_value, 2)
        }

    # --------------------------------------------------
    # LIGHTWEIGHT QTY ONLY (SAFE)
    # --------------------------------------------------
    def calculate_qty(self, entry: float, sl: float) -> int:
        """
        Returns qty only (no exception)
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