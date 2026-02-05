import csv
import os

from db.TradeFriendStocMasterRepo import TradeFriendStocMasterRepo


# ---------------------------------------
# CONFIG
# ---------------------------------------
CSV_FILE = "RangeBoundOutput/validated_symbols_ltp.csv"


# ---------------------------------------
# CSV → OBJECT → DB
# ---------------------------------------
def load_csv_into_stockmaster():
    if not os.path.exists(CSV_FILE):
        raise FileNotFoundError(f"❌ CSV not found: {CSV_FILE}")

    repo = TradeFriendStocMasterRepo()

    inserted = 0
    failed = 0

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            try:
                # ---------------------------------------
                # PREPARE OBJECT (NORMALIZED)
                # ---------------------------------------
                obj = {
                    "symbol": row["symbol"].strip(),
                    "symbolName": row["symbolName"].strip(),
                    "token": row["token"].strip(),
                    "symbolnameltp": row.get("symbolnameltp"),
                    "active": int(row.get("active", 0)),
                    "last_ltp_check": row.get("last_ltp_check"),
                }

                repo.upsert_from_csv(obj)
                inserted += 1

            except Exception as e:
                failed += 1
                print(f"❌ Failed | {row.get('symbol')} | {e}")

    print("------------------------------------------------")
    print(f"✅ Rows inserted / updated : {inserted}")
    print(f"⚠️ Failed                : {failed}")


# ---------------------------------------
# MAIN
# ---------------------------------------
if __name__ == "__main__":
    load_csv_into_stockmaster()
    print("🎯 tradefriend_stocmaster sync completed")
