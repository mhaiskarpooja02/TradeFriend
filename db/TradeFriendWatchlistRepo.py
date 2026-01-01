import sqlite3
import os


DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_algo.db")

os.makedirs(DB_FOLDER, exist_ok=True)


class TradeFriendWatchlistRepo:
    def __init__(self):
        self.conn = sqlite3.connect(
            DB_FILE,
            check_same_thread=False
        )
        self.conn.row_factory = sqlite3.Row
        self._create_table()

    # ---------------- Schema ----------------

    def _create_table(self):
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS tradefriend_watchlist (
            symbol TEXT PRIMARY KEY,
            strategy TEXT,
            bias TEXT,
            scanned_on TEXT,
            status TEXT
        )
        """)
        self.conn.commit()

    # ---------------- Write ----------------

    def upsert(self, record: dict):
        """
        record = {
            symbol: str,
            strategy: str,
            bias: str
        }
        """

        self.conn.execute("""
        INSERT INTO tradefriend_watchlist
            (symbol, strategy, bias, scanned_on, status)
        VALUES
            (?, ?, ?, datetime('now'), 'WATCH')
        ON CONFLICT(symbol) DO UPDATE SET
            strategy   = excluded.strategy,
            bias       = excluded.bias,
            scanned_on = datetime('now'),
            status     = 'WATCH'
        """, (
            record["symbol"],
            record["strategy"],
            record["bias"]
        ))

        self.conn.commit()

    # ---------------- Read ----------------

    def fetch_all(self):
        cursor = self.conn.execute("""
            SELECT *
            FROM tradefriend_watchlist
            WHERE status = 'WATCH'
            ORDER BY scanned_on DESC
        """)
        return cursor.fetchall()
