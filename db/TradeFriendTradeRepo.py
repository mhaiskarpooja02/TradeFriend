import sqlite3
import os
from datetime import datetime, date
from db.TradeFriendTradeHistoryRepo import TradeFriendTradeHistoryRepo
from db.TradeFriendSettingsRepo import TradeFriendSettingsRepo

DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_trades.db")
os.makedirs(DB_FOLDER, exist_ok=True)


class TradeFriendTradeRepo:
    """
    PURPOSE:
    - Persist ACTIVE swing trades only
    - Lock / Release swing capital safely
    - Handle partial exits
    - Archive trades on final exit
    """

    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        self._ensure_table()
        self._ensure_columns()

        self.history_repo = TradeFriendTradeHistoryRepo()
        self.settings_repo = TradeFriendSettingsRepo()

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
                initial_qty INTEGER NOT NULL,

                position_value REAL NOT NULL,
                risk_amount REAL,

                confidence REAL DEFAULT 0,
                status TEXT DEFAULT 'OPEN',

                hold_mode INTEGER DEFAULT 0,
                entry_day TEXT,

                created_on TEXT
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

    def _add_column(self, column, col_type):
        try:
            self.cursor.execute(
                f"ALTER TABLE tradefriend_trades ADD COLUMN {column} {col_type}"
            )
            self.conn.commit()
        except sqlite3.OperationalError:
            pass

    # -------------------------------------------------
    # CREATE TRADE (LOCK CAPITAL ATOMICALLY)
    # -------------------------------------------------
    def save_trade(self, trade: dict):
        """
        Insert ACTIVE trade and LOCK swing capital
        (capital is locked BEFORE insert for safety)
        """

        position_value = trade["entry"] * trade["qty"]
        risk_amount = abs(trade["entry"] - trade["sl"]) * trade["qty"]

        # 🔒 LOCK FIRST (fail-safe)
        self.settings_repo.adjust_available_swing_capital(-position_value)

        try:
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
                trade["sl"],
                trade["target"],
                trade["qty"],
                trade["qty"],
                position_value,
                risk_amount,
                trade.get("confidence", 0),
                date.today().isoformat(),
                datetime.now().isoformat()
            ))
            self.conn.commit()

        except Exception:
            # 🔁 rollback capital if insert fails
            self.settings_repo.adjust_available_swing_capital(+position_value)
            raise

    # -------------------------------------------------
    # RISK MANAGER SUPPORT
    # -------------------------------------------------
    def count_open_trades(self) -> int:
        cur = self.cursor.execute("""
            SELECT COUNT(*)
            FROM tradefriend_trades
            WHERE status IN ('OPEN', 'PARTIAL')
        """)
        return cur.fetchone()[0]

    def sum_open_position_value(self) -> float:
        cur = self.cursor.execute("""
            SELECT COALESCE(SUM(position_value), 0)
            FROM tradefriend_trades
            WHERE status IN ('OPEN', 'PARTIAL')
        """)
        return float(cur.fetchone()[0])

    # -------------------------------------------------
    # FETCH
    # -------------------------------------------------
    def fetch_open_trades(self):
        return self.cursor.execute("""
            SELECT *
            FROM tradefriend_trades
            WHERE status IN ('OPEN', 'PARTIAL')
        """).fetchall()

    def fetch_active_trades(self, limit: int = 100):
        return self.cursor.execute("""
            SELECT *
            FROM tradefriend_trades
            WHERE status IN ('OPEN', 'PARTIAL')
            ORDER BY created_on DESC
            LIMIT ?
        """, (limit,)).fetchall()

    def has_open_trade(self, symbol: str) -> bool:
        cur = self.cursor.execute("""
            SELECT 1
            FROM tradefriend_trades
            WHERE symbol = ?
              AND status IN ('OPEN', 'PARTIAL')
        """, (symbol,))
        return cur.fetchone() is not None

    # -------------------------------------------------
    # PARTIAL EXIT (RELEASE PROPORTIONAL CAPITAL)
    # -------------------------------------------------
    def partial_exit(self, trade_id: int, exit_qty: int):
        trade = self.cursor.execute(
            "SELECT * FROM tradefriend_trades WHERE id = ?",
            (trade_id,)
        ).fetchone()

        if not trade or exit_qty <= 0 or exit_qty >= trade["qty"]:
            return

        per_qty_value = trade["position_value"] / trade["initial_qty"]
        release_amount = per_qty_value * exit_qty

        # 🔓 RELEASE proportional capital
        self.settings_repo.adjust_available_swing_capital(release_amount)

        self.cursor.execute("""
            UPDATE tradefriend_trades
            SET
                qty = qty - ?,
                position_value = position_value - ?,
                status = 'PARTIAL'
            WHERE id = ?
        """, (exit_qty, release_amount, trade_id))

        self.conn.commit()

    # -------------------------------------------------
    # SL / TRAILING SL
    # -------------------------------------------------
    def update_sl(self, trade_id: int, new_sl: float):
        self.cursor.execute("""
            UPDATE tradefriend_trades
            SET sl = ?, trailing_sl = ?
            WHERE id = ?
        """, (new_sl, new_sl, trade_id))
        self.conn.commit()

    # -------------------------------------------------
    # FINAL EXIT (RELEASE + ARCHIVE)
    # -------------------------------------------------
    def close_and_archive(self, trade_row, exit_price: float, exit_reason: str):
        """
        FINAL lifecycle step:
        - Release remaining capital
        - Archive trade
        - Remove from active table
        """

        if not trade_row:
            return

        # 🔓 RELEASE remaining capital (always exact)
        remaining_value = trade_row["position_value"]
        self.settings_repo.adjust_available_swing_capital(remaining_value)

        exit_time = datetime.now().isoformat()

        # 📦 ARCHIVE trade
        self.history_repo.archive_trade(
            trade=trade_row,
            exit_price=exit_price,
            exit_reason=exit_reason,
            closed_on=exit_time
        )

        # ❌ REMOVE from active table
        self.cursor.execute(
            "DELETE FROM tradefriend_trades WHERE id = ?",
            (trade_row["id"],)
        )
        self.conn.commit()

    # -------------------------------------------------
    # SYMBOL HELPERS (DASHBOARD / SCAN)
    # -------------------------------------------------
    def get_all_symbols(self) -> set:
        rows = self.cursor.execute("""
            SELECT DISTINCT symbol
            FROM tradefriend_trades
            WHERE status IN ('OPEN', 'PARTIAL')
        """).fetchall()
        return {r["symbol"] for r in rows}
