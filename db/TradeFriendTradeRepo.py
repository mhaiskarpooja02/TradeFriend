import sqlite3
import os
from datetime import datetime, date


DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_trades.db")
os.makedirs(DB_FOLDER, exist_ok=True)


class TradeFriendTradeRepo:
    """
    PURPOSE:
    - Persist swing trades
    - Provide exposure stats to RiskManager
    - Serve dashboard & lifecycle operations
    """

    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        self._ensure_table()
        self._ensure_columns()

    # -------------------------------------------------
    # TABLE & MIGRATION
    # -------------------------------------------------
    def _ensure_table(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS tradefriend_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                symbol TEXT NOT NULL,
                entry REAL NOT NULL,
                sl REAL NOT NULL,
                trailing_sl REAL,
                target REAL NOT NULL,

                qty INTEGER NOT NULL,
                initial_qty INTEGER,

                position_value REAL,
                risk_amount REAL,

                confidence REAL DEFAULT 0,
                status TEXT DEFAULT 'OPEN',

                hold_mode INTEGER DEFAULT 0,
                entry_day TEXT,

                created_on TEXT,
                closed_on TEXT
            )
        """)
        self.conn.commit()

    def _ensure_columns(self):
        self._add_column("position_value", "REAL")
        self._add_column("risk_amount", "REAL")
        self._add_column("trailing_sl", "REAL")
        self._add_column("initial_qty", "INTEGER")
        self._add_column("hold_mode", "INTEGER DEFAULT 0")
        self._add_column("entry_day", "TEXT")
        self._add_column("closed_on", "TEXT")

    def _add_column(self, column, col_type):
        try:
            self.cursor.execute(
                f"ALTER TABLE tradefriend_trades ADD COLUMN {column} {col_type}"
            )
            self.conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists

    # -------------------------------------------------
    # CREATE TRADE (DecisionEngine ENTRY)
    # -------------------------------------------------
    def save_trade(self, trade: dict):
        """
        trade MUST contain:
        symbol, entry, sl, target, qty,
        position_value, confidence
        """

        self.cursor.execute("""
            INSERT INTO tradefriend_trades (
                symbol, entry, sl, trailing_sl,
                target, qty, initial_qty,
                position_value, risk_amount,
                confidence, status,
                hold_mode, entry_day,
                created_on
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', 0, ?, ?)
        """, (
            trade["symbol"],
            trade["entry"],
            trade["sl"],
            trade["sl"],                 # trailing_sl starts same as SL
            trade["target"],
            trade["qty"],
            trade["qty"],                # initial_qty
            trade.get("position_value"),
            trade.get("risk_amount"),
            trade.get("confidence", 0),
            date.today().isoformat(),
            datetime.now().isoformat()
        ))

        self.conn.commit()

    # -------------------------------------------------
    # RISK MANAGER SUPPORT
    # -------------------------------------------------
    def count_open_trades(self) -> int:
        cur = self.cursor.execute("""
            SELECT COUNT(*)
            FROM tradefriend_trades
            WHERE status = 'OPEN'
        """)
        return cur.fetchone()[0]

    def sum_open_position_value(self) -> float:
        cur = self.cursor.execute("""
            SELECT COALESCE(SUM(position_value), 0)
            FROM tradefriend_trades
            WHERE status = 'OPEN'
        """)
        return float(cur.fetchone()[0])

    # -------------------------------------------------
    # FETCH
    # -------------------------------------------------
    def fetch_open_trades(self):
        self.cursor.execute("""
            SELECT *
            FROM tradefriend_trades
            WHERE status IN ('OPEN', 'PARTIAL')
        """)
        return self.cursor.fetchall()

    # -------------------------------------------------
    # PARTIAL EXIT
    # -------------------------------------------------
    def partial_exit(self, trade_id: int, exit_qty: int):
        """
        Reduce quantity safely and mark trade PARTIAL
        """
        self.cursor.execute("""
            UPDATE tradefriend_trades
            SET 
                qty = qty - ?,
                status = 'PARTIAL'
            WHERE id = ?
              AND qty > ?
        """, (exit_qty, trade_id, exit_qty))
        self.conn.commit()

    # -------------------------------------------------
    # HOLD MODE
    # -------------------------------------------------
    def enable_hold_mode(self, trade_id: int):
        self.cursor.execute("""
            UPDATE tradefriend_trades
            SET hold_mode = 1
            WHERE id = ?
        """, (trade_id,))
        self.conn.commit()

    # -------------------------------------------------
    # SL / TRAILING SL
    # -------------------------------------------------
    def update_sl(self, trade_id: int, new_sl: float):
        self.cursor.execute("""
            UPDATE tradefriend_trades
            SET 
                sl = ?,
                trailing_sl = ?
            WHERE id = ?
        """, (new_sl, new_sl, trade_id))
        self.conn.commit()

    # -------------------------------------------------
    # CLOSE TRADE
    # -------------------------------------------------
    def close_trade(self, trade_id: int, status: str):
        """
        status examples:
        CLOSED / SL / TARGET / MANUAL
        """
        self.cursor.execute("""
            UPDATE tradefriend_trades
            SET 
                status = ?,
                closed_on = ?
            WHERE id = ?
        """, (status, datetime.now().isoformat(), trade_id))
        self.conn.commit()

    # -------------------------------------------------
    # DASHBOARD
    # -------------------------------------------------
    def fetch_recent_with_pnl(self, limit: int = 50):
        """
        PnL should be derived in UI layer
        """
        self.cursor.execute("""
            SELECT *
            FROM tradefriend_trades
            ORDER BY created_on DESC
            LIMIT ?
        """, (limit,))
        return self.cursor.fetchall()
