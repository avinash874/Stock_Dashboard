"""Application configuration."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data_store"
DB_PATH = DATA_DIR / "stocks.db"

# NSE symbols for yfinance (suffix .NS)
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
CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", "120"))

# yfinance throttling (see yf_client + data_service seeding)
YF_MIN_DELAY_SEC = float(os.environ.get("YF_MIN_DELAY_SEC", "1.0"))
YF_MAX_DELAY_SEC = float(os.environ.get("YF_MAX_DELAY_SEC", "3.0"))
YF_BATCH_SIZE = int(os.environ.get("YF_BATCH_SIZE", "4"))
YF_BATCH_PAUSE_SEC = float(os.environ.get("YF_BATCH_PAUSE_SEC", "5.0"))
# Retries after first failed attempt (total attempts = YF_MAX_RETRIES + 1)
YF_MAX_RETRIES = int(os.environ.get("YF_MAX_RETRIES", "3"))
YF_BASE_BACKOFF_SEC = float(os.environ.get("YF_BASE_BACKOFF_SEC", "2.0"))
# Skip full re-fetch during seed if symbol already has this many bars
YF_MIN_BARS_SKIP_SEED = int(os.environ.get("YF_MIN_BARS_SKIP_SEED", "120"))
