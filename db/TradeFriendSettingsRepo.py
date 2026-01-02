import sqlite3
import os

DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_settings.db")
os.makedirs(DB_FOLDER, exist_ok=True)


class TradeFriendSettingsRepo:
    """
    PURPOSE:
    - Store configurable trading settings
    - Single source of truth
    """

    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self._create_table()
        self._ensure_defaults()

    def _create_table(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        self.conn.commit()

    def _ensure_defaults(self):
        defaults = {
            "SWING_CAPITAL": "100000",
            "RISK_PERCENT": "1.0",
            "MAX_OPEN_TRADES": "5",
            "MAX_CAPITAL_UTILIZATION": "0.6",

            # qty slab rules (JSON-like string for now)
            "QTY_RULES": "500:10,1000:5,3000:2,5000:1,10000:1"
        }

        for k, v in defaults.items():
            self.cursor.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (k, v)
            )
        self.conn.commit()

    # ----------------------------
    # Public API
    # ----------------------------

    def get(self, key, default=None):
        self.cursor.execute(
            "SELECT value FROM settings WHERE key = ?",
            (key,)
        )
        row = self.cursor.fetchone()
        return row["value"] if row else default

    def set(self, key, value):
        self.cursor.execute("""
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, str(value)))
        self.conn.commit()

    def get_float(self, key, default=0.0):
        try:
            return float(self.get(key, default))
        except Exception:
            return default

    def get_int(self, key, default=0):
        try:
            return int(self.get(key, default))
        except Exception:
            return default

    def get_qty_rules(self):
        """
        Example stored:
        500:10,1000:5,3000:2,5000:1
        """
        raw = self.get("QTY_RULES", "")
        rules = []

        for part in raw.split(","):
            try:
                price, qty = part.split(":")
                rules.append((float(price), int(qty)))
            except Exception:
                pass

        # sort by price ascending
        return sorted(rules, key=lambda x: x[0])
