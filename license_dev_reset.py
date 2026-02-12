import sqlite3
import os

# --------------------------------------------------
# DB CONFIG
# --------------------------------------------------
DB_FOLDER = "dbdata"
LICENSE_DB_FILE = os.path.join(DB_FOLDER, "tradefriend_swingalgo.db")


class LicenseDevReset:
    """
    DEV ONLY utility
    - Clears license table for fresh activation testing
    """

    def __init__(self, db_file=LICENSE_DB_FILE):
        if not os.path.exists(db_file):
            raise FileNotFoundError(f"License DB not found: {db_file}")
        self.db_file = db_file

    def clear_license(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM app_license")
        deleted = cursor.rowcount

        conn.commit()
        conn.close()

        print("===================================")
        print(" License DEV Reset ")
        print("===================================")
        print(f"🗑 Deleted rows : {deleted}")
        print("===================================")


# --------------------------------------------------
# MANUAL RUN
# --------------------------------------------------
if __name__ == "__main__":
    resetter = LicenseDevReset()
    resetter.clear_license()
