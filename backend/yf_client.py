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
    low = min(YF_MIN_DELAY_SEC, YF_MAX_DELAY_SEC)
    high = max(YF_MIN_DELAY_SEC, YF_MAX_DELAY_SEC)
    time.sleep(random.uniform(low, high))


def sleep_between_batches(seconds: float) -> None:
    time.sleep(seconds)


def _looks_like_network_glitch(err: BaseException) -> bool:
    text = str(err).lower()
    if "too many requests" in text or "rate limit" in text or "429" in text:
        return True
    if "timeout" in text or "timed out" in text:
        return True
    if "connection" in text and ("reset" in text or "refused" in text or "aborted" in text):
        return True
    if "temporarily" in text or "try again" in text:
        return True
    return False


def fetch_history_with_retry(
    yf_symbol: str,
    period: str = "2y",
    *,
    max_retries: int | None = None,
) -> pd.DataFrame:
    retries = YF_MAX_RETRIES if max_retries is None else max_retries
    total_tries = retries + 1
    last_error: BaseException | None = None

    for i in range(total_tries):
        try:
            ticker = yf.Ticker(yf_symbol)
            hist = ticker.history(period=period, auto_adjust=True, repair=True)
            if isinstance(hist.columns, pd.MultiIndex):
                hist.columns = hist.columns.get_level_values(0)
            if hist.empty:
                logger.warning("Yahoo returned no rows for %s", yf_symbol)
            return hist
        except Exception as e:
            last_error = e
            giving_up = i == total_tries - 1
            if not giving_up and _looks_like_network_glitch(e):
                wait = YF_BASE_BACKOFF_SEC * (2**i) + random.uniform(0.0, 1.5)
                logger.warning(
                    "Fetch %s failed (%s), try %s/%s — waiting %.1fs",
                    yf_symbol,
                    type(e).__name__,
                    i + 1,
                    total_tries,
                    wait,
                )
                time.sleep(wait)
                continue
            logger.error("Giving up on %s after %s tries: %s", yf_symbol, i + 1, e)
            raise last_error from None

    assert last_error is not None
    raise last_error


def company_name_from_ticker(ticker: yf.Ticker, fallback: str) -> str:
    # fast_info is lighter than ticker.info (fewer round trips)
    try:
        fast = getattr(ticker, "fast_info", None)
        if fast is None:
            return fallback
        if hasattr(fast, "get"):
            bag = fast
        elif hasattr(fast, "items"):
            bag = dict(fast.items())
        else:
            bag = {}
        name = bag.get("longName") or bag.get("shortName") or bag.get("short_name")
        if name:
            return str(name)
    except Exception:
        logger.debug("Could not read company name from fast_info", exc_info=True)
    return fallback
