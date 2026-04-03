from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import yfinance as yf

from config import (
    DEFAULT_NSE_SYMBOLS,
    EXCHANGE_SUFFIX,
    YF_BATCH_PAUSE_SEC,
    YF_BATCH_SIZE,
    YF_MIN_BARS_SKIP_SEED,
)
from data_processor import add_metrics, clean_ohlcv
from database import get_connection
from yf_client import (
    company_name_from_ticker,
    fetch_history_with_retry,
    sleep_between_batches,
    sleep_between_symbols,
)

logger = logging.getLogger(__name__)

# Filled in when we bulk-download tickers at startup — /health reads this
LAST_SEED_RESULT: dict[str, Any] = {
    "status": "idle",
    "ingested_ok": 0,
    "skipped_db": 0,
    "failed": [],
}


def to_yfinance_symbol(symbol: str) -> str:
    s = symbol.strip().upper().replace(".NS", "").replace(".BO", "")
    return f"{s}{EXCHANGE_SUFFIX}"


def from_yfinance_symbol(yf_symbol: str) -> str:
    return yf_symbol.replace(EXCHANGE_SUFFIX, "").upper()


def count_bars_for_symbol(display_symbol: str) -> int:
    yf_sym = to_yfinance_symbol(display_symbol)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM stock_bars WHERE symbol = ?",
            (yf_sym,),
        ).fetchone()
    return int(row["c"]) if row else 0


def ingest_symbol(display_symbol: str) -> int:
    """Pull history from Yahoo, clean it, save. Returns how many daily rows we wrote."""
    yf_sym = to_yfinance_symbol(display_symbol)
    raw = fetch_history_with_retry(yf_sym)
    if raw.empty:
        return 0

    cleaned = clean_ohlcv(raw)
    if cleaned.empty:
        return 0

    with_metrics = add_metrics(cleaned)
    ticker = yf.Ticker(yf_sym)
    company_name = company_name_from_ticker(ticker, display_symbol)

    rows_written = 0
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO companies (symbol, display_symbol, name, exchange)
            VALUES (?, ?, ?, 'NSE')
            ON CONFLICT(symbol) DO UPDATE SET
                name = excluded.name,
                display_symbol = excluded.display_symbol
            """,
            (yf_sym, from_yfinance_symbol(yf_sym), company_name),
        )

        for _, row in with_metrics.iterrows():
            d = row["date"]
            if hasattr(d, "strftime"):
                date_str = d.strftime("%Y-%m-%d")
            else:
                date_str = str(pd.Timestamp(d).date())

            conn.execute(
                """
                INSERT INTO stock_bars (
                    symbol, bar_date, open, high, low, close, volume,
                    daily_return, ma7, week52_high, week52_low, volatility
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, bar_date) DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    volume = excluded.volume,
                    daily_return = excluded.daily_return,
                    ma7 = excluded.ma7,
                    week52_high = excluded.week52_high,
                    week52_low = excluded.week52_low,
                    volatility = excluded.volatility
                """,
                (
                    yf_sym,
                    date_str,
                    float(row["open"]),
                    float(row["high"]),
                    float(row["low"]),
                    float(row["close"]),
                    float(row.get("volume", 0) or 0),
                    float(row["daily_return"]) if pd.notna(row["daily_return"]) else None,
                    float(row["ma7"]) if pd.notna(row["ma7"]) else None,
                    float(row["week52_high"]) if pd.notna(row["week52_high"]) else None,
                    float(row["week52_low"]) if pd.notna(row["week52_low"]) else None,
                    float(row["volatility"]) if pd.notna(row["volatility"]) else None,
                ),
            )
            rows_written += 1

    return rows_written


def try_ingest_one(display_symbol: str) -> tuple[int, bool]:
    """Returns (rows_written, worked). Swallows errors so one bad ticker doesn't kill the batch."""
    try:
        n = ingest_symbol(display_symbol)
        return n, n > 0
    except Exception as e:
        logger.warning("Ingest failed for %s: %s", display_symbol, e)
        return 0, False


def seed_default_universe() -> None:
    """Download our default list of NSE stocks. Slow on purpose — we pause between Yahoo calls."""
    global LAST_SEED_RESULT

    need_fetch: list[str] = []
    skipped_already_full = 0
    for sym in DEFAULT_NSE_SYMBOLS:
        if count_bars_for_symbol(sym) >= YF_MIN_BARS_SKIP_SEED:
            skipped_already_full += 1
            logger.info("Skip %s — already have %s+ bars", sym, YF_MIN_BARS_SKIP_SEED)
        else:
            need_fetch.append(sym)

    if not need_fetch:
        LAST_SEED_RESULT = {
            "status": "done",
            "ingested_ok": 0,
            "skipped_db": skipped_already_full,
            "failed": [],
        }
        logger.info("Nothing to download (everything skipped or empty list).")
        return

    LAST_SEED_RESULT = {
        "status": "running",
        "ingested_ok": 0,
        "skipped_db": skipped_already_full,
        "failed": [],
    }

    failed_symbols: list[str] = []
    success_count = 0
    batch_size = max(1, YF_BATCH_SIZE)

    def run_through(symbols: list[str], label: str) -> None:
        nonlocal success_count, failed_symbols
        for i, sym in enumerate(symbols):
            if i > 0:
                if i % batch_size == 0:
                    sleep_between_batches(YF_BATCH_PAUSE_SEC)
                else:
                    sleep_between_symbols()

            rows, ok = try_ingest_one(sym)
            if ok:
                success_count += 1
                LAST_SEED_RESULT["ingested_ok"] = success_count
                logger.info("[%s] %s — saved %s rows", label, sym, rows)
            else:
                if sym not in failed_symbols:
                    failed_symbols.append(sym)
                logger.error("[%s] %s — no data or error", label, sym)

    run_through(need_fetch, "round1")

    if failed_symbols:
        logger.warning("Retrying %s tickers after a longer pause: %s", len(failed_symbols), failed_symbols)
        sleep_between_batches(max(YF_BATCH_PAUSE_SEC, 8.0))
        retry_list = failed_symbols[:]
        failed_symbols = []
        run_through(retry_list, "retry")

    LAST_SEED_RESULT = {
        "status": "done",
        "ingested_ok": success_count,
        "skipped_db": skipped_already_full,
        "failed": failed_symbols,
    }
    if failed_symbols:
        logger.error("Still failed after retry: %s", failed_symbols)
    else:
        logger.info("Seed done: ok=%s skipped=%s", success_count, skipped_already_full)


def load_bars_dataframe(symbol: str, start: datetime | None = None) -> pd.DataFrame:
    yf_sym = to_yfinance_symbol(symbol)
    with get_connection() as conn:
        if start:
            sql = (
                "SELECT * FROM stock_bars WHERE symbol = ? AND bar_date >= ? ORDER BY bar_date"
            )
            df = pd.read_sql_query(sql, conn, params=(yf_sym, start.strftime("%Y-%m-%d")))
        else:
            sql = "SELECT * FROM stock_bars WHERE symbol = ? ORDER BY bar_date"
            df = pd.read_sql_query(sql, conn, params=(yf_sym,))
    if not df.empty and "bar_date" in df.columns:
        df["bar_date"] = pd.to_datetime(df["bar_date"])
    return df


def correlation_between(stock_a: str, stock_b: str, days: int = 90) -> float | None:
    """How similarly the two stocks move day to day (-1 to 1). Needs enough overlapping dates."""
    start = datetime.utcnow() - timedelta(days=days * 2)
    a = load_bars_dataframe(stock_a, start=start)
    b = load_bars_dataframe(stock_b, start=start)
    if a.empty or b.empty:
        return None

    a = a.sort_values("bar_date").tail(days)
    b = b.sort_values("bar_date").tail(days)
    both = a[["bar_date", "close"]].merge(
        b[["bar_date", "close"]], on="bar_date", suffixes=("_a", "_b")
    )
    if len(both) < 10:
        return None

    ret_a = both["close_a"].pct_change().dropna()
    ret_b = both["close_b"].pct_change().dropna()
    together = pd.concat([ret_a, ret_b], axis=1, join="inner").dropna()
    if len(together) < 5:
        return None
    return float(together.iloc[:, 0].corr(together.iloc[:, 1]))
