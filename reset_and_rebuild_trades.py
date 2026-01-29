import os
import csv
import sqlite3
from datetime import datetime, date

# ---------------------------------------
# PROJECT IMPORTS
# ---------------------------------------
from db.TradeFriendTradeRepo import TradeFriendTradeRepo

# ---------------------------------------
# CONFIG
# ---------------------------------------
DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_trades.db")
CSV_FILE = "reports/swing_plans/active_trade_symbols_2026-01-29.csv"   # <-- put your CSV filename here

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
def rebuild_from_csv():
    if not os.path.exists(CSV_FILE):
        raise FileNotFoundError(f"CSV not found: {CSV_FILE}")

    trade_repo = TradeFriendTradeRepo()
    inserted = 0
    skipped = 0

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            trade = build_trade_from_csv(row)

            if not trade:
                skipped += 1
                continue

            try:
                trade_repo.save_trade(trade)
                inserted += 1
            except Exception as e:
                print(f"❌ Failed to insert {row['symbol']}: {e}")
                skipped += 1

    print("--------------------------------------------------")
    print(f"✅ Trades inserted : {inserted}")
    print(f"⚠️ Trades skipped  : {skipped}")
    print("--------------------------------------------------")


# ---------------------------------------
# MAIN
# ---------------------------------------
if __name__ == "__main__":
    print("🚀 Starting TradeFriend DB reset utility")

    # # Optional: inspect old data
    # read_existing_trades()

    # # Hard reset
    drop_db_file()

    # Rebuild using repo logic
    rebuild_from_csv()

    print("🎯 TradeFriend DB rebuild completed successfully")
