"""Pandas cleaning and metric computation for OHLCV data."""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS_52W = 252
MA_WINDOW = 7
VOL_WINDOW = 7


def clean_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize columns, parse dates, handle missing values."""
    if df.empty:
        return df

    out = df.copy()
    out = out.sort_index()
    if isinstance(out.index, pd.DatetimeIndex):
        out = out.reset_index()
    # yfinance: Date / datetime index column
    col_map = {c: c.lower().replace(" ", "_") for c in out.columns}
    out = out.rename(columns=col_map)
    date_candidates = ("date", "datetime")
    date_col = next((c for c in date_candidates if c in out.columns), None)
    if date_col is None:
        # first column is often the index-as-date
        date_col = out.columns[0]
    out = out.rename(columns={date_col: "date"})

    for c in ("open", "high", "low", "close", "volume"):
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")

    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    out = out.dropna(subset=["date"])
    numeric_cols = [c for c in ("open", "high", "low", "close", "volume") if c in out.columns]
    out[numeric_cols] = out[numeric_cols].replace([np.inf, -np.inf], np.nan)
    out[numeric_cols] = out[numeric_cols].ffill().bfill()
    out = out.dropna(subset=["close", "open"], how="any")
    return out


def add_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Daily return, MA7, 52-week high/low, annualized volatility (custom)."""
    if df.empty:
        return df

    out = df.copy()
    out["daily_return"] = (out["close"] - out["open"]) / out["open"].replace(0, np.nan)
    out["ma7"] = out["close"].rolling(window=MA_WINDOW, min_periods=1).mean()
    out["week52_high"] = out["high"].rolling(window=TRADING_DAYS_52W, min_periods=1).max()
    out["week52_low"] = out["low"].rolling(window=TRADING_DAYS_52W, min_periods=1).min()

    # Log returns for volatility; annualized rolling std
    log_ret = np.log(out["close"] / out["close"].shift(1))
    out["volatility"] = (
        log_ret.rolling(window=VOL_WINDOW, min_periods=2).std() * np.sqrt(TRADING_DAYS_52W)
    )

    out["daily_return"] = out["daily_return"].replace([np.inf, -np.inf], np.nan)
    return out
