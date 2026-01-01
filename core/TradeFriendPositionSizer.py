class TradeFriendPositionSizer:
    """
    PURPOSE:
    - Calculate position size based on risk
    - NO DB
    - NO API
    """

    def __init__(self, capital: float, risk_pct: float = 1.0):
        """
        capital   : total trading capital
        risk_pct : % risk per trade (default 1%)
        """
        self.capital = capital
        self.risk_pct = risk_pct

    def calculate(self, entry: float, sl: float):
        """
        Returns position sizing details
        """

        if entry <= 0 or sl <= 0:
            raise ValueError("Entry and SL must be positive")

        per_unit_risk = abs(entry - sl)

        if per_unit_risk == 0:
            raise ValueError("Entry and SL cannot be same")

        risk_amount = (self.capital * self.risk_pct) / 100

        qty = int(risk_amount / per_unit_risk)

        if qty <= 0:
            raise ValueError("Calculated quantity is zero")

        position_value = qty * entry

        return {
            "qty": qty,
            "risk_amount": round(risk_amount, 2),
            "per_unit_risk": round(per_unit_risk, 2),
            "position_value": round(position_value, 2)
        }
    
    def calculate_qty(self, capital: float, entry: float, sl: float) -> int:
        """
        Qty = (capital * risk%) / per-unit risk
        """

        if entry <= sl:
            return 0

        risk_amount = capital * (self.risk_pct / 100.0)
        per_unit_risk = abs(entry - sl)

        if per_unit_risk == 0:
            return 0

        qty = int(risk_amount / per_unit_risk)
        return max(qty, 0)