"""
Stock Data Intelligence Dashboard — FastAPI backend.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from cache_utils import api_cache, cached
from config import BASE_DIR
from data_service import (
    LAST_SEED_RESULT,
    correlation_between,
    from_yfinance_symbol,
    ingest_symbol,
    load_bars_dataframe,
    seed_default_universe,
    to_yfinance_symbol,
)
from database import get_connection, init_db, row_to_dict
from ml_predict import predict_next_closes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STATIC_DIR = BASE_DIR / "static"


def _resolve_yf_symbol(symbol: str) -> str:
    return to_yfinance_symbol(symbol)


def _company_rows() -> list[dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.execute(
            "SELECT symbol, display_symbol, name, exchange FROM companies ORDER BY display_symbol"
        )
        return [row_to_dict(r) for r in cur.fetchall()]


def _count_bars() -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM stock_bars").fetchone()
        return int(row["c"]) if row else 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    app.state.seeding = False
    seed_task: asyncio.Task | None = None
    if _count_bars() == 0:
        logger.info(
            "Database empty — seeding NSE universe in background (throttled; may take several minutes)..."
        )
        app.state.seeding = True

        async def seed_job() -> None:
            try:
                await asyncio.to_thread(seed_default_universe)
            finally:
                app.state.seeding = False

        seed_task = asyncio.create_task(seed_job())
    yield
    if seed_task is not None:
        await seed_task
    api_cache.clear()


app = FastAPI(
    title="Stock Data Intelligence API",
    description="Mini financial data platform: cleaned NSE data, metrics, comparison, and ML demo.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health(request: Request):
    return {
        "status": "ok",
        "bars": _count_bars(),
        "seeding": getattr(request.app.state, "seeding", False),
        "seed": LAST_SEED_RESULT,
    }


@app.get("/companies", tags=["companies"])
def list_companies():
    """List all available companies (from ingested universe)."""

    def load():
        return {"companies": _company_rows()}

    return cached("companies", load)


@app.get("/data/{symbol}", tags=["data"])
def get_stock_data(
    symbol: str,
    days: int = Query(30, ge=1, le=365, description="Number of recent trading days"),
):
    """Last N calendar days of OHLCV and computed metrics (daily return, MA7, 52w range, volatility)."""
    yf_sym = _resolve_yf_symbol(symbol)
    start = datetime.utcnow() - timedelta(days=days + 60)
    df = load_bars_dataframe(symbol, start=start)
    if df.empty:
        raise HTTPException(404, f"No data for symbol {symbol}. Try /companies for valid tickers.")

    df = df.sort_values("bar_date").tail(days)
    records = []
    for _, row in df.iterrows():
        records.append(
            {
                "date": str(row["bar_date"].date()) if hasattr(row["bar_date"], "date") else str(row["bar_date"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"] or 0),
                "daily_return": float(row["daily_return"]) if pd.notna(row["daily_return"]) else None,
                "ma7": float(row["ma7"]) if pd.notna(row["ma7"]) else None,
                "week52_high": float(row["week52_high"]) if pd.notna(row["week52_high"]) else None,
                "week52_low": float(row["week52_low"]) if pd.notna(row["week52_low"]) else None,
                "volatility": float(row["volatility"]) if pd.notna(row["volatility"]) else None,
            }
        )
    return {
        "symbol": from_yfinance_symbol(yf_sym),
        "days": len(records),
        "data": records,
    }


@app.get("/summary/{symbol}", tags=["summary"])
def get_summary(symbol: str):
    """52-week high, low, and average close over all stored history."""

    def build():
        yf_sym = _resolve_yf_symbol(symbol)
        df = load_bars_dataframe(symbol)
        if df.empty:
            raise HTTPException(404, f"No data for {symbol}")
        last = df.sort_values("bar_date").iloc[-1]
        # Prefer rolling 52-week metrics on last bar; fallback to range in history
        hi = (
            float(last["week52_high"])
            if pd.notna(last["week52_high"])
            else float(df["high"].tail(252).max())
        )
        lo = (
            float(last["week52_low"])
            if pd.notna(last["week52_low"])
            else float(df["low"].tail(252).min())
        )
        avg_close = float(df["close"].mean())
        return {
            "symbol": from_yfinance_symbol(yf_sym),
            "as_of": str(last["bar_date"]),
            "week52_high": hi,
            "week52_low": lo,
            "average_close": avg_close,
            "last_close": float(last["close"]),
            "latest_volatility": float(last["volatility"]) if pd.notna(last["volatility"]) else None,
        }

    return cached(f"summary:{symbol.upper()}", build)


@app.get("/compare", tags=["compare"])
def compare_stocks(
    symbol1: str = Query(..., description="First ticker, e.g. INFY"),
    symbol2: str = Query(..., description="Second ticker, e.g. TCS"),
    days: int = Query(90, ge=10, le=365),
):
    """Compare normalized performance and return correlation of returns (custom metric)."""
    s1, s2 = symbol1.strip().upper(), symbol2.strip().upper()
    df1 = load_bars_dataframe(s1)
    df2 = load_bars_dataframe(s2)
    if df1.empty or df2.empty:
        raise HTTPException(404, "One or both symbols have no data.")

    df1 = df1.sort_values("bar_date").tail(days)
    df2 = df2.sort_values("bar_date").tail(days)
    merged = df1[["bar_date", "close"]].merge(
        df2[["bar_date", "close"]], on="bar_date", suffixes=("_1", "_2")
    )
    if merged.empty:
        raise HTTPException(400, "No overlapping dates for comparison.")
    merged = merged.sort_values("bar_date")

    base1 = float(merged["close_1"].iloc[0])
    base2 = float(merged["close_2"].iloc[0])
    if base1 == 0 or base2 == 0:
        raise HTTPException(400, "Invalid base prices.")

    series = []
    for _, r in merged.iterrows():
        series.append(
            {
                "date": str(r["bar_date"].date()) if hasattr(r["bar_date"], "date") else str(r["bar_date"]),
                "norm1": (float(r["close_1"]) / base1) * 100.0,
                "norm2": (float(r["close_2"]) / base2) * 100.0,
            }
        )

    corr = correlation_between(s1, s2, days=min(days, 120))
    ret1 = (merged["close_1"].iloc[-1] / merged["close_1"].iloc[0] - 1.0) * 100.0
    ret2 = (merged["close_2"].iloc[-1] / merged["close_2"].iloc[0] - 1.0) * 100.0

    return {
        "symbol1": from_yfinance_symbol(to_yfinance_symbol(s1)),
        "symbol2": from_yfinance_symbol(to_yfinance_symbol(s2)),
        "period_days": len(merged),
        "total_return_pct_symbol1": round(float(ret1), 4),
        "total_return_pct_symbol2": round(float(ret2), 4),
        "return_correlation": round(corr, 4) if corr is not None else None,
        "series": series,
    }


@app.get("/top-movers", tags=["insights"])
def top_movers(days: int = Query(30, ge=1, le=90)):
    """Top gainers and losers by close-to-close return over the window."""
    with get_connection() as conn:
        symbols = [r["symbol"] for r in conn.execute("SELECT symbol FROM companies").fetchall()]
    movers: list[tuple[str, float]] = []
    for sym in symbols:
        df = load_bars_dataframe(from_yfinance_symbol(sym))
        if df.empty or len(df) < 2:
            continue
        df = df.sort_values("bar_date").tail(days + 1)
        if len(df) < 2:
            continue
        first, last = float(df["close"].iloc[0]), float(df["close"].iloc[-1])
        if first == 0:
            continue
        pct = (last / first - 1.0) * 100.0
        movers.append((from_yfinance_symbol(sym), pct))
    movers.sort(key=lambda x: x[1], reverse=True)
    return {
        "days": days,
        "top_gainers": [{"symbol": s, "return_pct": round(p, 4)} for s, p in movers[:5]],
        "top_losers": [{"symbol": s, "return_pct": round(p, 4)} for s, p in movers[-5:][::-1]],
    }


@app.get("/predict/{symbol}", tags=["ml"])
def predict_price(symbol: str, days: int = Query(60, ge=20, le=365)):
    """Linear regression on pre-April history; extrapolate April + May business days (demo, not financial advice)."""
    df = load_bars_dataframe(symbol)
    if df.empty:
        raise HTTPException(404, f"No data for {symbol}")
    df = df.sort_values("bar_date")
    df["bar_date"] = pd.to_datetime(df["bar_date"]).dt.normalize()

    year = date.today().year
    april_start = pd.Timestamp(year=year, month=4, day=1)
    april_end = pd.Timestamp(year=year, month=4, day=30)
    may_start = pd.Timestamp(year=year, month=5, day=1)
    may_end = pd.Timestamp(year=year, month=5, day=31)
    april_bdays = pd.bdate_range(april_start, april_end)
    may_bdays = pd.bdate_range(may_start, may_end)
    n_apr, n_may = len(april_bdays), len(may_bdays)
    horizon = n_apr + n_may

    train_df = df[df["bar_date"] < april_start].tail(days)
    if len(train_df) < 5:
        raise HTTPException(
            400,
            f"Need at least 5 daily bars before April {year}; got {len(train_df)}. Try more history or refresh data.",
        )

    closes = train_df["close"].astype(float).values
    fitted, future = predict_next_closes(closes, horizon=horizon)
    training_dates = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in train_df["bar_date"]]
    april_dates = [d.strftime("%Y-%m-%d") for d in april_bdays]
    may_dates = [d.strftime("%Y-%m-%d") for d in may_bdays]
    pred_apr = future[:n_apr]
    pred_may = future[n_apr:]

    return {
        "symbol": from_yfinance_symbol(_resolve_yf_symbol(symbol)),
        "method": "sklearn LinearRegression on time index vs close",
        "train_before": f"{year}-04-01",
        "predict_year": year,
        "fitted_close": fitted,
        "training_dates": training_dates,
        "april_dates": april_dates,
        "may_dates": may_dates,
        "predicted_april_closes": pred_apr,
        "predicted_may_closes": pred_may,
        "disclaimer": "Educational demo only — not investment advice.",
    }


@app.post("/admin/refresh/{symbol}", tags=["admin"])
def refresh_symbol(symbol: str):
    """Re-ingest one symbol from yfinance (clears cache)."""
    api_cache.clear()
    n = ingest_symbol(symbol)
    if n == 0:
        raise HTTPException(400, f"Failed to fetch data for {symbol}")
    return {"symbol": symbol, "rows_upserted": n}


if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


@app.get("/")
async def root():
    index = STATIC_DIR / "index.html"
    if index.is_file():
        return FileResponse(index)
    return {"message": "API running — add static/index.html for dashboard."}
