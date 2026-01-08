class MorningConfirmReport:
    """
    Collects morning confirm decisions in-memory
    """

    def __init__(self, mode: str, capital: float):
        self.mode = mode
        self.capital = capital
        self.rows = []

    def add(self,
            symbol,
            ltp,
            entry,
            sl,
            target,
            decision,
            reason,
            qty=0,
            position_value=0,
            confidence=None):
        self.rows.append({
            "symbol": symbol,
            "ltp": ltp,
            "entry": entry,
            "sl": sl,
            "target": target,
            "decision": decision,
            "reason": reason,
            "qty": qty,
            "position_value": position_value,
            "confidence": confidence
        })

    def is_empty(self):
        return len(self.rows) == 0
