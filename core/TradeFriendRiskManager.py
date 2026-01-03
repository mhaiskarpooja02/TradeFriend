from db.TradeFriendSettingsRepo import TradeFriendSettingsRepo


class TradeFriendRiskManager:
    """
    PURPOSE:
    - Enforce swing trading guardrails
    - Amount-based (no percentages)
    - Stateless (reads repo + settings only)
    """

    def __init__(self):
        self.settings = TradeFriendSettingsRepo()

    # -------------------------------------------------
    # MAIN GATE
    # -------------------------------------------------
    def can_take_trade(self, trade_repo, position_value: float, entry_price: float):
        """
        Returns (allowed: bool, reason: str)
        """

        # 1️⃣ MAX OPEN TRADES
        max_open_trades = self.settings.get_int("max_open_trades")
        if max_open_trades > 0:
            current = trade_repo.count_open_trades()
            if current >= max_open_trades:
                return False, "Max open trades limit reached"

        # 2️⃣ TOTAL SWING CAPITAL LIMIT
        max_swing_capital = self.settings.get_float("max_swing_capital")
        if max_swing_capital > 0:
            used_capital = trade_repo.sum_open_position_value()
            if used_capital + position_value > max_swing_capital:
                return False, "Max swing capital exceeded"

        # 3️⃣ PER TRADE CAPITAL LIMIT
        max_per_trade = self.settings.get_float("max_per_trade_capital")
        if max_per_trade > 0 and position_value > max_per_trade:
            return False, "Per-trade capital cap exceeded"

        # 4️⃣ PRICE BRACKET VALIDATION (CRITICAL)
        if not self._is_price_allowed(entry_price):
            return False, "Price not allowed as per configured brackets"

        return True, "Allowed"

    # -------------------------------------------------
    # PRICE BRACKET CHECK
    # -------------------------------------------------
    def _is_price_allowed(self, price: float) -> bool:
        """
        Checks if entry price falls inside ANY enabled price bracket
        """

        brackets = self.settings.get_price_brackets()

        if not brackets:
            # If not configured → allow by default
            return True

        for b in brackets:
            if not b.get("enabled", True):
                continue

            min_p = b.get("min", 0)
            max_p = b.get("max")

            if max_p is None:
                if price >= min_p:
                    return True
            else:
                if min_p <= price < max_p:
                    return True

        return False
