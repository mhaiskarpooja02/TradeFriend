from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from db.TradeFriendWatchlistRepo import TradeFriendWatchlistRepo
from db.TradeFriendSwingPlanRepo import TradeFriendSwingPlanRepo
from db.TradeFriendSettingsRepo import TradeFriendSettingsRepo
from datetime import datetime

def reset_trades():
    trade_repo = TradeFriendTradeRepo()
    settings_repo = TradeFriendSettingsRepo()

    open_trades = trade_repo.fetch_open_trades()

    print(f"🔄 Archiving {len(open_trades)} active trades")

    for trade in open_trades:
        position_value = trade["position_value"] or 0.0  # 🔐 SAFETY

        # restore capital ONLY if value exists
        if position_value > 0:
            settings_repo.adjust_available_swing_capital(position_value)

        trade_repo.history_repo.archive_trade(
            trade=trade,
            exit_price=trade["entry"],
            exit_reason="SYSTEM_RESET",
            closed_on=datetime.now().isoformat()
        )

    # wipe active trades
    trade_repo.cursor.execute("DELETE FROM tradefriend_trades")
    trade_repo.conn.commit()

    print("✅ Active trades cleared")


def reset_watchlist_and_plans():
    watchlist_repo = TradeFriendWatchlistRepo()
    plan_repo = TradeFriendSwingPlanRepo()

    watchlist_repo.conn.execute("DELETE FROM tradefriend_watchlist")
    watchlist_repo.conn.commit()

    watchlist_repo.conn.execute("DROP TABLE tradefriend_watchlist;")
    watchlist_repo.conn.commit()
    
    plan_repo.conn.execute("DELETE FROM swing_trade_plans")
    plan_repo.conn.commit()

    print("✅ Watchlist & swing plans cleared")


if __name__ == "__main__":
    print("🚨 FULL SYSTEM RESET STARTED")
    reset_trades()
    reset_watchlist_and_plans()
    print("🎯 RESET COMPLETE — READY FOR FRESH RUN")
