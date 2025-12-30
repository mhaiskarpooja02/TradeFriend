# db_helper.py
import sqlite3
import os
from utils.logger import get_logger

# DB path
DB_FOLDER = "db"
DB_FILE = os.path.join(DB_FOLDER, "RangeBound_instruments.db")

# Ensure db folder exists
os.makedirs(DB_FOLDER, exist_ok=True)

logger = get_logger(__name__)

class RangeboundDB:
    def __init__(self, db_path=DB_FILE):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.create_table()

    def create_table(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rangebound_stocks (
                    symbol TEXT PRIMARY KEY,
                    date TEXT,
                    year_low REAL,
                    year_high REAL,
                    low_touches INTEGER,
                    high_touches INTEGER,
                    range_percent REAL,
                    last_close REAL,
                    updated_at TEXT
                )
            """)
            self.conn.commit()
        except Exception as e:
            logger.error(f"DB creation failed: {e}")

    def execute(self, sql, params=None):
        try:
            cursor = self.conn.cursor()
            cursor.execute(sql, params or [])
            self.conn.commit()
            return cursor
        except Exception as e:
            logger.error(f"DB SQL failed: {e}")
            return None

    def upsert(self, data: dict):
        """
        Insert or replace a stock record with pure metrics.
        Expects data dict with keys:
        symbol, date, year_low, year_high, low_touches, high_touches, range_percent, last_close
        """
        try:
            self.conn.execute("""
                INSERT OR REPLACE INTO rangebound_stocks
                (symbol, date, year_low, year_high, low_touches, high_touches, range_percent, last_close, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                data["symbol"], data["date"], data["year_low"], data["year_high"],
                data["low_touches"], data["high_touches"], data["range_percent"],
                data["last_close"]
            ))
            self.conn.commit()
        except Exception as e:
            logger.error(f"DB upsert failed: {e}")

    def fetch(self, sql, params=None):
        try:
            cursor = self.conn.cursor()
            cursor.execute(sql, params or [])
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"DB Fetch failed: {e}")
            return []
