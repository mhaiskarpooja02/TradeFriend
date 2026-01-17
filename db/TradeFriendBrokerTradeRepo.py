import sqlite3
import os
from datetime import datetime
import json

DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_broker_trades.db")
os.makedirs(DB_FOLDER, exist_ok=True)


class TradeFriendBrokerTradeRepo:
    """
    PURPOSE:
    - Persist broker-level trade executions
    - Acts as ORDER AUDIT + EXECUTION LOG
    - Supports multi-broker, retries, and exits
    """

    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cur = self.conn.cursor()
        self._create_table()
        self._create_indexes()

    # --------------------------------------------------
    # TABLE
    # --------------------------------------------------
    def _create_table(self):
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS tradefriend_broker_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                trade_id INTEGER NOT NULL,

                broker TEXT NOT NULL,              -- DHAN / ANGEL
                order_mode TEXT NOT NULL,          -- LIVE / PAPER

                symbol TEXT NOT NULL,
                side TEXT NOT NULL,                -- BUY / SELL
                qty INTEGER NOT NULL,

                exchange TEXT,
                product TEXT,
                order_type TEXT,

                resolved_id TEXT,                  -- token / security_id
                broker_order_id TEXT,

                status TEXT NOT NULL,              -- ATTEMPT / SUCCESS / FAILED
                error_message TEXT,

                request_payload TEXT,
                response_payload TEXT,

                created_on TEXT,
                updated_on TEXT
            )
        """)
        self.conn.commit()

    # --------------------------------------------------
    # INDEXES (IMPORTANT)
    # --------------------------------------------------
    def _create_indexes(self):
        self.cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_bt_trade_id
            ON tradefriend_broker_trades(trade_id)
        """)

        self.cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_bt_broker
            ON tradefriend_broker_trades(broker)
        """)

        self.cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_bt_status
            ON tradefriend_broker_trades(status)
        """)
        self.conn.commit()

    # --------------------------------------------------
    # INSERT ATTEMPT
    # --------------------------------------------------
    def log_attempt(
        self,
        trade_id: int,
        broker: str,
        order_mode: str,
        symbol: str,
        side: str,
        qty: int,
        exchange: str = None,
        product: str = None,
        order_type: str = None,
        resolved_id: str = None,
        request_payload: dict = None
    ) -> int:
        """
        Insert ATTEMPT row.
        Returns broker_trade_id.
        """

        self.cur.execute("""
            INSERT INTO tradefriend_broker_trades (
                trade_id,
                broker,
                order_mode,
                symbol,
                side,
                qty,
                exchange,
                product,
                order_type,
                resolved_id,
                status,
                request_payload,
                created_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ATTEMPT', ?, ?)
        """, (
            trade_id,
            broker,
            order_mode,
            symbol,
            side,
            qty,
            exchange,
            product,
            order_type,
            resolved_id,
            json.dumps(request_payload) if request_payload else None,
            datetime.now().isoformat()
        ))

        self.conn.commit()
        return self.cur.lastrowid

    # --------------------------------------------------
    # SUCCESS
    # --------------------------------------------------
    def log_success(
        self,
        broker_trade_id: int,
        broker_order_id: str,
        response_payload: dict = None
    ):
        self.cur.execute("""
            UPDATE tradefriend_broker_trades
            SET
                status = 'SUCCESS',
                broker_order_id = ?,
                response_payload = ?,
                updated_on = ?
            WHERE id = ?
        """, (
            broker_order_id,
            json.dumps(response_payload) if response_payload else None,
            datetime.now().isoformat(),
            broker_trade_id
        ))
        self.conn.commit()

    # --------------------------------------------------
    # FAILURE
    # --------------------------------------------------
    def log_failure(
        self,
        broker_trade_id: int,
        error_message: str
    ):
        self.cur.execute("""
            UPDATE tradefriend_broker_trades
            SET
                status = 'FAILED',
                error_message = ?,
                updated_on = ?
            WHERE id = ?
        """, (
            error_message,
            datetime.now().isoformat(),
            broker_trade_id
        ))
        self.conn.commit()

    # --------------------------------------------------
    # FETCH ACTIVE BROKER TRADE (FOR EXIT)
    # --------------------------------------------------
    def fetch_active_execution(self, trade_id: int):
        """
        Returns latest SUCCESS broker execution for a trade.
        Used during EXIT to know broker & order_id.
        """
        row = self.cur.execute("""
            SELECT *
            FROM tradefriend_broker_trades
            WHERE trade_id = ?
              AND status = 'SUCCESS'
            ORDER BY id DESC
            LIMIT 1
        """, (trade_id,)).fetchone()

        return dict(row) if row else None
