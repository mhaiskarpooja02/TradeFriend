import os
import csv
import sqlite3
from datetime import datetime, date

# ---------------------------------------
# PROJECT IMPORTS
# ---------------------------------------
from db.TradeFriendSwingPlanRepo import TradeFriendSwingPlanRepo
from db.TradeFriendTradeRepo import TradeFriendTradeRepo

# ---------------------------------------
# CONFIG
# ---------------------------------------
DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_trades.db")
CSV_FILE = "reports/swing_plans/active_trade_symbolsfulldata_2026-02-04.csv"   # <-- put your CSV filename here

os.makedirs(DB_FOLDER, exist_ok=True)


# ---------------------------------------
# STEP 1: READ EXISTING DATA (OPTIONAL)
# ---------------------------------------
def read_existing_trades():
    if not os.path.exists(DB_FILE):
        print("ℹ️ No existing DB found")
        return []

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        rows = cursor.execute("SELECT * FROM tradefriend_trades").fetchall()
        print(f"📦 Existing trades found: {len(rows)}")
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        print("⚠️ Table not found, skipping read")
        return []
    finally:
        conn.close()


# ---------------------------------------
# STEP 2: DROP DB FILE
# ---------------------------------------
def drop_db_file():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        print("✅ Old DB file deleted")
    else:
        print("ℹ️ No DB file to delete")


# ---------------------------------------
# STEP 3: BUILD TRADE DICT FROM CSV ROW
# ---------------------------------------
def build_trade_from_csv(row: dict) -> dict:
    """
    Convert CSV row → trade dict expected by save_trade()
    Assumption:
    - All trades are BUY
    - Only OPEN / PARTIAL rows are restored
    """

    status = row["status"].strip().upper()
    if status not in ("OPEN", "PARTIAL"):
        return None

    trade = {
        "symbol": row["symbol"],
        "entry": float(row["entry"]),
        "sl": float(row["sl"]),
        "target": float(row["target"]),
        "qty": int(row["qty"]),
        "confidence": float(row.get("confidence", 0)),
        # side intentionally omitted → treated as BUY by system
    }

    return trade


# ---------------------------------------
# STEP 4: READ CSV + REBUILD DB
# ---------------------------------------
def rebuild_trades_from_csv():
    drop_db_file()

    trade_repo = TradeFriendTradeRepo()
    plan_repo = TradeFriendSwingPlanRepo()

    inserted = 0
    skipped = 0

    # 🔁 Hold all inserted trades in memory
    inserted_trades = []   # [{trade_id, plan_id, symbol}]

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            status = row["status"].strip().upper()
            if status not in ("OPEN", "PARTIAL"):
                continue

            symbol = row["symbol"]

            # STEP 1: resolve plan_id
            # plan_id = plan_repo.get_latest_approved_plan_id_by_symbol(symbol)
            # if not plan_id:
            #     print(f"⚠️ No active plan found for {symbol}, skipping")
            #     skipped += 1
            #     continue

            trade = {
                "id": int(row["id"]),                          # optional but recommended
                "swing_plan_id": int(row["swing_plan_id"]),
                "symbol": row["symbol"],
                "side": row["side"],

                "planned_entry": float(row["entry"]),          # OK for rebuild
                "entry": float(row["entry"]),
                "sl": float(row["sl"]),
                "trailing_sl": float(row["trailing_sl"]),
                "target": float(row["target"]),

                "qty": int(row["qty"]),
                "initial_qty": int(row["initial_qty"]),
                "remaining_qty": int(row["remaining_qty"]),

                "position_value": float(row["position_value"]),
                "risk_amount": float(row["risk_amount"]),

                "confidence": float(row["confidence"]),
                "status": row["status"],
                "hold_mode": int(row["hold_mode"]),

                "entry_day": row["entry_day"],
                "created_on": row["created_on"],
                "updated_at": row["updated_at"],
            }

            # STEP 2: insert trade
            trade_id = trade_repo.rebuild_trade(trade)

            # inserted_trades.append({
            #     "trade_id": trade_id,
            #     "plan_id": plan_id,
            #     "symbol": symbol,
            # })

            inserted += 1

    # --------------------------------------------------
    # PHASE 2: MARK ALL PLANS AS TRIGGERED
    # --------------------------------------------------
  

    print("------------------------------------------------")
    print(f"✅ Trades rebuilt           : {inserted}")
    print(f"⚠️ Trades skipped           : {skipped}")
    print(f"🎯 Plans triggered          : {len(inserted_trades)}")
    print("------------------------------------------------")

def trigger_plans_from_trade_table():
    """
    Reads all OPEN / PARTIAL trades from tradefriend_trades
    and marks corresponding swing plans as triggered.
    """

    if not os.path.exists(DB_FILE):
        raise FileNotFoundError(f"Database not found: {DB_FILE}")

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    rows = cursor.execute("""
        SELECT swing_plan_id,rowid, id
        FROM tradefriend_trades
        WHERE status IN ('OPEN', 'PARTIAL')
        ORDER BY symbol
    """).fetchall()

    conn.close()

    if not rows:
        print("⚠️ No active trades found")
        return

    plan_repo = TradeFriendSwingPlanRepo()

    triggered = 0
    seen_plans = set()

    for r in rows:
        plan_id = r["swing_plan_id"]

        # 🔒 Avoid triggering same plan multiple times
        if plan_id in seen_plans:
            continue

        plan_repo.mark_triggered_by_Planid(plan_id)
        seen_plans.add(plan_id)
        triggered += 1

    print("------------------------------------------------")
    print(f"🎯 Plans triggered from trades : {triggered}")
    print("------------------------------------------------")

# ---------------------------------------
# MAIN
# ---------------------------------------
if __name__ == "__main__":
    print("🚀 Rebuilding trades with symbol → plan mapping")
    rebuild_trades_from_csv()
    print("🎯 Done")