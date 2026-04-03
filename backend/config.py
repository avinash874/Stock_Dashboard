# Paths and knobs you might want to tweak without digging through the rest of the app.

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data_store"
DB_PATH = DATA_DIR / "stocks.db"

# Tickers we load on first run (NSE — yahoo wants a .NS suffix; we add that in code)
DEFAULT_NSE_SYMBOLS = [
    "RELIANCE",
    "TCS",
    "INFY",
    "HDFCBANK",
    "ICICIBANK",
    "HINDUNILVR",
    "ITC",
    "SBIN",
    "BHARTIARTL",
    "KOTAKBANK",
]

EXCHANGE_SUFFIX = ".NS"

# API responses: reuse answer for this many seconds before recomputing
CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", "120"))

# Be nice to Yahoo — small random pause between calls, batches, retries
YF_MIN_DELAY_SEC = float(os.environ.get("YF_MIN_DELAY_SEC", "1.0"))
YF_MAX_DELAY_SEC = float(os.environ.get("YF_MAX_DELAY_SEC", "3.0"))
YF_BATCH_SIZE = int(os.environ.get("YF_BATCH_SIZE", "4"))
YF_BATCH_PAUSE_SEC = float(os.environ.get("YF_BATCH_PAUSE_SEC", "5.0"))
YF_MAX_RETRIES = int(os.environ.get("YF_MAX_RETRIES", "3"))
YF_BASE_BACKOFF_SEC = float(os.environ.get("YF_BASE_BACKOFF_SEC", "2.0"))

# If we already have this many days for a symbol, skip re-downloading it during seed
YF_MIN_BARS_SKIP_SEED = int(os.environ.get("YF_MIN_BARS_SKIP_SEED", "120"))
