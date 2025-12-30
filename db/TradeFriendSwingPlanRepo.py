# db/TradeFriendSwingPlanRepo.py

class TradeFriendSwingPlanRepo:
    """
    PURPOSE:
    - Persist swing trade plans
    - Manage lifecycle (PLANNED → TRIGGERED / EXPIRED)
    """

    def __init__(self, db):
        self.db = db

    # -----------------------------
    # SAVE NEW PLAN
    # -----------------------------
    def save_plan(self, plan: dict):
        """
        plan = {
            symbol, strategy, entry, sl, target1,
            rr, expiry_date
        }
        """
        self.db.execute("""
            INSERT INTO swing_trade_plans
            (symbol, strategy, entry, sl, target1, rr,
             status, expiry_date, created_on)
            VALUES (?, ?, ?, ?, ?, ?, 'PLANNED', ?, datetime('now'))
        """, (
            plan["symbol"],
            plan.get("strategy"),
            plan["entry"],
            plan["sl"],
            plan["target1"],
            plan.get("rr"),
            plan["expiry_date"]
        ))

    # -----------------------------
    # FETCH ACTIVE PLANS
    # -----------------------------
    def fetch_active_plans(self):
        """
        Used by LTP monitor
        """
        return self.db.fetchall("""
            SELECT *
            FROM swing_trade_plans
            WHERE status = 'PLANNED'
        """)

    # -----------------------------
    # MARK PLAN AS TRIGGERED
    # -----------------------------
    def mark_triggered(self, plan_id):
        self.db.execute("""
            UPDATE swing_trade_plans
            SET status = 'TRIGGERED',
                triggered_on = datetime('now')
            WHERE id = ?
        """, (plan_id,))

    # -----------------------------
    # EXPIRE OLD PLANS
    # -----------------------------
    def expire_old_plans(self):
        """
        Run daily before market open
        """
        self.db.execute("""
            UPDATE swing_trade_plans
            SET status = 'EXPIRED'
            WHERE status = 'PLANNED'
              AND date(expiry_date) < date('now')
        """)

    # -----------------------------
    # CANCEL PLAN (MANUAL)
    # -----------------------------
    def cancel_plan(self, plan_id):
        self.db.execute("""
            UPDATE swing_trade_plans
            SET status = 'CANCELLED'
            WHERE id = ?
        """, (plan_id,))
