# reports/generate_eod_csv_reports.py

import os
import csv
import sqlite3
from datetime import datetime

# =====================================================
# CONFIG
# =====================================================
BASE_DB_FOLDER = "dbdata"
REPORT_BASE_DIR = "reports"


REALIZED_DB = os.path.join(BASE_DB_FOLDER, "tradefriend_realized_pnl.db")
AUDIT_DB = os.path.join(BASE_DB_FOLDER, "tradefriend_order_audit.db")
HISTORY_DB = os.path.join(BASE_DB_FOLDER, "tradefriend_trade_history.db")


# =====================================================
# UTILITY
# =====================================================
def ensure_report_folder():
    today = datetime.now().strftime("%Y-%m-%d")
    folder = os.path.join(REPORT_BASE_DIR, today)
    os.makedirs(folder, exist_ok=True)
    return folder


def export_table_to_csv(db_path, query, output_file):
    if not os.path.exists(db_path):
        print(f"DB not found: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    rows = cur.execute(query).fetchall()

    if not rows:
        print(f"No data for {output_file}")
        conn.close()
        return

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        headers = rows[0].keys()
        writer.writerow(headers)

        for row in rows:
            writer.writerow([row[h] for h in headers])

    conn.close()
    print(f"Generated → {output_file}")


# =====================================================
# REPORTS
# =====================================================
def generate_realized_pnl_report(report_dir):
    today = datetime.now().strftime("%Y-%m-%d")

    query = """
        SELECT *
        FROM tradefriend_realized_pnl
        WHERE exit_date = ?
        ORDER BY exit_time DESC
    """

    output_file = os.path.join(report_dir, "realized_pnl.csv")

    conn = sqlite3.connect(REALIZED_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    rows = cur.execute(query, (today,)).fetchall()

    if not rows:
        print("No realized PnL today.")
        conn.close()
        return

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        headers = rows[0].keys()
        writer.writerow(headers)
        for row in rows:
            writer.writerow([row[h] for h in headers])

    conn.close()
    print("Realized PnL report created.")


def generate_order_audit_report(report_dir):
    today = datetime.now().strftime("%Y-%m-%d")

    query = """
        SELECT *
        FROM tradefriend_order_audit
        WHERE date(created_on) = ?
        ORDER BY created_on DESC
    """

    output_file = os.path.join(report_dir, "order_audit.csv")
    export_table_to_csv(AUDIT_DB, query.replace("?", f"'{today}'"), output_file)


def generate_closed_trade_report(report_dir):
    today = datetime.now().strftime("%Y-%m-%d")

    query = """
        SELECT *
        FROM tradefriend_trade_history
        WHERE date(closed_on) = ?
        ORDER BY closed_on DESC
    """

    output_file = os.path.join(report_dir, "closed_trades.csv")
    export_table_to_csv(HISTORY_DB, query.replace("?", f"'{today}'"), output_file)


def generate_summary_report(report_dir):
    today = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect(REALIZED_DB)
    cur = conn.cursor()

    row = cur.execute("""
        SELECT
            COUNT(*) as total_exits,
            ROUND(SUM(pnl_amount),2) as total_pnl
        FROM tradefriend_realized_pnl
        WHERE exit_date = ?
    """, (today,)).fetchone()

    conn.close()

    output_file = os.path.join(report_dir, "summary.csv")

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "total_exits", "total_pnl"])
        writer.writerow([
            today,
            row[0] if row else 0,
            row[1] if row and row[1] else 0
        ])

    print("Summary report created.")


# =====================================================
# MAIN RUNNER
# =====================================================
def run():
    print("Generating EOD CSV Reports...")

    report_dir = ensure_report_folder()

    generate_realized_pnl_report(report_dir)
    generate_order_audit_report(report_dir)
    generate_closed_trade_report(report_dir)
    generate_summary_report(report_dir)

    print("All reports generated successfully.")


if __name__ == "__main__":
    run()
