import logging
from db.tradefindinstrument_db import TradeFindDB
from utils.file_handler import load_symbols_from_csv
from utils.symbol_resolver import SymbolResolver
from config.settings import RangeBoundInput_DIR


# ------------------------------
# CONFIG
# ------------------------------
INPUT_FOLDER = RangeBoundInput_DIR


# ------------------------------
# LOGGER
# ------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s"
)
logger = logging.getLogger("initial_insert")


# ------------------------------
# MAIN FUNCTION
# ------------------------------
def initial_insert_symbols(input_folder):
    logger.info(f"🔍 Scanning folder for CSV symbols: {input_folder}")

    # Step 1: Load symbols
    try:
        names = load_symbols_from_csv(input_folder)
        if not names:
            logger.warning("⚠ No symbols found.")
            return
        logger.info(f"📄 Found {len(names)} symbols.")
    except Exception as e:
        logger.error(f"❌ Error loading symbols: {e}")
        return

    resolver = SymbolResolver()
    inserted, rejected = 0, []

    # Track symbols seen in this run (for soft delete later)
    seen_symbols = set()

    # Step 2: DB operations (context manager)
    with TradeFindDB() as db:
        for sym in names:
            sym = sym.strip().upper()
            if not sym:
                continue

            mapping = resolver.resolve_symbol_tradefinder(sym)
            if not mapping:
                rejected.append(f"{sym} → No mapping found")
                continue

            trading_symbol = mapping.get("trading_symbol")
            token = mapping.get("token")

            if not trading_symbol or not token:
                rejected.append(f"{sym} → Incomplete mapping")
                continue

            ok = db.upsert_symbol(
                symbol=sym,
                trading_symbol=trading_symbol,
                token=str(token)
            )

            if ok:
                logger.info(f"✅ Inserted/Updated: {sym} → {trading_symbol} ({token})")
                inserted += 1
                seen_symbols.add(sym)
            else:
                logger.warning(f"⏭ Failed: {sym}")

        # ----------------------------------
        # OPTIONAL: SOFT DELETE MISSING SYMBOLS
        # ----------------------------------
        # Uncomment ONLY if you want this behavior
        #
        # active_rows = db.get_active()
        # for row in active_rows:
        #     if row["symbol"] not in seen_symbols:
        #         db.deactivate_symbol(row["symbol"])
        #         logger.info(f"🛑 Deactivated: {row['symbol']}")

    logger.info("🎉 INITIAL IMPORT COMPLETE")
    logger.info(f"➡ Inserted / Updated: {inserted}")
    logger.info(f"➡ Rejected: {len(rejected)}")

def get_symbols_for_validation(self):
    """
    Placeholder method.

    Responsibility:
    - Return a normalized list of symbols to be validated.
    - Future versions may:
        - Pull from DB
        - Merge multiple sources
        - Apply filters (watchlist, sector, etc.)

    Expected return:
        List[str]
    """
    return []
# ------------------------------
# ENTRY POINT
# ------------------------------
if __name__ == "__main__":
    initial_insert_symbols(INPUT_FOLDER)
