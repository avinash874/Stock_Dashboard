"""Fetch stock data via yfinance and persist to SQLite."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from config import DEFAULT_NSE_SYMBOLS, EXCHANGE_SUFFIX
from data_processor import add_metrics, clean_ohlcv
from database import get_connection

logger = logging.getLogger(__name__)


def to_yfinance_symbol(symbol: str) -> str:
    s = symbol.strip().upper().replace(".NS", "").replace(".BO", "")
    return f"{s}{EXCHANGE_SUFFIX}"


def from_yfinance_symbol(yf_symbol: str) -> str:
    return yf_symbol.replace(EXCHANGE_SUFFIX, "").upper()


def fetch_history(yf_symbol: str, period: str = "2y") -> pd.DataFrame:
    ticker = yf.Ticker(yf_symbol)
    df = ticker.history(period=period, auto_adjust=True, repair=True)
    if df.empty:
        logger.warning("No data returned for %s", yf_symbol)
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def ingest_symbol(display_symbol: str) -> int:
    """Download, clean, compute metrics, upsert rows. Returns row count."""
    yf_sym = to_yfinance_symbol(display_symbol)
    raw = fetch_history(yf_sym)
    if raw.empty:
        return 0

    cleaned = clean_ohlcv(raw)
    if cleaned.empty:
        return 0

    enriched = add_metrics(cleaned)
    ticker = yf.Ticker(yf_sym)
    info = ticker.info or {}
    long_name = info.get("longName") or info.get("shortName") or display_symbol

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


def seed_default_universe() -> None:
    for sym in DEFAULT_NSE_SYMBOLS:
        try:
            n = ingest_symbol(sym)
            logger.info("Ingested %s: %s rows", sym, n)
        except Exception as e:
            logger.exception("Failed to ingest %s: %s", sym, e)


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
