import os
import csv
import time
import random
import logging
import pandas as pd

from datetime import datetime
from config.settings import RangeBoundOutput_DIR
from utils.instrumenthelper import InstrumentHelper
from utils.symbol_resolver import SymbolResolver
from brokers.angel_client import AngelClient


# -----------------------------------
# CONFIG
# -----------------------------------
MIN_ROWS = 2
SEARCH_DELAY = 0.4
SERIES_PRIORITY = ["-SM", "-EQ", "-SL", "-SQ", "-ST"]

INPUT_CSV_PREFIX = "rangebound_symbols_"
OUTPUT_FILE_PREFIX = "validated_symbols_"


# -----------------------------------
# LOGGER
# -----------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s"
)
logger = logging.getLogger("csv_token_validator")


# ===================================
# MAIN CLASS
# ===================================
class TokenValidator:
    def __init__(self):
        """
        Standalone validator (no UI dependency)
        """
        self.helper = InstrumentHelper()
        self.broker = AngelClient()

        if getattr(self.broker, "smart_api", None) is None:
            raise RuntimeError("Broker login failed")

    # -----------------------------------
    # Utils
    # -----------------------------------
    def _get_latest_input_csv(self, folder):
        files = [
            f for f in os.listdir(folder)
            if f.startswith(INPUT_CSV_PREFIX) and f.endswith(".csv")
        ]
        if not files:
            raise FileNotFoundError("No rangebound_symbols_*.csv found")

        files.sort(reverse=True)
        return os.path.join(folder, files[0])

    def _read_symbols(self, csv_file):
        symbols = []
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                s = row.get("symbol")
                if s and s.strip():
                    symbols.append(s.strip().upper())
        return symbols

    def _export_valid_csv(self, rows, folder):
        os.makedirs(folder, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(folder, f"{OUTPUT_FILE_PREFIX}{ts}.csv")

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["symbol", "token", "symbolName"]
            )
            writer.writeheader()
            writer.writerows(rows)

        logger.info("📁 CSV written: %s", path)

    # -----------------------------------
    # CORE LOGIC
    # -----------------------------------
    def validate_from_csv(self):
        input_csv = self._get_latest_input_csv(RangeBoundOutput_DIR)
        logger.info("📄 Using input CSV: %s", input_csv)

        symbols = self._read_symbols(input_csv)
        logger.info("Total symbols loaded: %d", len(symbols))

        valid, failed = [], []

        for symbol in symbols:
            try:
                time.sleep(SEARCH_DELAY + random.uniform(0, 0.2))

                search_name = symbol.replace("-EQ", "")
                result = self.helper.search_symbol("NSE", search_name)

                if not result or not result.get("data"):
                    failed.append(symbol)
                    continue

                data = result["data"]

                def rank(ts):
                    for i, sfx in enumerate(SERIES_PRIORITY):
                        if ts.endswith(sfx):
                            return i
                    return len(SERIES_PRIORITY)

                data = sorted(data, key=lambda x: rank(x.get("tradingsymbol", "")))

                for r in data:
                    tsym = r.get("tradingsymbol")
                    token = r.get("symboltoken")

                    if not tsym or not token:
                        continue

                    df = self.broker.get_historical_data(tsym, token)

                    if df is None or df.empty:
                        continue

                    df = df.copy()
                    if "close" not in df.columns:
                        continue

                    df["close"] = pd.to_numeric(df["close"], errors="coerce")
                    df = df.dropna(subset=["close"])
                    df = df[df["close"] > 0]

                    if len(df) < MIN_ROWS:
                        continue

                    # ✅ FOUND
                    valid.append({
                        "symbol": tsym,
                        "token": str(token),
                        "symbolName": search_name
                    })
                    logger.info("✅ VALID: %s", tsym)
                    break

            except Exception:
                logger.exception("Error validating %s", symbol)
                failed.append(symbol)

        if valid:
            self._export_valid_csv(valid, RangeBoundOutput_DIR)

        logger.info("🎉 Done | Valid=%d | Failed=%d", len(valid), len(failed))


# -----------------------------------
# ENTRY POINT
# -----------------------------------
if __name__ == "__main__":
    TokenValidator().validate_from_csv()
