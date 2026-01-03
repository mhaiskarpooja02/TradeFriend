import sqlite3
from pathlib import Path


class TradeFriendSettingsRepo:
    """
    Central settings repository for TradeFriend
    Uses AMOUNT-based capital configuration (no percentages except risk)
    """

    DB_PATH = Path("tradefriend.db")

    DEFAULTS = {
        "total_capital": 1000000,
        "swing_capital": 300000,
        "max_active_capital": 200000,
        "per_trade_cap": 40000,
        "risk_percent": 1.0,
        "max_open_trades": 5,
    }

    def __init__(self):
        self.conn = sqlite3.connect(self.DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self._create_table()
        self._ensure_defaults()

    # -------------------------------------------------
    # DB
    # -------------------------------------------------
    def _create_table(self):
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS tradefriend_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)
        self.conn.commit()

    def _ensure_defaults(self):
        for k, v in self.DEFAULTS.items():
            if self.get(k) is None:
                self.set(k, v)

    # -------------------------------------------------
    # API
    # -------------------------------------------------
    def get(self, key):
        cur = self.conn.execute(
            "SELECT value FROM tradefriend_settings WHERE key = ?",
            (key,)
        )
        row = cur.fetchone()
        if not row:
            return None

        val = row["value"]
        if "." in val:
            return float(val)
        return int(val)

    def set(self, key, value):
        self.conn.execute("""
        INSERT INTO tradefriend_settings(key, value)
        VALUES(?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """, (key, str(value)))
        self.conn.commit()

    # -------------------------------------------------
    # Convenience Getters (OPTIONAL but clean)
    # -------------------------------------------------
    def total_capital(self):
        return self.get("total_capital")

    def swing_capital(self):
        return self.get("swing_capital")

    def max_active_capital(self):
        return self.get("max_active_capital")

    def per_trade_cap(self):
        return self.get("per_trade_cap")

    def risk_percent(self):
        return self.get("risk_percent")

    def max_open_trades(self):
        return self.get("max_open_trades")
