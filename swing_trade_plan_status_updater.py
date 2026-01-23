import sqlite3
import os
import csv
from datetime import datetime

# --------------------------------------------------
# DB CONFIG
# --------------------------------------------------
DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_algo.db")

# --------------------------------------------------
# UPDATER CLASS
# --------------------------------------------------
class SwingTradePlanStatusUpdater:
    def __init__(self, db_file=DB_FILE):
        if not os.path.exists(db_file):
            raise FileNotFoundError(f"Database not found: {db_file}")
        self.db_file = db_file

    def update_status_from_csv(self, csv_path, new_status="PLANNED"):
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV not found: {csv_path}")

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        updated = 0
        skipped = 0

        with open(csv_path, mode="r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                plan_id = row.get("id")

                if not plan_id:
                    skipped += 1
                    continue

                cursor.execute(
                    """
                    UPDATE swing_trade_plans
                    SET status = ?, triggered_on = ?
                    WHERE id = ?
                    """,
                    (
                        new_status,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        plan_id
                    )
                )

                if cursor.rowcount > 0:
                    updated += 1
                else:
                    skipped += 1

        conn.commit()
        conn.close()

        print("===================================")
        print(" Swing Trade Plan Status Update ")
        print("===================================")
        print(f"✅ Updated rows : {updated}")
        print(f"⚠️ Skipped rows : {skipped}")
        print("===================================")


# --------------------------------------------------
# MANUAL RUN
# --------------------------------------------------
if __name__ == "__main__":
    updater = SwingTradePlanStatusUpdater()

    # 🔽 CHANGE CSV PATH IF NEEDED
    csv_file_path = "reports/swing_plans/swing_trade_actual_2026-01-23_planned.csv"

    updater.update_status_from_csv(
        csv_path=csv_file_path,
        new_status="PLANNED"
    )
