"""yfinance access with throttling, retries, and exponential backoff."""
from __future__ import annotations

import logging
import random
import time
from typing import Any

import pandas as pd
import yfinance as yf

from config import YF_BASE_BACKOFF_SEC, YF_MAX_DELAY_SEC, YF_MAX_RETRIES, YF_MIN_DELAY_SEC

logger = logging.getLogger(__name__)


def sleep_between_symbols() -> None:
    """Random delay between symbol requests (rate-limit friendly)."""
    lo, hi = min(YF_MIN_DELAY_SEC, YF_MAX_DELAY_SEC), max(YF_MIN_DELAY_SEC, YF_MAX_DELAY_SEC)
    time.sleep(random.uniform(lo, hi))


def sleep_between_batches(batch_pause_sec: float) -> None:
    time.sleep(batch_pause_sec)


def _is_transient_yf_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    if "too many requests" in msg or "rate limit" in msg or "429" in msg:
        return True
    if "timeout" in msg or "timed out" in msg:
        return True
    if "connection" in msg and ("reset" in msg or "refused" in msg or "aborted" in msg):
        return True
    if "temporarily" in msg or "try again" in msg:
        return True
    return False


def fetch_history_with_retry(
    yf_symbol: str,
    period: str = "2y",
    *,
    max_retries: int | None = None,
) -> pd.DataFrame:
    """
    Download OHLCV history with retries and exponential backoff on transient errors.
    max_retries: extra attempts after the first (total attempts = max_retries + 1).
    """
    retries = YF_MAX_RETRIES if max_retries is None else max_retries
    attempts = retries + 1
    last_exc: BaseException | None = None

    for attempt in range(attempts):
        try:
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(period=period, auto_adjust=True, repair=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if df.empty:
                logger.warning("No data returned for %s", yf_symbol)
            return df
        except Exception as e:
            last_exc = e
            is_last = attempt == attempts - 1
            if not is_last and _is_transient_yf_error(e):
                wait = YF_BASE_BACKOFF_SEC * (2**attempt) + random.uniform(0.0, 1.5)
                logger.warning(
                    "yfinance history attempt %s/%s failed for %s (%s): %s — sleeping %.1fs",
                    attempt + 1,
                    attempts,
                    yf_symbol,
                    type(e).__name__,
                    e,
                    wait,
                )
                time.sleep(wait)
                continue
            logger.error(
                "yfinance history failed for %s after %s attempts: %s",
                yf_symbol,
                attempt + 1,
                e,
            )
            raise last_exc from None

    assert last_exc is not None
    raise last_exc


def company_name_from_ticker(ticker: yf.Ticker, fallback: str) -> str:
    """
    Prefer fast_info over full info (fewer HTTP calls, lighter payload).
    """
    try:
        fi: Any = getattr(ticker, "fast_info", None)
        if fi is None:
            return fallback
        if hasattr(fi, "get"):
            d = fi
        elif hasattr(fi, "items"):
            d = dict(fi.items())
        else:
            d = {}
        name = d.get("longName") or d.get("shortName") or d.get("short_name")
        if name:
            return str(name)
    except Exception:
        logger.debug("fast_info unavailable for ticker", exc_info=True)
    return fallback
