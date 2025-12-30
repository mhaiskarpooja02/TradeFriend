import sqlite3
import os
from utils.logger import get_logger

logger = get_logger(__name__)

DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_swingalgo.db")

os.makedirs(DB_FOLDER, exist_ok=True)


class SwingTradePlanDB:
    """
    DB handler for Swing Trade Plans
    Auto initializes table + indexes
    """

    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        self._ensure_table()
        self._ensure_indexes()

    # ----------------------------
    # TABLE
    # ----------------------------
    def _ensure_table(self):
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS swing_trade_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            symbol TEXT NOT NULL,
            strategy TEXT NOT NULL,
            bias TEXT NOT NULL,

            planned_entry REAL NOT NULL,
            planned_sl REAL NOT NULL,
            planned_target REAL NOT NULL,

            rr REAL NOT NULL,
            confidence INTEGER DEFAULT 0,

            status TEXT DEFAULT 'PLANNED',
            is_paper INTEGER DEFAULT 1,

            planned_on DATE NOT NULL,
            valid_till DATE NOT NULL,

            entry_price REAL,
            exit_price REAL,
            exit_reason TEXT,

            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        self.conn.commit()
        logger.info("✅ swing_trade_plans table ready")

    # ----------------------------
    # INDEXES
    # ----------------------------
    def _ensure_indexes(self):
        self.cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_swing_symbol
        ON swing_trade_plans(symbol)
        """)
        self.cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_swing_status
        ON swing_trade_plans(status)
        """)
        self.cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_swing_validity
        ON swing_trade_plans(valid_till)
        """)
        self.conn.commit()
        logger.info("✅ swing_trade_plans indexes ready")

    # ----------------------------
    # CLEANUP
    # ----------------------------
    def close(self):
        self.conn.close()
