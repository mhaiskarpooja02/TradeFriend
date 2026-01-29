# debug_active_trades.py

from db.TradeFriendSwingPlanRepo import TradeFriendSwingPlanRepo
from utils.logger import get_logger

logger = get_logger(__name__)


def print_tradefriend_trades():
    trade_repo = TradeFriendSwingPlanRepo()

    rows = trade_repo.cursor.execute("""SELECT DISTINCT symbol
            FROM tradefriend_trades
            WHERE status IN ('OPEN', 'PARTIAL')
                                      """).fetchall()

# ,'EGSHP-EQ')
    print("\n================ ACTIVE TRADES DEBUG ================\n")
    print(f"Total active trades found: {len(rows)}\n")

    if not rows:
        print("❌ No trades with status OPEN / PARTIAL found")
        return

    for i, trade in enumerate(rows, start=1):
        trade_dict = dict(trade)

        print(f"--- Trade #{i} ---")
        for k, v in trade_dict.items():
            print(f"{k:20}: {v}")
        print("-" * 50)

    print("\n================ END =================\n")

def print_active_trades():
    trade_repo = TradeFriendSwingPlanRepo()

    rows = trade_repo.cursor.execute("""
      SELECT symbol,  COUNT(*) AS cnt
FROM swing_trade_plans
GROUP BY symbol, d;

    """).fetchall()

# ,'EGSHP-EQ')
    print("\n================ ACTIVE TRADES DEBUG ================\n")
    print(f"Total active trades found: {len(rows)}\n")

    if not rows:
        print("❌ No trades with status OPEN / PARTIAL found")
        return

    for i, trade in enumerate(rows, start=1):
        trade_dict = dict(trade)

        print(f"--- Trade #{i} ---")
        for k, v in trade_dict.items():
            print(f"{k:20}: {v}")
        print("-" * 50)

    print("\n================ END =================\n")


if __name__ == "__main__":
    # print_active_trades()
    print_tradefriend_trades()
