import logging
import os
import sys
from config.settings import LOG_DIR

# Ensure log directory exists
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE = os.path.join(LOG_DIR, "app.log")
ORDER_LOG_FILE = os.path.join(LOG_DIR, "orders.log")

# ---------------------------------------------------------------------
# Safe text sanitizer
# ---------------------------------------------------------------------
def sanitize_for_log(text: str) -> str:
    """Remove or replace characters not supported by console encoding."""
    if not isinstance(text, str):
        return str(text)
    try:
        return text.encode(sys.stdout.encoding or "utf-8", errors="replace").decode("utf-8")
    except Exception:
        # Fallback: strip to ASCII if encoding still fails
        return text.encode("ascii", errors="ignore").decode("ascii")

# ---------------------------------------------------------------------
# Main logger
# ---------------------------------------------------------------------
def get_logger(name=__name__):
    """Returns a UTF-8 safe logger with console and file handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        # --- File Handler ---
        fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
        fh.setLevel(logging.INFO)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        fh.setFormatter(file_formatter)

        # --- Console Handler ---
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

        # Reconfigure stream encoding (Python 3.10+)
        if hasattr(ch.stream, "reconfigure"):
            try:
                ch.stream.reconfigure(encoding="utf-8")
            except Exception:
                pass

        # --- Add Handlers ---
        logger.addHandler(fh)
        logger.addHandler(ch)

        # --- Patch logger.info/warning/error to sanitize text ---
        _info = logger.info
        _warning = logger.warning
        _error = logger.error

        logger.info = lambda msg, *a, **kw: _info(sanitize_for_log(str(msg)), *a, **kw)
        logger.warning = lambda msg, *a, **kw: _warning(sanitize_for_log(str(msg)), *a, **kw)
        logger.error = lambda msg, *a, **kw: _error(sanitize_for_log(str(msg)), *a, **kw)

    return logger

# ---------------------------------------------------------------------
# Order logger
# ---------------------------------------------------------------------
def get_order_logger():
    """Dedicated UTF-8 safe logger for order placement (file only)."""
    order_logger = logging.getLogger("orders")
    order_logger.setLevel(logging.DEBUG)

    if not order_logger.handlers:
        fh = logging.FileHandler(ORDER_LOG_FILE, mode="a", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        order_logger.addHandler(fh)

        # Sanitize all order logs
        _info = order_logger.info
        _error = order_logger.error
        order_logger.info = lambda msg, *a, **kw: _info(sanitize_for_log(str(msg)), *a, **kw)
        order_logger.error = lambda msg, *a, **kw: _error(sanitize_for_log(str(msg)), *a, **kw)

    return order_logger
