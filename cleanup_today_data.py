import sqlite3
import os
from datetime import date, datetime

DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_algo.db")
DBTrade_FILE= os.path.join(DB_FOLDER, "tradefriend_trades.db")


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
        WHERE date(scanned_on) < date('now', '-3 days');
    """)
    watchlist_deleted = cursor.rowcount

    # -----------------------------
    # Delete today's swing plans
    # -----------------------------
    cursor.execute("""
        DELETE FROM swing_trade_plans
        WHERE date(created_on) < date('now', '-3 days');
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

def delete_trades_by_ids(ids):
    if not ids:
        print("⚠️ No trades found for today. Nothing to delete.")
        return

    conn = sqlite3.connect(DBTrade_FILE)
    cursor = conn.cursor()

    placeholders = ",".join("?" for _ in ids)

    cursor.execute(
        f"DELETE FROM tradefriend_trades WHERE id IN ({placeholders});",
        ids
    )

    deleted = cursor.rowcount
    conn.commit()
    conn.close()

    print(f"✅ Trades deleted using ID match: {deleted}")

def get_todays_trade_ids():
    conn = sqlite3.connect(DBTrade_FILE)
    cursor = conn.cursor()

    today = date.today().isoformat()

    cursor.execute("""
        SELECT id, created_on, typeof(created_on)
        FROM tradefriend_trades
        WHERE CAST(created_on AS TEXT) LIKE ?;
    """, (f"{today}%",))

    rows = cursor.fetchall()
    conn.close()

    for r in rows:
        print(r)

    return [r[0] for r in rows]

def mark_todays_plans_as_planned():
    if not os.path.exists(DB_FILE):
        print("❌ Database not found:", DB_FILE)
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    print("📝 Marking today's swing plans as PLANNED...")

    cursor.execute("""
        UPDATE swing_trade_plans
        SET status = 'PLANNED'
        WHERE date(created_on) = date('now');
    """)

    updated = cursor.rowcount
    conn.commit()
    conn.close()

    print("✅ Status update completed")
    print(f"   • Rows updated to PLANNED : {updated}")

def delete_by_symbols(symbols):
    """
    Delete rows from:
    - swing_trade_plans
    - tradefriend_watchlist
    - tradefriend_trades
    based on symbol list
    """

    if not symbols:
        print("⚠️ No symbols provided. Nothing to delete.")
        return

    placeholders = ",".join("?" for _ in symbols)

    # -----------------------------
    # DB_FILE (plans + watchlist)
    # -----------------------------
    if not os.path.exists(DB_FILE):
        print("❌ Database not found:", DB_FILE)
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        f"DELETE FROM swing_trade_plans WHERE symbol IN ({placeholders});",
        symbols
    )
    plans_deleted = cursor.rowcount

    cursor.execute(
        f"DELETE FROM tradefriend_watchlist WHERE symbol IN ({placeholders});",
        symbols
    )
    watchlist_deleted = cursor.rowcount

    conn.commit()
    conn.close()

    # -----------------------------
    # DBTrade_FILE (trades)
    # -----------------------------
    if not os.path.exists(DBTrade_FILE):
        print("❌ Trade DB not found:", DBTrade_FILE)
        return

    conn = sqlite3.connect(DBTrade_FILE)
    cursor = conn.cursor()

    cursor.execute(
        f"DELETE FROM tradefriend_trades WHERE symbol IN ({placeholders});",
        symbols
    )
    trades_deleted = cursor.rowcount

    conn.commit()
    conn.close()

    # -----------------------------
    # Summary
    # -----------------------------
    print("🧹 Symbol-based cleanup completed")
    print(f"   • Swing plans deleted    : {plans_deleted}")
    print(f"   • Watchlist rows deleted : {watchlist_deleted}")
    print(f"   • Trades deleted         : {trades_deleted}")

    # -----------------------------
    # Summary
    # -----------------------------
    
# ==================================================
# LTP VALIDATION
# ==================================================
def validate_symbol_ltp_ready(provider, symbol, rejected):
    """
    READY-stage LTP validation.
    Returns LTP or None
    """
    try:
        ltp = provider.get_ltp_byLtp(symbol)

        if ltp is None or not isinstance(ltp, (int, float)) or ltp <= 0:
            rejected.append({
                "symbol": symbol,
                "reason": "Invalid LTP at READY stage"
            })
            return None

        return ltp

    except Exception:
        rejected.append({
            "symbol": symbol,
            "reason": "LTP validation error"
        })
        return None


# ==================================================
# DELETE BY SYMBOLS (UNCHANGED LOGIC, CLEANED)
# ==================================================
def delete_by_symbols(symbols):
    if not symbols:
        print("⚠️ No symbols provided. Nothing to delete.")
        return

    placeholders = ",".join("?" for _ in symbols)

    # ---------- MAIN DB ----------
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        f"DELETE FROM swing_trade_plans WHERE symbol IN ({placeholders});",
        symbols
    )
    plans_deleted = cursor.rowcount

    cursor.execute(
        f"DELETE FROM tradefriend_watchlist WHERE symbol IN ({placeholders});",
        symbols
    )
    watchlist_deleted = cursor.rowcount

    conn.commit()
    conn.close()

    # ---------- TRADE DB ----------
    conn = sqlite3.connect(DBTrade_FILE)
    cursor = conn.cursor()

    cursor.execute(
        f"DELETE FROM tradefriend_trades WHERE symbol IN ({placeholders});",
        symbols
    )
    trades_deleted = cursor.rowcount

    conn.commit()
    conn.close()

    print("🧹 Symbol-based cleanup completed")
    print(f"   • Swing plans deleted    : {plans_deleted}")
    print(f"   • Watchlist rows deleted : {watchlist_deleted}")
    print(f"   • Trades deleted         : {trades_deleted}")


# ==================================================
# MAIN ORCHESTRATOR (ONLY FUNCTION YOU CALL)
# ==================================================
def validate_watchlist_symbols_and_cleanup(provider):
    """
    1. Load watchlist symbols
    2. Validate LTP
    3. Collect invalid symbols
    4. Delete them from all tables
    """

    if not os.path.exists(DB_FILE):
        print("❌ Database not found:", DB_FILE)
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT symbol FROM tradefriend_watchlist;")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("⚠️ Watchlist is empty")
        return

    rejected = []
    symbols_to_delete = []

    print(f"🔍 Validating {len(rows)} watchlist symbols...")

    for (symbol,) in rows:
        ltp = validate_symbol_ltp_ready(provider, symbol, rejected)

        if ltp is None:
            symbols_to_delete.append(symbol)

    symbols_to_delete = list(set(symbols_to_delete))  # dedupe

    if symbols_to_delete:
        print("🧹 Symbols to delete:")
        for s in symbols_to_delete:
            print("   •", s)

        delete_by_symbols(symbols_to_delete)
    else:
        print("✅ No invalid symbols found")

    print("✅ Validation + cleanup completed")
if __name__ == "__main__":
    #  cleanup_today_data()
    # remove_duplicate_rows()

    # ids = get_todays_trade_ids()
    # delete_trades_by_ids(ids)
    # delete_todays_trades()

     mark_todays_plans_as_planned()

    # symbols_to_delete = [
    #     "NACLIND-EQ",
    #     "VENUSREM-EQ"
        
    # ]

    # delete_by_symbols(symbols_to_delete)
    # from core.TradeFriendDataProvider import TradeFriendDataProvider

    # provider = TradeFriendDataProvider()
    # validate_watchlist_symbols_and_cleanup(provider)
