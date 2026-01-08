import sqlite3
import os
from datetime import datetime

DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_algo.db")


def cleanup_today_data():
    if not os.path.exists(DB_FILE):
        print("❌ Database not found:", DB_FILE)
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    today = datetime.now().strftime("%Y-%m-%d")

    print(f"🧹 Cleaning data for date: {today}")

    # -----------------------------
    # Delete today's watchlist
    # -----------------------------
    cursor.execute("""
        DELETE FROM tradefriend_watchlist
        WHERE date(scanned_on) < date('now', '-5 days');
    """)
    watchlist_deleted = cursor.rowcount

    # -----------------------------
    # Delete today's swing plans
    # -----------------------------
    cursor.execute("""
        DELETE FROM swing_trade_plans
        WHERE date(created_on) < date('now', '-5 days');
    """)
    plans_deleted = cursor.rowcount

    conn.commit()
    conn.close()

    print("✅ Cleanup completed")
    print(f"   • Watchlist rows deleted : {watchlist_deleted}")
    print(f"   • Swing plans deleted    : {plans_deleted}")

def remove_duplicate_rows():
    if not os.path.exists(DB_FILE):
        print("❌ Database not found:", DB_FILE)
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    print("🧹 Removing duplicate rows...")

    # Remove duplicates from watchlist
    cursor.execute("""
        DELETE FROM tradefriend_watchlist
        WHERE rowid NOT IN (
            SELECT MIN(rowid)
            FROM tradefriend_watchlist
            GROUP BY symbol, date(scanned_on)
        );
    """)
    watchlist_dupes = cursor.rowcount

    # Remove duplicates from swing trade plans
    cursor.execute("""
        DELETE FROM swing_trade_plans
        WHERE rowid NOT IN (
            SELECT MIN(rowid)
            FROM swing_trade_plans
            GROUP BY symbol, date(created_on)
        );
    """)
    swing_dupes = cursor.rowcount

    conn.commit()
    conn.close()

    print("✅ Duplicate cleanup completed")
    print(f"   • Watchlist duplicates removed : {watchlist_dupes}")
    print(f"   • Swing plan duplicates removed: {swing_dupes}")


if __name__ == "__main__":
    cleanup_today_data()
    remove_duplicate_rows()
