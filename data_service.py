"""Fetch stock data via yfinance and persist to SQLite."""
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

# Last seed run summary (for /health and ops)
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
    """Download, clean, compute metrics, upsert rows. Returns row count."""
    yf_sym = to_yfinance_symbol(display_symbol)
    raw = fetch_history_with_retry(yf_sym)
    if raw.empty:
        return 0

    cleaned = clean_ohlcv(raw)
    if cleaned.empty:
        return 0

    enriched = add_metrics(cleaned)
    ticker = yf.Ticker(yf_sym)
    long_name = company_name_from_ticker(ticker, display_symbol)

    rows = 0
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO companies (symbol, display_symbol, name, exchange)
            VALUES (?, ?, ?, 'NSE')
            ON CONFLICT(symbol) DO UPDATE SET
                name = excluded.name,
                display_symbol = excluded.display_symbol
            """,
            (yf_sym, from_yfinance_symbol(yf_sym), long_name),
        )

        for _, row in enriched.iterrows():
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
            rows += 1

    return rows


def _run_ingest_safe(display_symbol: str) -> tuple[int, bool]:
    """Returns (rows, ok). Never raises."""
    try:
        n = ingest_symbol(display_symbol)
        return n, n > 0
    except Exception as e:
        logger.warning("Ingest failed for %s: %s", display_symbol, e)
        return 0, False


def seed_default_universe() -> None:
    """
    Ingest default NSE list with throttling, batching, retries, and a final retry pass.
    Skips symbols that already have enough rows in DB. One failure does not stop others.
    """
    global LAST_SEED_RESULT

    pending: list[str] = []
    skipped_db = 0
    for sym in DEFAULT_NSE_SYMBOLS:
        if count_bars_for_symbol(sym) >= YF_MIN_BARS_SKIP_SEED:
            skipped_db += 1
            logger.info("Seed skip %s — already have >= %s bars in DB", sym, YF_MIN_BARS_SKIP_SEED)
        else:
            pending.append(sym)

    if not pending:
        LAST_SEED_RESULT = {
            "status": "done",
            "ingested_ok": 0,
            "skipped_db": skipped_db,
            "failed": [],
        }
        logger.info("Seed: nothing to fetch (all symbols skipped or empty list).")
        return

    LAST_SEED_RESULT = {
        "status": "running",
        "ingested_ok": 0,
        "skipped_db": skipped_db,
        "failed": [],
    }

    failed: list[str] = []
    ok_count = 0
    batch = max(1, YF_BATCH_SIZE)

    def process_list(symbols: list[str], phase: str) -> None:
        nonlocal ok_count, failed
        for i, sym in enumerate(symbols):
            if i > 0:
                if i % batch == 0:
                    sleep_between_batches(YF_BATCH_PAUSE_SEC)
                else:
                    sleep_between_symbols()
            n, success = _run_ingest_safe(sym)
            if success:
                ok_count += 1
                LAST_SEED_RESULT["ingested_ok"] = ok_count
                logger.info("[%s] Ingested %s: %s rows", phase, sym, n)
            else:
                if sym not in failed:
                    failed.append(sym)
                logger.error("[%s] Failed or empty ingest for %s", phase, sym)

    process_list(pending, "phase1")

    if failed:
        logger.warning("Retrying %s symbols after cooldown: %s", len(failed), failed)
        sleep_between_batches(max(YF_BATCH_PAUSE_SEC, 8.0))
        retry_syms = failed[:]
        failed = []
        process_list(retry_syms, "retry")

    LAST_SEED_RESULT = {
        "status": "done",
        "ingested_ok": ok_count,
        "skipped_db": skipped_db,
        "failed": failed,
    }
    if failed:
        logger.error("Seed finished with unresolved failures: %s", failed)
    else:
        logger.info("Seed finished: ok=%s skipped_db=%s", ok_count, skipped_db)


def load_bars_dataframe(symbol: str, start: datetime | None = None) -> pd.DataFrame:
    yf_sym = to_yfinance_symbol(symbol)
    with get_connection() as conn:
        if start:
            q = (
                "SELECT * FROM stock_bars WHERE symbol = ? AND bar_date >= ? ORDER BY bar_date"
            )
            df = pd.read_sql_query(q, conn, params=(yf_sym, start.strftime("%Y-%m-%d")))
        else:
            q = "SELECT * FROM stock_bars WHERE symbol = ? ORDER BY bar_date"
            df = pd.read_sql_query(q, conn, params=(yf_sym,))
    if not df.empty and "bar_date" in df.columns:
        df["bar_date"] = pd.to_datetime(df["bar_date"])
    return df


def correlation_between(s1: str, s2: str, days: int = 90) -> float | None:
    """Pearson correlation of daily close-to-close returns over last `days` bars."""
    start = datetime.utcnow() - timedelta(days=days * 2)
    a = load_bars_dataframe(s1, start=start)
    b = load_bars_dataframe(s2, start=start)
    if a.empty or b.empty:
        return None
    a = a.sort_values("bar_date").tail(days)
    b = b.sort_values("bar_date").tail(days)
    merged = a[["bar_date", "close"]].merge(
        b[["bar_date", "close"]], on="bar_date", suffixes=("_a", "_b")
    )
    if len(merged) < 10:
        return None
    ra = merged["close_a"].pct_change().dropna()
    rb = merged["close_b"].pct_change().dropna()
    aligned = pd.concat([ra, rb], axis=1, join="inner").dropna()
    if len(aligned) < 5:
        return None
    return float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1]))
