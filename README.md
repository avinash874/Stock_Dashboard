# Stock Data Intelligence Dashboard (JarNox internship)

A small **end-to-end** demo: pull **NSE** daily prices with **yfinance**, clean and enrich them with **Pandas**, persist to **SQLite**, expose **FastAPI** REST endpoints (with **Swagger**), and serve a **Chart.js** dashboard for exploration.

> This is a learning/demo project. Prices and any “ML” output are **not** investment advice.

## Tech stack

| Layer | Choice |
| --- | --- |
| **Language** | Python |
| **Backend** | FastAPI (REST + OpenAPI/Swagger) |
| **Database** | SQLite (file `data_store/stocks.db`; PostgreSQL can be used as a drop-in alternative with schema migration if needed) |
| **Data / ML** | Pandas, NumPy, scikit-learn (linear regression demo), **yfinance** for market data (uses HTTP under the hood) |
| **Frontend (bonus)** | HTML + static **Chart.js** (`static/`) |

No Docker — run locally with Python + `venv` (see Quick start below).

## What this project does

### Data collection and preparation

- Downloads ~2 years of daily OHLCV for a fixed universe of liquid **NSE** tickers (`.NS` suffix for yfinance).
- Cleans data: numeric coercion, missing-value handling, sorted calendar dates.
- Computes metrics:
  - **Daily return**: \((\text{close} - \text{open}) / \text{open}\)
  - **7-day moving average** of close
  - **52-week high / low** using a 252-trading-day rolling window on highs/lows
  - **Custom metric — annualized volatility**: rolling std of log returns (7 sessions) × \(\sqrt{252}\)
- Stores one row per `(symbol, date)` in SQLite (`data_store/stocks.db`).

### Backend API (FastAPI)

Interactive docs: run the server and open `/docs`.

| Endpoint | Description |
| --- | --- |
| `GET /companies` | All symbols in the local universe |
| `GET /data/{symbol}?days=30` | Recent bars with OHLCV + metrics |
| `GET /summary/{symbol}` | 52-week high/low (from latest rolling metrics), average close, last close, latest volatility |
| `GET /compare?symbol1=INFY&symbol2=TCS&days=90` | Normalized performance + **return correlation** (custom insight) |
| `GET /top-movers?days=30` | Simple gainers/losers over the window |
| `GET /predict/{symbol}?days=60` | **Bonus**: sklearn `LinearRegression` on pre-April bars + Apr + May (business-day) forecast (demo only) |
| `POST /admin/refresh/{symbol}` | Re-download one symbol (clears the tiny API cache) |

**Caching:** responses for `/companies` and `/summary/{symbol}` are cached in-memory for `CACHE_TTL_SECONDS` (default **120s**) to reduce repeated heavy reads.

### Dashboard (static)

`static/index.html` (served at `/`) includes:

- Left-hand company list with search
- Close price chart (+ optional **7d MA**)
- Range filter (**30 / 90** days) and **Top movers**
- Optional **ML trend** overlay (linear fit + short extrapolation)
- **Compare** mode (normalized lines + correlation shown in subtitle)

## Quick start (local)

```bash
cd project_JarNox
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

- API + Swagger: `http://127.0.0.1:8000/docs`
- Dashboard: `http://127.0.0.1:8000/`

**First boot note:** if `data_store/stocks.db` is missing/empty, the app **downloads and ingests** all default tickers on startup (typically ~1–3 minutes depending on network).

## Postman

Import `postman_collection.json` and set `base` to your server URL.

## Repository layout

- `main.py` — FastAPI app, routing, caching, static dashboard
- `data_service.py` — yfinance ingestion + SQLite upserts
- `data_processor.py` — cleaning + derived metrics
- `database.py` — SQLite schema
- `ml_predict.py` — simple regression helper
- `static/` — dashboard assets
- `yf_client.py` — throttled yfinance fetches with retries

## Ideas for “insights” you can mention in your write-up

When presenting the assignment, good narrative angles are:

- **Volatility vs trend**: high volatility with flat prices often implies noisy, event-driven trading; combine with moving averages to describe regime shifts.
- **Correlation** (from `/compare`): quantify diversification — high correlation means less independent risk reduction when pairing names.
- **Top movers**: highlight sector rotation or idiosyncratic moves, but treat short windows cautiously (noise dominates).

## Troubleshooting

- **`pip` downloads time out:** retry with `export PIP_DEFAULT_TIMEOUT=300` or `pip install --no-cache-dir -r requirements.txt`.
- **Stale data:** call `POST /admin/refresh/{SYMBOL}` or delete `data_store/` to force a rebuild on next boot.
- **yfinance outages:** symptoms include empty frames during ingest; the API will return 404s for affected symbols until refresh succeeds.
