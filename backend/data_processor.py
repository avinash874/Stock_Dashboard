from __future__ import annotations

import numpy as np
import pandas as pd

# Roughly one trading year — used for 52-week high/low style numbers
DAYS_PER_TRADING_YEAR = 252
MOVING_AVG_DAYS = 7
VOLATILITY_LOOKBACK_DAYS = 7


def clean_ohlcv(raw: pd.DataFrame) -> pd.DataFrame:
    """Turn yfinance's table into a tidy daily table: one row per day, numeric columns."""
    if raw.empty:
        return raw

    df = raw.copy()
    df = df.sort_index()
    if isinstance(df.index, pd.DatetimeIndex):
        df = df.reset_index()

    df = df.rename(columns={c: c.lower().replace(" ", "_") for c in df.columns})
    for name in ("date", "datetime"):
        if name in df.columns:
            df = df.rename(columns={name: "date"})
            break
    else:
        df = df.rename(columns={df.columns[0]: "date"})

    for col in ("open", "high", "low", "close", "volume"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df = df.dropna(subset=["date"])

    numeric = [c for c in ("open", "high", "low", "close", "volume") if c in df.columns]
    df[numeric] = df[numeric].replace([np.inf, -np.inf], np.nan)
    df[numeric] = df[numeric].ffill().bfill()
    df = df.dropna(subset=["close", "open"], how="any")
    return df


def add_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add columns we show in the API: return %, 7-day avg close, 52w range, volatility."""
    if df.empty:
        return df

    out = df.copy()

    # Same day: (close - open) / open
    out["daily_return"] = (out["close"] - out["open"]) / out["open"].replace(0, np.nan)

    # Simple moving average of close
    out["ma7"] = out["close"].rolling(window=MOVING_AVG_DAYS, min_periods=1).mean()

    # Highest high / lowest low in the last ~252 trading sessions (rolling window)
    out["week52_high"] = out["high"].rolling(window=DAYS_PER_TRADING_YEAR, min_periods=1).max()
    out["week52_low"] = out["low"].rolling(window=DAYS_PER_TRADING_YEAR, min_periods=1).min()

    # Volatility: std of log returns, then scale to "per year" (hand-wavy but standard trick)
    log_return = np.log(out["close"] / out["close"].shift(1))
    out["volatility"] = (
        log_return.rolling(window=VOLATILITY_LOOKBACK_DAYS, min_periods=2).std()
        * np.sqrt(DAYS_PER_TRADING_YEAR)
    )

    out["daily_return"] = out["daily_return"].replace([np.inf, -np.inf], np.nan)
    return out
