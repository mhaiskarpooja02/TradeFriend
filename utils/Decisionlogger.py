import logging
import os
import sys
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

from config.settings import LOG_DIR

# ---------------------------------------------------------------------
# Ensure log directory exists
# ---------------------------------------------------------------------
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "Decisionapp.log")
ORDER_LOG_FILE = os.path.join(LOG_DIR, "orders.log")

# ---------------------------------------------------------------------
# Safe text sanitizer
# ---------------------------------------------------------------------
def sanitize_for_log(text: str) -> str:
    """Remove or replace characters not supported by console encoding."""
    if not isinstance(text, str):
        return str(text)
    try:
        return text.encode(
            sys.stdout.encoding or "utf-8", errors="replace"
        ).decode("utf-8")
    except Exception:
        return text.encode("ascii", errors="ignore").decode("ascii")

# ---------------------------------------------------------------------
# Main logger (APP LOG)
# ---------------------------------------------------------------------
def get_logger(name=__name__):
    """
    Returns a UTF-8 safe logger with:
    - Daily rotating file logs
    - Console output
    - Sanitized text
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # IMPORTANT: prevent duplicate handlers
    if not logger.handlers:

        # -------------------------------
        # FILE HANDLER (DAILY ROTATION)
        # -------------------------------
        fh = TimedRotatingFileHandler(
            LOG_FILE,
            when="midnight",
            interval=1,
            backupCount=14,          # keep last 14 days
            encoding="utf-8"
        )
        fh.suffix = "%Y-%m-%d"
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ))

        # -------------------------------
        # CONSOLE HANDLER
        # -------------------------------
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        ))

        # Reconfigure stdout encoding (Python 3.10+)
        if hasattr(ch.stream, "reconfigure"):
            try:
                ch.stream.reconfigure(encoding="utf-8")
            except Exception:
                pass

        # -------------------------------
        # ADD HANDLERS
        # -------------------------------
        logger.addHandler(fh)
        logger.addHandler(ch)

        # -------------------------------
        # SANITIZE LOG TEXT
        # -------------------------------
        _info = logger.info
        _warning = logger.warning
        _error = logger.error
        _exception = logger.exception

        logger.info = lambda msg, *a, **kw: _info(
            sanitize_for_log(str(msg)), *a, **kw
        )
        logger.warning = lambda msg, *a, **kw: _warning(
            sanitize_for_log(str(msg)), *a, **kw
        )
        logger.error = lambda msg, *a, **kw: _error(
            sanitize_for_log(str(msg)), *a, **kw
        )
        logger.exception = lambda msg, *a, **kw: _exception(
            sanitize_for_log(str(msg)), *a, **kw
        )

    return logger

# ---------------------------------------------------------------------
# Order logger (ORDERS LOG – FILE ONLY)
# ---------------------------------------------------------------------
def get_order_logger():
    """
    Dedicated UTF-8 safe logger for order placement:
    - Daily rotating file logs
    - No console output
    """
    order_logger = logging.getLogger("orders")
    order_logger.setLevel(logging.DEBUG)

    if not order_logger.handlers:

        fh = TimedRotatingFileHandler(
            ORDER_LOG_FILE,
            when="midnight",
            interval=1,
            backupCount=30,          # keep last 30 days
            encoding="utf-8"
        )
        fh.suffix = "%Y-%m-%d"
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        ))

        order_logger.addHandler(fh)

        # Sanitize order logs
        _info = order_logger.info
        _error = order_logger.error
        _exception = order_logger.exception

        order_logger.info = lambda msg, *a, **kw: _info(
            sanitize_for_log(str(msg)), *a, **kw
        )
        order_logger.error = lambda msg, *a, **kw: _error(
            sanitize_for_log(str(msg)), *a, **kw
        )
        order_logger.exception = lambda msg, *a, **kw: _exception(
            sanitize_for_log(str(msg)), *a, **kw
        )

    return order_logger
