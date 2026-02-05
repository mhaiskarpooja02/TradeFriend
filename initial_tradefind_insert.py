import os
import csv
import logging
from datetime import datetime

from utils.file_handler import load_symbols_from_csv
from config.settings import RangeBoundInput_DIR, RangeBoundOutput_DIR


# ------------------------------
# LOGGER
# ------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s"
)
logger = logging.getLogger("symbol_csv_only")


# ------------------------------
# MAIN FUNCTION
# ------------------------------
def generate_symbol_csv(input_folder, output_folder):
    logger.info(f"🔍 Reading symbols from: {input_folder}")

    try:
        symbols = load_symbols_from_csv(input_folder)
        if not symbols:
            logger.warning("⚠ No symbols found.")
            return
    except Exception as e:
        logger.error(f"❌ Failed to read symbols: {e}")
        return

    # Normalize + deduplicate
    clean_symbols = sorted({
        s.strip().upper()
        for s in symbols
        if s and s.strip()
    })

    logger.info(f"📄 Total unique symbols: {len(clean_symbols)}")

    # Ensure output folder exists
    os.makedirs(output_folder, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(
        output_folder,
        f"rangebound_symbols_{ts}.csv"
    )

    # Write CSV
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["symbol"])
        for sym in clean_symbols:
            writer.writerow([sym])

    logger.info("🎉 SYMBOL CSV CREATED")
    logger.info(f"📁 File saved at: {output_file}")


# ------------------------------
# ENTRY POINT
# ------------------------------
if __name__ == "__main__":
    generate_symbol_csv(
        input_folder=RangeBoundInput_DIR,
        output_folder=RangeBoundOutput_DIR
    )
