from config.TradeFriendConfig import (
    MAX_OPEN_TRADES,
    MAX_CAPITAL_UTILIZATION,
    SWING_CAPITAL
)


class TradeFriendRiskManager:
    """
    PURPOSE:
    - Central risk gate for swing trades
    - Enforces capital & exposure rules
    """

    def can_take_trade(self, trade_repo, entry, qty):
        """
        Returns (allowed: bool, reason: str)
        """

        # -----------------------------
        # 1️⃣ MAX OPEN TRADES
        # -----------------------------
        open_count = trade_repo.count_open_trades()

        if open_count >= MAX_OPEN_TRADES:
            return False, f"Max open trades reached ({open_count})"

        # -----------------------------
        # 2️⃣ CAPITAL LOCK CHECK
        # -----------------------------
        locked_capital = trade_repo.get_locked_capital()
        new_trade_value = entry * qty

        total_after = locked_capital + new_trade_value
        max_allowed = SWING_CAPITAL * MAX_CAPITAL_UTILIZATION

        if total_after > max_allowed:
            return False, (
                f"Capital lock exceeded | "
                f"Locked={locked_capital:.0f}, "
                f"Required={new_trade_value:.0f}, "
                f"Limit={max_allowed:.0f}"
            )

        # -----------------------------
        # ✅ ALL CHECKS PASSED
        # -----------------------------
        return True, "OK"
