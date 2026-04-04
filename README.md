# Stock Data Intelligence Dashboard (JarNox)

End-to-end demo: **NSE** daily prices via **yfinance**, **Pandas** cleaning + metrics, **SQLite** storage, **FastAPI** REST API, and a **React + Tailwind** dashboard (Chart.js under the hood).

> Learning/demo only. Prices and any “ML” output are **not** investment advice.

## Repo layout

| Path | What lives there |
| --- | --- |
| `backend/` | Python: FastAPI app, data pipeline, SQLite, ML helper |
| `frontend/` | React (Vite) + Tailwind UI; `npm run build` outputs `frontend/dist/` |
| `postman_collection.json` | API collection (repo root) |
| `.gitignore` | Python, SQLite data dirs, Node, OS noise |

SQLite file (after you run the backend): `backend/data_store/stocks.db`.

## Tech stack

| Layer | Choice |
| --- | --- |
| **Backend** | Python 3, FastAPI, SQLite |
| **Data / ML** | Pandas, NumPy, scikit-learn (linear regression demo), yfinance |
| **Frontend** | React 18, Vite 6, Tailwind CSS 3, Chart.js (via `react-chartjs-2`) |

No Docker in this repo — run backend + frontend dev server locally.

## Backend API

With the server running, open **`/docs`** for Swagger.

| Endpoint | Description |
| --- | --- |
| `GET /companies` | Symbols in the local universe |
| `GET /data/{symbol}?days=30` | OHLCV + metrics |
| `GET /summary/{symbol}` | 52w-style high/low, averages, last close, volatility |
| `GET /compare?symbol1=&symbol2=&days=` | Normalized lines + return correlation |
| `GET /top-movers?days=30` | Simple gainers/losers |
| `GET /predict/{symbol}?days=60` | Toy linear extrapolation (demo) |
| `POST /admin/refresh/{symbol}` | Re-fetch one symbol (clears small API cache) |

**Caching:** `/companies` and `/summary/{symbol}` use an in-memory TTL cache (`CACHE_TTL_SECONDS`, default **120**).

## Quick start

### 1) Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

- API + Swagger: http://127.0.0.1:8000/docs  
- If `frontend/dist/` **exists** (after step 2), the dashboard is at http://127.0.0.1:8000/  
- If you have **not** built the frontend yet, `GET /` returns a short JSON hint.

**First boot:** empty DB triggers a **background** download of the default ticker list (often ~1–3 minutes, depends on Yahoo + throttling).

### 2) Frontend (development)

Use a **second terminal** while the backend stays on port **8000**:

```bash
cd frontend
npm install
npm run dev
```

- UI: http://127.0.0.1:5173  
- Vite proxies API paths (`/companies`, `/data`, …) to `http://127.0.0.1:8000`.

### 3) Frontend (production build — same origin as API)

```bash
cd frontend
npm install
npm run build
cd ../backend
source .venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 8000
```

Then open http://127.0.0.1:8000/ — FastAPI serves files from `frontend/dist/`.

Optional: copy `frontend/.env.example` to `frontend/.env` and set `VITE_API_BASE` if the UI is hosted on a **different** origin than the API.

**Vercel (frontend) + Render (API):** If `VITE_API_BASE` is not set at build time, the UI still uses the Render API URL baked into **`frontend/src/services/config.js`** (so requests do not go to `*.vercel.app/companies` and 404). Optional: commit **`frontend/.env.production`** or set **`VITE_API_BASE`** in Vercel → Environment Variables to point at another backend. Vercel: **Root Directory** `frontend`, **Build** `npm run build`, **Output** `dist`. Example UI: [stock-dashboard-tawny-nine.vercel.app](https://stock-dashboard-tawny-nine.vercel.app/).

## Postman

Import `postman_collection.json` from the repo root and point `base` at your API URL (e.g. `http://127.0.0.1:8000`).

## Troubleshooting

- **Port already in use:** stop the old uvicorn or use `--port 8001`.
- **Blank `/` after deploy:** run `npm run build` in `frontend/` so `frontend/dist/` exists.
- **Stale prices:** `POST /admin/refresh/{SYMBOL}` or delete `backend/data_store/` and restart (forces re-seed if empty).
- **Old layout:** if you still have `data_store/` at the **repo root** from an earlier version, the app now uses `backend/data_store/`; you can remove the old folder or move the `.db` file if you want to keep data.

## Presentation angles (write-up)

- **Volatility vs trend:** noisy flat ranges vs smoother trends; pair with the 7-day MA.
- **Correlation (`/compare`):** high correlation → less diversification between two names.
- **Top movers:** short windows are noisy; use as a conversation starter, not a signal.
