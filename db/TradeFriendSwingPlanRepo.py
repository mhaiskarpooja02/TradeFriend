import sqlite3
import os
from typing import Dict, List

DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_algo.db")

os.makedirs(DB_FOLDER, exist_ok=True)


class TradeFriendSwingPlanRepo:
    """
    PURPOSE:
    - Single authoritative TRADE INTENT table
    - Supports SWING / INTRADAY
    - BUY / SELL
    - Carry-forward aware
    - Future-proof (no schema churn)
    """

    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        # 🔒 SQLite safety
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.conn.execute("PRAGMA busy_timeout = 5000;")

        self._create_table()

    # --------------------------------------------------
    # TABLE & INDEX
    # --------------------------------------------------
    def _create_table(self):
        """
        NOTE:
        You already backed up old data.
        This creates a clean, final schema.
        """

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS swing_trade_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                symbol TEXT NOT NULL,
                strategy TEXT,

                direction TEXT DEFAULT 'BUY',        -- BUY / SELL
                order_type TEXT DEFAULT 'MARKET',    -- BREAKOUT / PULLBACK / MARKET
                trade_type TEXT DEFAULT 'SWING',     -- SWING / INTRADAY
                carry_forward INTEGER DEFAULT 1,     -- 0 / 1
                product_type TEXT DEFAULT 'CNC',     -- CNC / MIS / NRML

                entry REAL NOT NULL,
                sl REAL NOT NULL,
                target1 REAL NOT NULL,
                rr REAL,

                status TEXT DEFAULT 'PLANNED',
                expiry_date TEXT,
                created_on TEXT DEFAULT (datetime('now')),
                triggered_on TEXT
            )
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_swing_plan_status
            ON swing_trade_plans(status)
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_swing_plan_symbol
            ON swing_trade_plans(symbol)
        """)

        self.conn.commit()

    # --------------------------------------------------
    # SAVE NEW PLAN
    # --------------------------------------------------
    def save_plan(self, plan: Dict):
        if not plan:
            return

        plan = dict(plan)

        target1 = plan.get("target1") or plan.get("target")
        if target1 is None:
            raise ValueError(f"Missing target for {plan.get('symbol')}")

        self.conn.execute("""
            INSERT INTO swing_trade_plans (
                symbol, strategy,
                direction, order_type, trade_type, carry_forward, product_type,
                entry, sl, target1, rr,
                status, expiry_date, created_on
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PLANNED', ?, datetime('now'))
        """, (
            plan["symbol"],
            plan.get("strategy"),

            plan.get("direction", "BUY"),
            plan.get("order_type", "MARKET"),
            plan.get("trade_type", "SWING"),
            int(plan.get("carry_forward", 1)),
            plan.get("product_type", "CNC"),

            float(plan["entry"]),
            float(plan["sl"]),
            float(target1),
            plan.get("rr"),
            plan.get("expiry_date")
        ))

        self.conn.commit()

    # --------------------------------------------------
    # UPDATE EXISTING PLAN
    # --------------------------------------------------
    def update_plan(self, plan_id: int, new_plan: Dict):
        if not plan_id or not new_plan:
            return

        new_plan = dict(new_plan)
        target1 = new_plan.get("target1") or new_plan.get("target")

        self.conn.execute("""
            UPDATE swing_trade_plans
            SET
                entry = ?,
                sl = ?,
                target1 = ?,
                rr = ?,
                expiry_date = ?,
                strategy = ?,

                direction = COALESCE(?, direction),
                order_type = COALESCE(?, order_type),
                trade_type = COALESCE(?, trade_type),
                carry_forward = COALESCE(?, carry_forward),
                product_type = COALESCE(?, product_type)
            WHERE id = ?
        """, (
            float(new_plan["entry"]),
            float(new_plan["sl"]),
            float(target1),
            new_plan.get("rr"),
            new_plan.get("expiry_date"),
            new_plan.get("strategy"),

            new_plan.get("direction"),
            new_plan.get("order_type"),
            new_plan.get("trade_type"),
            new_plan.get("carry_forward"),
            new_plan.get("product_type"),

            plan_id
        ))

        self.conn.commit()

    # --------------------------------------------------
    # FETCH ACTIVE PLANS
    # --------------------------------------------------
    def fetch_active_plans(self) -> List[sqlite3.Row]:
        return self.conn.execute("""
            SELECT *
            FROM swing_trade_plans
            WHERE status = 'PLANNED'
            ORDER BY created_on DESC
        """).fetchall()

    # --------------------------------------------------
    # FETCH ACTIVE PLAN FOR SYMBOL
    # --------------------------------------------------
    def get_active_plan(self, symbol: str):
        return self.conn.execute("""
            SELECT *
            FROM swing_trade_plans
            WHERE symbol = ?
              AND status = 'PLANNED'
            ORDER BY created_on DESC
            LIMIT 1
        """, (symbol,)).fetchone()

    # --------------------------------------------------
    # MARK TRIGGERED
    # --------------------------------------------------
    def mark_triggered(self, plan_id: int):
        self.conn.execute("""
            UPDATE swing_trade_plans
            SET status = 'TRIGGERED',
                triggered_on = datetime('now')
            WHERE id = ?
        """, (plan_id,))
        self.conn.commit()

    # --------------------------------------------------
    # EXPIRE OLD PLANS
    # --------------------------------------------------
    def expire_old_plans(self):
        self.conn.execute("""
            UPDATE swing_trade_plans
            SET status = 'EXPIRED'
            WHERE status = 'PLANNED'
              AND expiry_date IS NOT NULL
              AND date(expiry_date) < date('now')
        """)
        self.conn.commit()

    # --------------------------------------------------
    # DELETE ORPHANS
    # --------------------------------------------------
    def delete_orphan_plans(self):
        self.conn.execute("""
            DELETE FROM swing_trade_plans
            WHERE symbol NOT IN (
                SELECT symbol FROM tradefriend_watchlist
            )
        """)
        self.conn.commit()

    # --------------------------------------------------
    # mark decision
    # --------------------------------------------------
    def mark_decision(self, plan_id: int, status: str):
        self.conn.execute("""
            UPDATE swing_trade_plans
            SET status = ?
            WHERE id = ?
        """, (status, plan_id))
        self.conn.commit()

    # --------------------------------------------------
    # RESET
    # --------------------------------------------------
    def reset_all(self):
        self.conn.execute("DELETE FROM swing_trade_plans")
        self.conn.commit()

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass
