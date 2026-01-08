# db/TradeFriendTradeHistoryRepo.py

import sqlite3
import os
from datetime import datetime

DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_trade_history.db")
os.makedirs(DB_FOLDER, exist_ok=True)


class TradeFriendTradeHistoryRepo:
    """
    PURPOSE:
    - Persist CLOSED / ARCHIVED trades
    - Immutable historical record
    """

    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        self._ensure_table()

    # -------------------------------------------------
    # TABLE
    # -------------------------------------------------
    def _ensure_table(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS tradefriend_trade_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                symbol TEXT,
                entry REAL,
                sl REAL,
                target REAL,

                qty INTEGER,
                initial_qty INTEGER,

                exit_price REAL,
                exit_reason TEXT,

                position_value REAL,
                risk_amount REAL,

                confidence REAL,
                status TEXT,

                entry_day TEXT,
                created_on TEXT,
                closed_on TEXT
            )
        """)
        self.conn.commit()

    # -------------------------------------------------
    # ARCHIVE
    # -------------------------------------------------
    def archive_trade(
        self,
        trade,
        exit_price: float,
        exit_reason: str,
        closed_on: str | None = None
    ):
        if not trade:
            return

        self.cursor.execute("""
            INSERT INTO tradefriend_trade_history (
                symbol, entry, sl, target,
                qty, initial_qty,
                exit_price, exit_reason,
                position_value, risk_amount,
                confidence, status,
                entry_day, created_on, closed_on
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade["symbol"],
            trade["entry"],
            trade["sl"],
            trade["target"],
            trade["qty"],
            trade["initial_qty"],
            exit_price,
            exit_reason,
            trade["position_value"],
            trade["risk_amount"],
            trade["confidence"],
            exit_reason,                # final status
            trade["entry_day"],
            trade["created_on"],
            closed_on or datetime.now().isoformat()
        ))

        self.conn.commit()

    # -------------------------------------------------
    # FETCH (Dashboard)
    # -------------------------------------------------
    def fetch_recent_closed(self, limit: int = 50):
        self.cursor.execute("""
            SELECT *
            FROM tradefriend_trade_history
            ORDER BY closed_on DESC
            LIMIT ?
        """, (limit,))
        return self.cursor.fetchall()
