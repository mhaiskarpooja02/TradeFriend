import csv
import hashlib

from db.TradeFriendDhanInstrumentRepo import TradeFriendDhanInstrumentRepo

CSV_FILE = r"C:\Project\TradeFriend\Masterdata\api-scrip-master-detailed.csv"



def row_hash(symbol, security_id):
    key = f"{symbol}|{security_id}|NSE|EQ"
    return hashlib.sha256(key.encode()).hexdigest()


def load_csv():
    repo = TradeFriendDhanInstrumentRepo()

    inserted = 0
    skipped = 0

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:

            # -----------------------------
            # FILTER: NSE EQUITY ONLY
            # -----------------------------
            if row.get("EXCH_ID") != "NSE":
                continue

            if row.get("INSTRUMENT") != "EQUITY":
                continue

            if row.get("INSTRUMENT_TYPE") not in ["ES", "ETF"]:
                continue

            trading_symbol = row.get("UNDERLYING_SYMBOL")
            security_id = row.get("SECURITY_ID")

            if not trading_symbol or not security_id:
                continue

            symbol = f"{trading_symbol}-EQ"
            h = row_hash(symbol, security_id)

            if repo.exists_by_hash(h):
                skipped += 1
                continue

            repo.upsert(
                symbol=symbol,
                trading_symbol=trading_symbol,
                security_id=security_id,
                source_hash=h
            )
            inserted += 1

    print("✅ Dhan CSV Load Complete")
    print(f"Inserted/Updated: {inserted}")
    print(f"Skipped (unchanged): {skipped}")


if __name__ == "__main__":
    load_csv()
