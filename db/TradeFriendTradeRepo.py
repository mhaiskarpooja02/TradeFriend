import sqlite3
import os
import logging
from datetime import datetime, date

from db.TradeFriendTradeHistoryRepo import TradeFriendTradeHistoryRepo
from db.TradeFriendSettingsRepo import TradeFriendSettingsRepo

logger = logging.getLogger(__name__)

DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_trades.db")
os.makedirs(DB_FOLDER, exist_ok=True)


class TradeFriendTradeRepo:
    """
    PURPOSE:
    - Persist ACTIVE trades only
    - Lock / release swing capital safely
    - Handle PARTIAL exits
    - Archive trades on FINAL exit
    """

    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        self._create_table()

        self.history_repo = TradeFriendTradeHistoryRepo()
        self.settings_repo = TradeFriendSettingsRepo()

    # -------------------------------------------------
    # TABLE (ACTIVE ONLY)
    # -------------------------------------------------
    def _create_table(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS tradefriend_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                symbol TEXT NOT NULL,
                side TEXT NOT NULL DEFAULT 'BUY',

                entry REAL NOT NULL,
                sl REAL NOT NULL,
                trailing_sl REAL,
                target REAL NOT NULL,

                qty INTEGER NOT NULL,
                initial_qty INTEGER NOT NULL,
                remaining_qty INTEGER NOT NULL,

                position_value REAL NOT NULL,
                risk_amount REAL,

                confidence REAL DEFAULT 0,
                status TEXT DEFAULT 'OPEN',      -- OPEN / PARTIAL
                hold_mode INTEGER DEFAULT 0,

                entry_day TEXT,
                created_on TEXT,
                updated_at TEXT
            )
        """)
        self.conn.commit()

    # -------------------------------------------------
    # CREATE TRADE (LOCK CAPITAL)
    # -------------------------------------------------
    def save_trade(self, trade: dict) -> int:
        position_value = trade["entry"] * trade["qty"]
        risk_amount = abs(trade["entry"] - trade["sl"]) * trade["qty"]

        # 🔒 lock capital first
        self.settings_repo.adjust_available_swing_capital(-position_value)

        try:
            self.cursor.execute("""
                INSERT INTO tradefriend_trades (
                    symbol, side,
                    entry, sl, trailing_sl, target,
                    qty, initial_qty, remaining_qty,
                    position_value, risk_amount,
                    confidence, status,
                    hold_mode, entry_day,
                    created_on
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', 0, ?, ?)
            """, (
                trade["symbol"],
                trade.get("side", "BUY"),

                trade["entry"],
                trade["sl"],
                trade["sl"],
                trade["target"],

                trade["qty"],
                trade["qty"],
                trade["qty"],

                position_value,
                risk_amount,
                trade.get("confidence", 0),

                date.today().isoformat(),
                datetime.now().isoformat()
            ))

            self.conn.commit()
            return self.cursor.lastrowid

        except Exception:
            # rollback capital if insert fails
            self.settings_repo.adjust_available_swing_capital(+position_value)
            raise

    # -------------------------------------------------
    # FETCH
    # -------------------------------------------------
    def fetch_open_trades(self):
        return self.cursor.execute("""
            SELECT *
            FROM tradefriend_trades
            WHERE status IN ('OPEN', 'PARTIAL')
        """).fetchall()

    def fetch_by_id(self, trade_id: int):
        row = self.cursor.execute("""
            SELECT *
            FROM tradefriend_trades
            WHERE id = ?
        """, (trade_id,)).fetchone()

        return dict(row) if row else None

    def has_open_trade(self, symbol: str) -> bool:
        row = self.cursor.execute("""
            SELECT 1
            FROM tradefriend_trades
            WHERE symbol = ?
              AND status IN ('OPEN', 'PARTIAL')
            LIMIT 1
        """, (symbol,)).fetchone()
        return row is not None

    # -------------------------------------------------
    # SL / TRAILING SL
    # -------------------------------------------------
    def update_sl(self, trade_id: int, new_sl: float):
        self.cursor.execute("""
            UPDATE tradefriend_trades
            SET sl = ?,
                trailing_sl = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_sl, new_sl, trade_id))
        self.conn.commit()

    # -------------------------------------------------
    # PARTIAL EXIT (ONLY METHOD)
    # -------------------------------------------------
    def mark_partial_exit(
        self,
        trade_id: int,
        exit_qty: int,
        exit_price: float
    ) -> int | None:
        trade = self.fetch_by_id(trade_id)
        if not trade:
            return None

        remaining = trade["remaining_qty"]
        if exit_qty <= 0 or exit_qty >= remaining:
            return None

        new_remaining = remaining - exit_qty

        # 🔓 release proportional capital
        per_qty_value = trade["position_value"] / remaining
        released = per_qty_value * exit_qty

        self.settings_repo.adjust_available_swing_capital(released)

        self.cursor.execute("""
            UPDATE tradefriend_trades
            SET
                remaining_qty = ?,
                position_value = position_value - ?,
                status = 'PARTIAL',
                hold_mode = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_remaining, released, trade_id))

        self.conn.commit()
        return new_remaining

    # -------------------------------------------------
    # FINAL EXIT → HISTORY
    # -------------------------------------------------
    def close_and_archive(
        self,
        trade_id: int,
        exit_price: float,
        exit_reason: str
    ):
        trade = self.fetch_by_id(trade_id)
        if not trade:
            return

        # 🔓 release remaining capital
        self.settings_repo.adjust_available_swing_capital(
            trade["position_value"]
        )

        self.history_repo.archive_trade(
            trade=trade,
            exit_price=exit_price,
            exit_reason=exit_reason,
            closed_on=datetime.now().isoformat()
        )

        self.cursor.execute(
            "DELETE FROM tradefriend_trades WHERE id = ?",
            (trade_id,)
        )
        self.conn.commit()

    # -------------------------------------------------
    # SYMBOL HELPERS
    # -------------------------------------------------
    def get_all_symbols(self) -> set:
        rows = self.cursor.execute("""
            SELECT DISTINCT symbol
            FROM tradefriend_trades
            WHERE status IN ('OPEN', 'PARTIAL')
        """).fetchall()
        return {r["symbol"] for r in rows}
    
    # -------------------------------------------------
    # fetch active Trade for Dashboard
    # -------------------------------------------------
    def fetch_active_trades(self, limit: int = 100):
        """
        Fetch active trades (OPEN / PARTIAL) ordered by most recent.
        """

        rows = self.cursor.execute(
            """
            SELECT *
            FROM tradefriend_trades
            WHERE status IN ('OPEN', 'PARTIAL')
            ORDER BY created_on DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()

        statuses = list({r["status"] for r in rows}) if rows else []

        logger.info(
            "📦 fetch_active_trades | rows=%d | statuses=%s",
            len(rows),
            statuses
        )

        if rows:
            logger.debug(
                "📦 First active trade → %s",
                dict(rows[0])
            )

        return rows

    
    def fetch_ready_trades(self): return self.cursor.execute(""" SELECT * FROM tradefriend_trades WHERE status = 'READY' """).fetchall()
