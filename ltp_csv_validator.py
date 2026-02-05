import csv
import os
import time
from datetime import datetime, timedelta
import logging

from brokers.angel_client import AngelClient, getltp, init_client

# -------------------------------------------------
# CONFIG
# -------------------------------------------------
INPUT_FOLDER = "RangeBoundOutput"
INPUT_CSV = "validated_symbols_20260130_193632.csv"
OUTPUT_CSV = "validated_symbols_ltp.csv"

REVALIDATE_AFTER_DAYS = 5
INACTIVE_EXPIRY_DAYS = 10

SERIES_FALLBACK = ["-EQ", "-SM", "-BE"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# -------------------------------------------------
# MAIN VALIDATOR
# -------------------------------------------------
class LTPCsvValidator:

    def __init__(self):
        init_client()          # Angel init (ONCE)
        self.angel = AngelClient()

    # -------------------------------------------------
    # SHOULD REVALIDATE?
    # -------------------------------------------------
    def _needs_revalidation(self, row: dict) -> bool:
        last_check = row.get("last_ltp_check")
        if not last_check:
            return True

        try:
            last_dt = datetime.fromisoformat(last_check)
            return (datetime.now() - last_dt).days >= REVALIDATE_AFTER_DAYS
        except Exception:
            return True

    # -------------------------------------------------
    # AUTO-EXPIRE INACTIVE
    # -------------------------------------------------
    def _is_expired(self, row: dict) -> bool:
        if row.get("active") != "0":
            return False

        last_check = row.get("last_ltp_check")
        if not last_check:
            return False

        try:
            last_dt = datetime.fromisoformat(last_check)
            return (datetime.now() - last_dt).days >= INACTIVE_EXPIRY_DAYS
        except Exception:
            return False

    # -------------------------------------------------
    # LTP VALIDATION USING ANGEL
    # -------------------------------------------------
    def _validate_ltp(self, symbol_eq: str, token: str, rejected: list) -> float | None:
        try:
            resolved = {
                "symbol": symbol_eq,
                "token": token,
                "exchange": "NSE",
                "trading_symbol": symbol_eq,
            }

            logger.info(f"🔎 LTP check | {resolved}")

            ltp = getltp(resolved)

            if ltp is None or not isinstance(ltp, (int, float)) or ltp <= 0:
                rejected.append({
                    "symbol": symbol_eq,
                    "reason": "Invalid LTP"
                })
                return None

            return float(ltp)

        except Exception as e:
            logger.error(f"❌ LTP error | {symbol_eq} | {e}")
            rejected.append({
                "symbol": symbol_eq,
                "reason": "LTP exception"
            })
            return None

    # -------------------------------------------------
    # MAIN CSV VALIDATION
    # -------------------------------------------------
    def validate_csv_with_ltp(self):
        input_path = os.path.join(INPUT_FOLDER, INPUT_CSV)
        output_path = os.path.join(INPUT_FOLDER, OUTPUT_CSV)

        if not os.path.exists(input_path):
            raise FileNotFoundError(input_path)

        with open(input_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        validated_rows = []
        rejected = []

        for row in rows:
            symbol = row["symbol"]
            base_symbol = row["symbolName"]
            token = row["token"]

            # -----------------------------------------
            # AUTO-EXPIRE
            # -----------------------------------------
            if self._is_expired(row):
                logger.info(f"🛑 Expired | {symbol}")
                row["active"] = "0"
                validated_rows.append(row)
                continue

            # -----------------------------------------
            # SKIP IF RECENTLY VALIDATED
            # -----------------------------------------
            if not self._needs_revalidation(row):
                validated_rows.append(row)
                continue

            logger.info(f"🚀 Validating LTP | {symbol}")

            selected_symbol = ""
            active = "0"

            # -----------------------------------------
            # EQ → SM → BE FALLBACK
            # -----------------------------------------
            for suffix in SERIES_FALLBACK:
                symbol_eq = f"{base_symbol}{suffix}"

                ltp = self._validate_ltp(symbol_eq, token, rejected)
                if ltp is not None:
                    selected_symbol = symbol_eq.replace("-", "_")
                    active = "1"
                    break

            # -----------------------------------------
            # UPDATE ROW
            # -----------------------------------------
            row["symbolnameltp"] = selected_symbol
            row["active"] = active
            row["last_ltp_check"] = datetime.now().isoformat()

            validated_rows.append(row)

            time.sleep(0.15)  # gentle rate limit

        # -------------------------------------------------
        # WRITE OUTPUT CSV
        # -------------------------------------------------
        fieldnames = validated_rows[0].keys()

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(validated_rows)

        logger.info("✅ LTP validation complete")
        logger.info("➡ Output CSV: %s", output_path)
        logger.info("➡ Total rows: %d", len(validated_rows))
        logger.info("➡ Rejected attempts: %d", len(rejected))


# -------------------------------------------------
# CLI
# -------------------------------------------------
if __name__ == "__main__":
    validator = LTPCsvValidator()
    validator.validate_csv_with_ltp()
