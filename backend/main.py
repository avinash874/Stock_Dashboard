from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
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

# Production UI: `npm run build` in ../frontend — FastAPI serves that folder when present
FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"


def _as_float(x: Any) -> float | None:
    if pd.isna(x):
        return None
    return float(x)


def _bar_date_str(value: Any) -> str:
    if hasattr(value, "date"):
        return str(value.date())
    return str(value)


def _company_list_from_db() -> list[dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.execute(
            "SELECT symbol, display_symbol, name, exchange FROM companies ORDER BY display_symbol"
        )
        return [row_to_dict(r) for r in cur.fetchall()]


def _how_many_bars_in_db() -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM stock_bars").fetchone()
        return int(row["c"]) if row else 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    app.state.seeding = False
    seed_task: asyncio.Task | None = None

    if _how_many_bars_in_db() == 0:
        logger.info("DB is empty — filling default tickers in the background (can take a few minutes).")
        app.state.seeding = True

        async def background_seed() -> None:
            try:
                await asyncio.to_thread(seed_default_universe)
            finally:
                app.state.seeding = False

        seed_task = asyncio.create_task(background_seed())

    yield

    if seed_task is not None:
        await seed_task
    api_cache.clear()


app = FastAPI(
    title="Stock Data Intelligence API",
    description="NSE demo: SQLite + FastAPI + a tiny ML toy endpoint.",
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
        "bars": _how_many_bars_in_db(),
        "seeding": getattr(request.app.state, "seeding", False),
        "seed": LAST_SEED_RESULT,
    }


@app.get("/companies", tags=["companies"], summary="All tickers we have in the database")
def list_companies():

    def load():
        return {"companies": _company_list_from_db()}

    return cached("companies", load)


@app.get("/data/{symbol}", tags=["data"], summary="Daily OHLCV + metrics for last N days")
def get_stock_data(
    symbol: str,
    days: int = Query(30, ge=1, le=365, description="How far back (calendar days, then we trim to `days` rows)"),
):
    yahoo = to_yfinance_symbol(symbol)
    # Grab extra history so we don't run out of rows after weekends/holidays
    start = datetime.utcnow() - timedelta(days=days + 60)
    df = load_bars_dataframe(symbol, start=start)
    if df.empty:
        raise HTTPException(404, f"No data for {symbol}. Try GET /companies.")

    df = df.sort_values("bar_date").tail(days)
    out = []
    for _, row in df.iterrows():
        out.append(
            {
                "date": _bar_date_str(row["bar_date"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"] or 0),
                "daily_return": _as_float(row["daily_return"]),
                "ma7": _as_float(row["ma7"]),
                "week52_high": _as_float(row["week52_high"]),
                "week52_low": _as_float(row["week52_low"]),
                "volatility": _as_float(row["volatility"]),
            }
        )

    return {
        "symbol": from_yfinance_symbol(yahoo),
        "days": len(out),
        "data": out,
    }


@app.get("/summary/{symbol}", tags=["summary"], summary="52w high/low-ish numbers + averages from stored history")
def get_summary(symbol: str):

    def build():
        yahoo = to_yfinance_symbol(symbol)
        df = load_bars_dataframe(symbol)
        if df.empty:
            raise HTTPException(404, f"No data for {symbol}")

        df = df.sort_values("bar_date")
        last_row = df.iloc[-1]

        if pd.notna(last_row["week52_high"]):
            high_52w = float(last_row["week52_high"])
        else:
            high_52w = float(df["high"].tail(252).max())

        if pd.notna(last_row["week52_low"]):
            low_52w = float(last_row["week52_low"])
        else:
            low_52w = float(df["low"].tail(252).min())

        return {
            "symbol": from_yfinance_symbol(yahoo),
            "as_of": str(last_row["bar_date"]),
            "week52_high": high_52w,
            "week52_low": low_52w,
            "average_close": float(df["close"].mean()),
            "last_close": float(last_row["close"]),
            "latest_volatility": _as_float(last_row["volatility"]),
        }

    return cached(f"summary:{symbol.upper()}", build)


@app.get("/compare", tags=["compare"], summary="Two stocks overlaid + correlation of daily moves")
def compare_stocks(
    symbol1: str = Query(..., description="e.g. INFY"),
    symbol2: str = Query(..., description="e.g. TCS"),
    days: int = Query(90, ge=10, le=365),
):
    a = symbol1.strip().upper()
    b = symbol2.strip().upper()

    df_a = load_bars_dataframe(a)
    df_b = load_bars_dataframe(b)
    if df_a.empty or df_b.empty:
        raise HTTPException(404, "One or both symbols have no data.")

    df_a = df_a.sort_values("bar_date").tail(days)
    df_b = df_b.sort_values("bar_date").tail(days)

    merged = df_a[["bar_date", "close"]].merge(
        df_b[["bar_date", "close"]], on="bar_date", suffixes=("_1", "_2")
    )
    if merged.empty:
        raise HTTPException(400, "No overlapping dates.")
    merged = merged.sort_values("bar_date")

    first_close_a = float(merged["close_1"].iloc[0])
    first_close_b = float(merged["close_2"].iloc[0])
    if first_close_a == 0 or first_close_b == 0:
        raise HTTPException(400, "Bad prices (zero) — can't normalize.")

    # Start both lines at 100 so you can compare shape, not rupee levels
    chart = []
    for _, r in merged.iterrows():
        chart.append(
            {
                "date": _bar_date_str(r["bar_date"]),
                "norm1": (float(r["close_1"]) / first_close_a) * 100.0,
                "norm2": (float(r["close_2"]) / first_close_b) * 100.0,
            }
        )

    corr = correlation_between(a, b, days=min(days, 120))
    ret_a = (merged["close_1"].iloc[-1] / merged["close_1"].iloc[0] - 1.0) * 100.0
    ret_b = (merged["close_2"].iloc[-1] / merged["close_2"].iloc[0] - 1.0) * 100.0

    return {
        "symbol1": from_yfinance_symbol(to_yfinance_symbol(a)),
        "symbol2": from_yfinance_symbol(to_yfinance_symbol(b)),
        "period_days": len(merged),
        "total_return_pct_symbol1": round(float(ret_a), 4),
        "total_return_pct_symbol2": round(float(ret_b), 4),
        "return_correlation": round(corr, 4) if corr is not None else None,
        "series": chart,
    }


@app.get("/top-movers", tags=["insights"], summary="Who gained / lost most over the window")
def top_movers(days: int = Query(30, ge=1, le=90)):
    with get_connection() as conn:
        symbols = [r["symbol"] for r in conn.execute("SELECT symbol FROM companies").fetchall()]

    moves: list[tuple[str, float]] = []
    for yahoo_sym in symbols:
        label = from_yfinance_symbol(yahoo_sym)
        df = load_bars_dataframe(label)
        if df.empty or len(df) < 2:
            continue
        df = df.sort_values("bar_date").tail(days + 1)
        if len(df) < 2:
            continue
        old_close = float(df["close"].iloc[0])
        new_close = float(df["close"].iloc[-1])
        if old_close == 0:
            continue
        pct_change = (new_close / old_close - 1.0) * 100.0
        moves.append((label, pct_change))

    moves.sort(key=lambda x: x[1], reverse=True)
    return {
        "days": days,
        "top_gainers": [{"symbol": s, "return_pct": round(p, 4)} for s, p in moves[:5]],
        "top_losers": [{"symbol": s, "return_pct": round(p, 4)} for s, p in moves[-5:][::-1]],
    }


@app.get("/predict/{symbol}", tags=["ml"], summary="Toy linear extrapolation — not advice")
def predict_price(symbol: str, days: int = Query(60, ge=20, le=365)):
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
    n_april, n_may = len(april_bdays), len(may_bdays)
    horizon = n_april + n_may

    train = df[df["bar_date"] < april_start].tail(days)
    if len(train) < 5:
        raise HTTPException(
            400,
            f"Need 5+ trading days before April {year}; got {len(train)}. Refresh data or pick another symbol.",
        )

    closes = train["close"].astype(float).values
    fitted, future = predict_next_closes(closes, horizon=horizon)

    training_dates = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in train["bar_date"]]
    april_dates = [d.strftime("%Y-%m-%d") for d in april_bdays]
    may_dates = [d.strftime("%Y-%m-%d") for d in may_bdays]

    return {
        "symbol": from_yfinance_symbol(to_yfinance_symbol(symbol)),
        "method": "sklearn LinearRegression on time index vs close",
        "train_before": f"{year}-04-01",
        "predict_year": year,
        "fitted_close": fitted,
        "training_dates": training_dates,
        "april_dates": april_dates,
        "may_dates": may_dates,
        "predicted_april_closes": future[:n_april],
        "predicted_may_closes": future[n_april:],
        "disclaimer": "Educational demo only — not investment advice.",
    }


@app.post("/admin/refresh/{symbol}", tags=["admin"], summary="Re-download one symbol from Yahoo")
def refresh_symbol(symbol: str):
    api_cache.clear()
    n = ingest_symbol(symbol)
    if n == 0:
        raise HTTPException(400, f"Could not fetch {symbol}")
    return {"symbol": symbol, "rows_upserted": n}


if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="spa")
else:

    @app.get("/")
    async def root():
        return {
            "message": "API is running. Build the React app to get the dashboard at /",
            "hint": "cd frontend && npm install && npm run build",
            "docs": "/docs",
        }
