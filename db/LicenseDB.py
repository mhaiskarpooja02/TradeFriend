import sqlite3
import os
from utils.logger import get_logger

logger = get_logger(__name__)

# --------------------------------------------------
# DB CONFIG
# --------------------------------------------------
DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_swingalgo.db")

































os.makedirs(DB_FOLDER, exist_ok=True)


class LicenseDB:
    """
    DB handler for Application License lifecycle

    Lifecycle:
    - EMAIL_SUBMITTED
    - KEY_ENTERED
    - VERIFIED
    - EXPIRED

    This table is intentionally SINGLE-ROW driven.
    All updates operate on the latest record.
    """

    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        self._ensure_table()
        self._ensure_indexes()

    # --------------------------------------------------
    # SCHEMA
    # --------------------------------------------------
    def _ensure_table(self):
        logger.info("🔐 Ensuring app_license table exists")

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_license (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                email TEXT,
                license_key TEXT,
                machine_id TEXT,

                verified INTEGER DEFAULT 0,
                expiry_date TEXT,

                status TEXT NOT NULL,

                created_on TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_on TEXT
            )
        """)
        self.conn.commit()

    def _ensure_indexes(self):
        logger.info("📌 Ensuring app_license indexes")

        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_app_license_email
            ON app_license (email)
        """)

        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_app_license_key
            ON app_license (license_key)
        """)

        self.conn.commit()

    # --------------------------------------------------
    # STARTUP CHECKS
    # --------------------------------------------------
    def has_any_record(self) -> bool:
        cur = self.cursor.execute(
            "SELECT 1 FROM app_license LIMIT 1"
        )
        return cur.fetchone() is not None

    def has_email(self) -> bool:
        cur = self.cursor.execute("""
            SELECT 1 FROM app_license
            WHERE email IS NOT NULL
            ORDER BY id DESC
            LIMIT 1
        """)
        return cur.fetchone() is not None

    def has_license_key(self) -> bool:
        cur = self.cursor.execute("""
            SELECT 1 FROM app_license
            WHERE license_key IS NOT NULL
            ORDER BY id DESC
            LIMIT 1
        """)
        return cur.fetchone() is not None

    def is_verified(self) -> bool:
        cur = self.cursor.execute("""
            SELECT verified
            FROM app_license
            ORDER BY id DESC
            LIMIT 1
        """)
        row = cur.fetchone()
        return bool(row["verified"]) if row else False

    def get_status(self) -> str | None:
        cur = self.cursor.execute("""
            SELECT status
            FROM app_license
            ORDER BY id DESC
            LIMIT 1
        """)
        row = cur.fetchone()
        return row["status"] if row else None

    # --------------------------------------------------
    # INSERT / UPDATE (ACTIVATION STEPS)
    # --------------------------------------------------
    def insert_email(self, email: str, machine_id: str):
        """
        FIRST STEP (fresh install)
        """
        logger.info("📧 Inserting activation email")

        self.cursor.execute("""
            INSERT INTO app_license (
                email,
                machine_id,
                status,
                created_on
            ) VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            email,
            machine_id,
            "EMAIL_SUBMITTED"
        ))
        self.conn.commit()

    def update_license_key(self, license_key: str):
        """
        SECOND STEP (user enters key)
        """
        logger.info("🔑 Updating license key")

        self.cursor.execute("""
            UPDATE app_license
            SET license_key = ?,
                status = 'KEY_ENTERED',
                updated_on = CURRENT_TIMESTAMP
            WHERE id = (SELECT MAX(id) FROM app_license)
        """, (license_key,))
        self.conn.commit()

    def update_machine_id(self, machine_id: str):
        logger.info("🖥 Updating machine id")

        self.cursor.execute("""
            UPDATE app_license
            SET machine_id = ?,
                updated_on = CURRENT_TIMESTAMP
            WHERE id = (SELECT MAX(id) FROM app_license)
        """, (machine_id,))
        self.conn.commit()

    def mark_verified(self, expiry_date: str):
        """
        CALLED AFTER VALIDATION SUCCESS
        """
        logger.info("✅ Marking license as verified")

        self.cursor.execute("""
            UPDATE app_license
            SET verified = 1,
                expiry_date = ?,
                status = 'VERIFIED',
                updated_on = CURRENT_TIMESTAMP
            WHERE id = (SELECT MAX(id) FROM app_license)
        """, (expiry_date,))
        self.conn.commit()

    def mark_expired(self):
        logger.warning("⛔ Marking license as expired")

        self.cursor.execute("""
            UPDATE app_license
            SET verified = 0,
                status = 'EXPIRED',
                updated_on = CURRENT_TIMESTAMP
            WHERE id = (SELECT MAX(id) FROM app_license)
        """)
        self.conn.commit()

    # --------------------------------------------------
    # READ
    # --------------------------------------------------
    def get_latest_license(self):
        cur = self.cursor.execute("""
            SELECT *
            FROM app_license
            ORDER BY id DESC
            LIMIT 1
        """)
        return cur.fetchone()

    # --------------------------------------------------
    # DEV / ADMIN
    # --------------------------------------------------
    def clear_all(self):
        """
        DEV ONLY — wipes license state
        """
        logger.warning("⚠ Clearing app_license table")

        self.cursor.execute("DELETE FROM app_license")
        self.conn.commit()
