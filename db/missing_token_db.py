import sqlite3
from utils.logger import get_logger

logger = get_logger(__name__)

DB_PATH = "dbdata/trade_data.db"  # adjust to your DB location


class MissingTokenDB:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.create_table()
        self._ensure_active_set()  # automatically fix missing active flags

    def create_table(self):
        """Create table if not exists"""
        try:
            with self.conn:
                self.conn.execute("""
                CREATE TABLE IF NOT EXISTS missing_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    name TEXT,
                    active INTEGER DEFAULT 1,
                    UNIQUE(symbol)
                )
                """)
        except Exception as e:
            logger.error(f"Failed creating missing_tokens table: {e}")

    def _ensure_active_set(self):
        """
        Ensure all rows have active set to 1 if it's NULL or invalid.
        This runs every init, so the table stays consistent.
        """
        try:
            with self.conn:
                self.conn.execute("""
                    UPDATE missing_tokens
                    SET active = 1
                    WHERE active IS NULL OR active NOT IN (0,1)
                """)
            logger.info(" Ensured all rows have active set to 1 if missing/invalid")
        except Exception as e:
            logger.error(f"Failed to ensure active flags: {e}")


    def add_or_update(self, symbol: str, name: str = None, active: int = 1):
         """
         Insert a missing token entry if not exists.
         If exists with active=0 and we now have valid token, update to active=1.
         """
    
         try:
             # -----------------------------
             # 🔒 HARD VALIDATION
             # -----------------------------
             if not isinstance(symbol, str):
                 logger.warning(f"Skipping invalid symbol type: {symbol}")
                 return
    
             symbol = symbol.strip()
             if not symbol or symbol.startswith("<sqlite3.Row"):
                 logger.warning(f"Skipping invalid symbol value: {symbol}")
                 return
    
             cur = self.conn.cursor()
             cur.execute(
                 "SELECT active FROM missing_tokens WHERE symbol = ?",
                 (symbol,)
             )
             row = cur.fetchone()
    
             logger.info(f"SELECTED data for Symbol {symbol} in add_or_update")
    
             if row:
                 current_status = row[0]
    
                 if current_status == 1:
                     logger.info(
                         f"Symbol {symbol} already active, skipping insert"
                     )
    
                 elif current_status == 0 and active == 1:
                     with self.conn:
                         self.conn.execute(
                             """
                             UPDATE missing_tokens
                             SET active = ?, name = ?
                             WHERE symbol = ?
                             """,
                             (active, name, symbol),
                         )
                     logger.info(f"Re-activated missing token: {symbol}")
    
             else:
                 with self.conn:
                     self.conn.execute(
                         """
                         INSERT INTO missing_tokens (symbol, name, active)
                         VALUES (?, ?, ?)
                         """,
                         (symbol, name, active),
                     )
                 logger.info(f"Stored missing token: {symbol} ({name})")
    
             cur.close()
    
         except Exception as e:
             logger.error(f"Error storing missing token {symbol}: {e}", exc_info=True)

    def update_active_status(self, symbol: str, active: int, name: str = None):
        """
        Update the active status of a symbol in missing_tokens table.
        If name is provided, it will also update the name field.
        """
        try:
            with self.conn:
                if name:
                    self.conn.execute(
                        "UPDATE missing_tokens SET active = ?, name = ? WHERE symbol = ?",
                        (active, name, symbol),
                    )
                else:
                    self.conn.execute(
                        "UPDATE missing_tokens SET active = ? WHERE symbol = ?",
                        (active, symbol),
                    )
            logger.info(f"Updated symbol {symbol} → active={active}, name={name}")
        except Exception as e:
            logger.error(f"Error updating active status for {symbol}: {e}")

    def get_all(self):
       """Fetch all stored missing tokens"""
       try:
           logger.info("Calling get_all() in MissingTokenDB")
           cur = self.conn.cursor()
           cur.execute("SELECT symbol, name, active FROM missing_tokens ")
        #    cur.execute("SELECT symbol, name, active FROM missing_tokens WHERE symbol LIKE 'CONNPLEX%'")
           rows = cur.fetchall()
           logger.info(f"Fetched {len(rows)} rows from missing_tokens table")
           logger.debug(f"Rows data: {rows}")  # debug level for full data
           return [{"symbol": r[0], "name": r[1], "active": r[2]} for r in rows]
       except Exception as e:
           logger.exception(f"Error fetching missing tokens: {e}")
           return []
    def cleanup_invalid_symbols(self):
        """
        Remove corrupted / invalid symbols safely (SQLite compatible)
        """
        try:
            with self.conn:
                self.conn.execute("""
                    DELETE FROM missing_tokens
                    WHERE symbol IS NULL
                       OR TRIM(symbol) = ''
                       OR symbol LIKE '<sqlite3.Row%'
                       OR symbol LIKE '%object at%'
                """)
            logger.info("Cleaned up invalid symbols from missing_tokens table")
        except Exception as e:
            logger.error(f"Failed to cleanup invalid symbols: {e}")

    def _is_valid_symbol(self, symbol):
        return isinstance(symbol, str) and symbol.strip() and not symbol.startswith("<sqlite3.Row")