from config.TradeFriendConfig import (
    MAX_OPEN_TRADES,
    MAX_CAPITAL_UTILIZATION
)

class TradeFriendRiskManager:

    def can_take_trade(self, trade_repo, capital, required_capital):
        open_trades = trade_repo.fetch_open_trades()

        if len(open_trades) >= MAX_OPEN_TRADES:
            return False, "Max open trades reached"

        deployed = sum(t["entry"] * t["qty"] for t in open_trades)

        if deployed + required_capital > capital * MAX_CAPITAL_UTILIZATION:
            return False, "Capital utilization exceeded"

        return True, "OK"
