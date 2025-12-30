CAPITAL = 500000        # change as needed
RISK_PERCENT = 1.0
TIMEFRAME_ENTRY = "15m"
REQUEST_DELAY_SEC = 1.2        # between symbols
ERROR_COOLDOWN_SEC = 5         # after exception
SEARCH_DELAY = 0.35        # seconds between search calls
HISTORY_DELAY = 0.50       # seconds between historical calls
RETRY_DELAY = 1.5          # base retry delay
MAX_RETRIES = 3

# ---------------- TRADING MODE ----------------
PAPER_TRADE = True

# ---------------- SWING RULES ----------------
MAX_OPEN_TRADES = 5
SWING_PLAN_EXPIRY_DAYS = 7
MAX_CAPITAL_UTILIZATION = 0.60   # 60%
ALLOW_TRAILING_SL = True
TRAIL_SL_AT_R = 1.0              # Start trailing after 1R
TRAIL_SL_MULTIPLIER = 1.0        # ATR or R based

# ---------------- PARTIAL BOOKING ----------------
ENABLE_PARTIAL_BOOKING = True
PARTIAL_BOOK_RR = 1.0
PARTIAL_BOOK_PERCENT = 0.5
PARTIAL_BOOK_RR = 1.0
HARD_EXIT_R_MULTIPLE = 2.0

# ---------------- SAFETY ----------------
DISABLE_NEW_TRADES = False

# SL behavior
SL_ON_CLOSE = True   # True = swing mode, False = intraday mode
