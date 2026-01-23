import sqlite3
import os
import csv
from datetime import datetime

# --------------------------------------------------
# DB CONFIG
# --------------------------------------------------
DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_trades.db")
DBSwinggPlan_FILE = os.path.join(DB_FOLDER, "tradefriend_algo.db")

# --------------------------------------------------
# OUTPUT CONFIG
# --------------------------------------------------
REPORT_FOLDER = "reports/swing_plans"
os.makedirs(REPORT_FOLDER, exist_ok=True)

# --------------------------------------------------
# EXPORT LOGIC
# --------------------------------------------------
def export_tradefriend_trades_plans():
    if not os.path.exists(DB_FILE):
        raise FileNotFoundError(f"Database not found: {DB_FILE}")

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM tradefriend_trades
        ORDER BY created_on DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("⚠️ No records found")
        return

    # CSV PATH
    today = datetime.now().strftime("%Y-%m-%d")
    csv_path = os.path.join(
        REPORT_FOLDER,
        f"swing_trade_actual_{today}.csv"
    )

    # Write CSV
    with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Header
        writer.writerow(rows[0].keys())

        # Data
        for row in rows:
            writer.writerow(list(row))

    print(f"✅ Exported {len(rows)} records → {csv_path}")

def export_swing_trade_plans():
    if not os.path.exists(DBSwinggPlan_FILE):
        raise FileNotFoundError(f"Database not found: {DBSwinggPlan_FILE}")

    conn = sqlite3.connect(DBSwinggPlan_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM swing_trade_plans
        WHERE status != 'REJECTED'
        AND date(created_on) = date('now')
        ORDER BY created_on DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("⚠️ No records found")
        return

    # CSV PATH
    today = datetime.now().strftime("%Y-%m-%d")
    csv_path = os.path.join(
        REPORT_FOLDER,
        f"swing_trade_actual_{today}.csv"
    )

    # Write CSV
    with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Header
        writer.writerow(rows[0].keys())

        # Data
        for row in rows:
            writer.writerow(list(row))

    print(f"✅ Exported {len(rows)} records → {csv_path}")

# --------------------------------------------------
# MANUAL RUN
# --------------------------------------------------
if __name__ == "__main__":
    export_swing_trade_plans()
