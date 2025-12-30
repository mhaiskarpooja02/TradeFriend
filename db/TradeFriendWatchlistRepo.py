import sqlite3
import os

# DB path
DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_algo.db")

# Ensure db folder exists
os.makedirs(DB_FOLDER, exist_ok=True)

class TradeFriendWatchlistRepo:
    def __init__(self, db):
        self.db = db
        self._create_table()

    def _create_table(self):
        self.db.execute("""
        CREATE TABLE IF NOT EXISTS tradefriend_watchlist (
            symbol TEXT PRIMARY KEY,
            strategy TEXT,
            bias TEXT,
            scanned_on TEXT,
            status TEXT
        )
        """)

    def upsert(self, record):
        self.db.execute("""
        INSERT INTO tradefriend_watchlist
        (symbol, strategy, bias, scanned_on, status)
        VALUES (?, ?, ?, datetime('now'), ?)
        ON CONFLICT(symbol) DO UPDATE SET
            strategy=excluded.strategy,
            bias=excluded.bias,
            scanned_on=datetime('now'),
            status=excluded.status
        """, (
            record["symbol"],
            record["strategy"],
            record["bias"],
            "WATCH"
        ))

    def fetch_all(self):
        return self.db.fetchall("""
            SELECT * FROM tradefriend_watchlist
            WHERE status='WATCH'
        """)
