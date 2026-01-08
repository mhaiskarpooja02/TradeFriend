import sqlite3
import os

DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_algo.db")

os.makedirs(DB_FOLDER, exist_ok=True)


class TradeFriendSwingPlanRepo:
    """
    PURPOSE:
    - Persist swing trade plans
    - Manage lifecycle (PLANNED → TRIGGERED / EXPIRED)
    """

    def __init__(self):
        self.conn = sqlite3.connect(
            DB_FILE,
            check_same_thread=False
        )
        self.conn.row_factory = sqlite3.Row
        self._create_table()

    # -----------------------------
    # ENSURE TABLE
    # -----------------------------
    def _create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS swing_trade_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                strategy TEXT,
                entry REAL NOT NULL,
                sl REAL NOT NULL,
                target1 REAL NOT NULL,
                rr REAL,
                status TEXT DEFAULT 'PLANNED',
                expiry_date TEXT,
                created_on TEXT,
                triggered_on TEXT
            )
        """)
        self.conn.commit()

    # -----------------------------
    # SAVE NEW PLAN
    # -----------------------------
    def save_plan(self, plan: dict):
        """
        Accepts normalized plan dict from planner.
        Handles schema mapping internally.
        """
    
        # 🔒 Normalize input once
        plan = dict(plan)
    
        # ✅ Backward / forward compatible target resolution
        target1 = (
            plan.get("target1")
            or plan.get("target")
        )
    
        if target1 is None:
            raise ValueError(
                f"SwingPlan missing target/target1 for {plan.get('symbol')}"
            )
    
        self.conn.execute("""
            INSERT INTO swing_trade_plans
            (symbol, strategy, entry, sl, target1, rr,
             status, expiry_date, created_on)
            VALUES (?, ?, ?, ?, ?, ?, 'PLANNED', ?, datetime('now'))
        """, (
            plan["symbol"],
            plan.get("strategy"),
            plan["entry"],
            plan["sl"],
            float(target1),
            plan.get("rr"),
            plan["expiry_date"]
        ))
        self.conn.commit()


    # -----------------------------
    # FETCH ACTIVE PLANS
    # -----------------------------
    def fetch_active_plans(self):
        cursor = self.conn.execute("""
            SELECT *
            FROM swing_trade_plans
            WHERE status = 'PLANNED'
            ORDER BY created_on DESC
        """)
        return cursor.fetchall()

    # -----------------------------
    # MARK PLAN AS TRIGGERED
    # -----------------------------
    def mark_triggered(self, plan_id):
        self.conn.execute("""
            UPDATE swing_trade_plans
            SET status = 'TRIGGERED',
                triggered_on = datetime('now')
            WHERE id = ?
        """, (plan_id,))
        self.conn.commit()

    # -----------------------------
    # EXPIRE OLD PLANS
    # -----------------------------
    def expire_old_plans(self):
        self.conn.execute("""
            UPDATE swing_trade_plans
            SET status = 'EXPIRED'
            WHERE status = 'PLANNED'
              AND date(expiry_date) < date('now')
        """)
        self.conn.commit()

    # -----------------------------
    # CANCEL PLAN (MANUAL)
    # -----------------------------
    def cancel_plan(self, plan_id):
        self.conn.execute("""
            UPDATE swing_trade_plans
            SET status = 'CANCELLED'
            WHERE id = ?
        """, (plan_id,))
        self.conn.commit()
    # -----------------------
    # delete_orphan_plans 
    # -----------------------
    def delete_orphan_plans(self):
        """
        Delete swing plans whose symbol no longer exists in watchlist
        """
        self.conn.execute("""
            DELETE FROM swing_trade_plans
            WHERE symbol NOT IN (
                SELECT symbol FROM tradefriend_watchlist
            )
        """)
        self.conn.commit()