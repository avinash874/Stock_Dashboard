"""
Stock Data Intelligence Dashboard — FastAPI backend
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


# -------------------- Logging --------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STATIC_DIR = BASE_DIR / "static"


# -------------------- Helper Functions --------------------

def resolve_symbol(symbol: str) -> str:
    """Convert symbol to yfinance format."""
    return to_yfinance_symbol(symbol)


def get_all_companies() -> list[dict[str, Any]]:
    """Fetch all companies from database."""
    with get_connection() as conn:
        result = conn.execute(
            "SELECT symbol, display_symbol, name, exchange FROM companies ORDER BY display_symbol"
        )
        return [row_to_dict(row) for row in result.fetchall()]


def get_total_bars() -> int:
    """Count total stock records."""
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM stock_bars").fetchone()
        return int(row["count"]) if row else 0


# -------------------- App Lifespan --------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs at startup and shutdown."""
    init_db()

    app.state.seeding = False
    seed_task: asyncio.Task | None = None

    # Seed data if DB is empty
    if get_total_bars() == 0:
        logger.info("Database empty → Seeding stock data...")

        app.state.seeding = True

        async def seed_job():
            try:
                await asyncio.to_thread(seed_default_universe)
            finally:
                app.state.seeding = False

        seed_task = asyncio.create_task(seed_job())

    yield

    # Cleanup on shutdown
    if seed_task:
        await seed_task

    api_cache.clear()


# -------------------- FastAPI App --------------------

app = FastAPI(
    title="Stock Data Intelligence API",
    description="Stock analytics platform with metrics, comparison, and ML predictions.",
    version="1.0.0",
    lifespan=lifespan,
)


# -------------------- Middleware --------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------- APIs --------------------

@app.get("/health")
def health_check(request: Request):
    return {
        "status": "ok",
        "total_records": get_total_bars(),
        "seeding": getattr(request.app.state, "seeding", False),
        "last_seed": LAST_SEED_RESULT,
    }


@app.get("/companies", tags=["companies"])
def list_companies():
    """Get all available companies."""
    return cached("companies", lambda: {"companies": get_all_companies()})


@app.get("/data/{symbol}", tags=["data"])
def get_stock_data(
    symbol: str,
    days: int = Query(30, ge=1, le=365),
):
    """Get last N days stock data with metrics."""
    yf_symbol = resolve_symbol(symbol)

    start_date = datetime.utcnow() - timedelta(days=days + 60)
    df = load_bars_dataframe(symbol, start=start_date)

    if df.empty:
        raise HTTPException(404, f"No data found for {symbol}")

    df = df.sort_values("bar_date").tail(days)

    records = []
    for _, row in df.iterrows():
        records.append({
            "date": str(row["bar_date"]),
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
        })

    return {
        "symbol": from_yfinance_symbol(yf_symbol),
        "days": len(records),
        "data": records,
    }


@app.get("/summary/{symbol}", tags=["summary"])
def get_summary(symbol: str):
    """Get stock summary."""

    def build():
        df = load_bars_dataframe(symbol)

        if df.empty:
            raise HTTPException(404, f"No data for {symbol}")

        df = df.sort_values("bar_date")
        last = df.iloc[-1]

        return {
            "symbol": symbol,
            "last_close": float(last["close"]),
            "average_close": float(df["close"].mean()),
            "week52_high": float(df["high"].tail(252).max()),
            "week52_low": float(df["low"].tail(252).min()),
            "latest_volatility": float(last["volatility"]) if pd.notna(last["volatility"]) else None,
        }

    return cached(f"summary:{symbol}", build)


@app.get("/compare", tags=["compare"])
def compare_stocks(
    symbol1: str,
    symbol2: str,
    days: int = Query(90, ge=10, le=365),
):
    """Compare two stocks."""

    df1 = load_bars_dataframe(symbol1).tail(days)
    df2 = load_bars_dataframe(symbol2).tail(days)

    if df1.empty or df2.empty:
        raise HTTPException(404, "Data missing")

    merged = df1.merge(df2, on="bar_date", suffixes=("_1", "_2"))

    if merged.empty:
        raise HTTPException(400, "No overlapping dates")

    base1 = merged["close_1"].iloc[0]
    base2 = merged["close_2"].iloc[0]

    result = []
    for _, row in merged.iterrows():
        result.append({
            "date": str(row["bar_date"]),
            "norm1": (row["close_1"] / base1) * 100,
            "norm2": (row["close_2"] / base2) * 100,
        })

    return {
        "symbol1": symbol1,
        "symbol2": symbol2,
        "correlation": correlation_between(symbol1, symbol2),
        "series": result,
    }


@app.get("/top-movers", tags=["insights"])
def top_movers(days: int = 30):
    """Top gainers and losers."""

    with get_connection() as conn:
        symbols = [row["symbol"] for row in conn.execute("SELECT symbol FROM companies")]

    results = []

    for sym in symbols:
        df = load_bars_dataframe(sym).tail(days)

        if len(df) < 2:
            continue

        change = (df["close"].iloc[-1] / df["close"].iloc[0] - 1) * 100
        results.append((sym, change))

    results.sort(key=lambda x: x[1], reverse=True)

    return {
        "top_gainers": results[:5],
        "top_losers": results[-5:],
    }


@app.get("/predict/{symbol}", tags=["ml"])
def predict(symbol: str):
    """Predict future prices."""

    df = load_bars_dataframe(symbol)

    if df.empty:
        raise HTTPException(404, "No data")

    closes = df["close"].values

    fitted, future = predict_next_closes(closes, horizon=40)

    return {
        "symbol": symbol,
        "predicted": future.tolist(),
        "fitted": fitted.tolist(),
        "note": "Demo only",
    }


@app.post("/admin/refresh/{symbol}", tags=["admin"])
def refresh(symbol: str):
    """Refresh stock data."""
    api_cache.clear()

    rows = ingest_symbol(symbol)

    if rows == 0:
        raise HTTPException(400, "Failed to fetch data")

    return {"symbol": symbol, "rows_updated": rows}


# -------------------- Static Files --------------------

if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


@app.get("/")
def home():
    index_file = STATIC_DIR / "index.html"

    if index_file.exists():
        return FileResponse(index_file)

    return {"message": "API is running "}in_df) < 5:
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
