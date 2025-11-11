import os
import sqlite3

# DB path
DB_FOLDER = "db"
DB_FILE = os.path.join(DB_FOLDER, "Dhan_instruments.db")

# Ensure db folder exists
os.makedirs(DB_FOLDER, exist_ok=True)


class DhanDBHelper:
    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # dict-like access
        self.cursor = self.conn.cursor()
        self._create_table()

    def _create_table(self):
        """Create instruments table if not exists"""
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS instruments (
            symbol TEXT PRIMARY KEY,
            broker TEXT,
            quantity INTEGER,
            avg_price REAL,
            ltp REAL,
            monitor_target1 INTEGER DEFAULT 1,
            monitor_target2 INTEGER DEFAULT 1,
            target1 REAL DEFAULT 0,
            target2 REAL DEFAULT 0,
            sell_qty_target1 INTEGER DEFAULT 0,
            sell_qty_target2 INTEGER DEFAULT 0,
            mode TEXT DEFAULT 'Manual',
            active_target1 INTEGER DEFAULT 1,
            active_target2 INTEGER DEFAULT 1
        )
        """)
        self.conn.commit()

    # ----------------- CRUD Operations -----------------

    def insert_or_update(self, data: dict):
        """Insert or update an instrument"""
        self.cursor.execute("""
        INSERT INTO instruments (
            symbol, broker, quantity, avg_price, ltp,
            monitor_target1, monitor_target2,
            target1, target2,
            sell_qty_target1, sell_qty_target2,
            mode, active_target1, active_target2
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol) DO UPDATE SET
            broker=excluded.broker,
            quantity=excluded.quantity,
            avg_price=excluded.avg_price,
            ltp=excluded.ltp,
            monitor_target1=excluded.monitor_target1,
            monitor_target2=excluded.monitor_target2,
            target1=excluded.target1,
            target2=excluded.target2,
            sell_qty_target1=excluded.sell_qty_target1,
            sell_qty_target2=excluded.sell_qty_target2,
            mode=excluded.mode,
            active_target1=excluded.active_target1,
            active_target2=excluded.active_target2
        """, (
            data.get("symbol"),
            data.get("broker", "Dhan"),
            data.get("quantity", 0),
            data.get("avg_price", 0.0),
            data.get("ltp", 0.0),
            data.get("monitor_target1", 1),
            data.get("monitor_target2", 1),
            data.get("target1", 0.0),
            data.get("target2", 0.0),
            data.get("sell_qty_target1", 0),
            data.get("sell_qty_target2", 0),
            data.get("mode", "Manual"),
            data.get("active_target1", 1),
            data.get("active_target2", 1),
        ))
        self.conn.commit()

    def get_all(self):
        """Fetch all instruments as list of dicts"""
        self.cursor.execute("SELECT * FROM instruments")
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]

    def get_by_symbol(self, symbol: str):
        """Fetch single instrument by symbol"""
        self.cursor.execute("SELECT * FROM instruments WHERE symbol=?", (symbol,))
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def delete_by_symbol(self, symbol: str):
        """Delete an instrument by symbol"""
        self.cursor.execute("DELETE FROM instruments WHERE symbol=?", (symbol,))
        self.conn.commit()

    def close(self):
        """Close DB connection"""
        self.conn.close()
