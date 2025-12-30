class TradeFriendPositionSizer:
    """
    PURPOSE:
    - Decide quantity based on risk
    - Keeps loss per trade fixed
    """

    def __init__(self, risk_percent=1.0):
        self.risk_percent = risk_percent

    def calculate_qty(self, capital, entry, sl):
        if entry <= sl:
            return 0

        risk_amount = capital * (self.risk_percent / 100)
        per_share_risk = entry - sl

        qty = int(risk_amount // per_share_risk)
        return max(qty, 0)
