import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Legend,
  Tooltip,
  Filler,
} from "chart.js";
import { Line } from "react-chartjs-2";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Legend,
  Tooltip,
  Filler
);

// No trailing slash — we join paths like `/companies`
// Vite exposes only VITE_* keys on import.meta.env (see .env.production for production builds)
const apiBase = String(import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

// Swagger lives on the API host when the UI is on Vercel and the API is on Render
const docsUrl = apiBase ? `${apiBase}/docs` : "/docs";

// Public URL of this UI (footer link). Not the API URL.
const LIVE_APP_URL =
  import.meta.env.VITE_APP_LIVE_URL ?? "https://stock-dashboard-1-0qoi.onrender.com/";

async function fetchJSON(path) {
  const url = `${apiBase}${path}`;
  const r = await fetch(url);
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json();
}

const chartOpts = {
  responsive: true,
  plugins: {
    legend: { labels: { color: "#8b9bb4" } },
  },
  scales: {
    x: {
      ticks: { color: "#8b9bb4", maxTicksLimit: 10 },
      grid: { color: "#2d3a4d" },
    },
    y: {
      ticks: { color: "#8b9bb4" },
      grid: { color: "#2d3a4d" },
    },
  },
};

function buildPriceDatasets(series, showMA, pred) {
  const labels = series.data.map((d) => d.date);
  const closes = series.data.map((d) => d.close);
  const ma7 = series.data.map((d) => d.ma7);

  const datasets = [
    {
      label: "Close",
      data: closes,
      borderColor: "#3d9eff",
      backgroundColor: "rgba(61, 158, 255, 0.1)",
      tension: 0.15,
      fill: true,
      pointRadius: 0,
    },
  ];

  if (showMA) {
    datasets.push({
      label: "7d MA",
      data: ma7,
      borderColor: "#5ce1c5",
      borderDash: [4, 4],
      tension: 0.15,
      pointRadius: 0,
    });
  }

  if (
    pred &&
    pred.training_dates &&
    pred.fitted_close &&
    pred.training_dates.length === pred.fitted_close.length
  ) {
    const fitMap = new Map(pred.training_dates.map((d, i) => [d, pred.fitted_close[i]]));
    const fittedAligned = labels.map((d) => fitMap.get(d) ?? null);
    if (fittedAligned.some((x) => x != null)) {
      datasets.push({
        label: "ML linear fit",
        data: fittedAligned,
        borderColor: "#c9a227",
        borderDash: [4, 3],
        tension: 0.1,
        pointRadius: 0,
        spanGaps: true,
      });
    }
  }

  const nApr =
    pred && pred.april_dates && pred.predicted_april_closes
      ? Math.min(pred.april_dates.length, pred.predicted_april_closes.length)
      : 0;
  const nMay =
    pred && pred.may_dates && pred.predicted_may_closes
      ? Math.min(pred.may_dates.length, pred.predicted_may_closes.length)
      : 0;
  const nFc = nApr + nMay;
  const padFc = (arr) => [...arr, ...Array(nFc).fill(null)];

  if (pred && nApr > 0 && pred.predicted_april_closes && pred.april_dates) {
    const aprDates = pred.april_dates.slice(0, nApr);
    const mayDates = pred.may_dates ? pred.may_dates.slice(0, nMay) : [];
    const extLabels = [...labels, ...aprDates, ...mayDates];
    const L = closes.length;
    const lastClose = closes[L - 1];
    const pa = pred.predicted_april_closes.slice(0, nApr);
    const pm = pred.predicted_may_closes ? pred.predicted_may_closes.slice(0, nMay) : [];
    const lastApr = pa.length ? pa[pa.length - 1] : lastClose;

    const bridgeApr = [...Array(L - 1).fill(null), lastClose, ...pa, ...Array(nMay).fill(null)];
    const bridgeMay =
      nMay > 0 ? [...Array(L + nApr - 1).fill(null), lastApr, ...pm] : null;

    datasets[0].data = padFc(datasets[0].data);
    if (datasets[1] && datasets[1].label === "7d MA") datasets[1].data = padFc(datasets[1].data);
    const fitIdx = datasets.findIndex((d) => d.label === "ML linear fit");
    if (fitIdx >= 0) datasets[fitIdx].data = padFc(datasets[fitIdx].data);

    datasets.push({
      label: "ML April (forecast)",
      data: bridgeApr,
      borderColor: "#f0c14d",
      borderDash: [2, 4],
      pointRadius: 2,
    });
    if (bridgeMay) {
      datasets.push({
        label: "ML May (forecast)",
        data: bridgeMay,
        borderColor: "#e07a5f",
        borderDash: [4, 2],
        pointRadius: 2,
      });
    }

    return { labels: extLabels, datasets, chartKey: extLabels.join(",") };
  }

  return { labels, datasets, chartKey: labels.join(",") };
}

export default function App() {
  const [companies, setCompanies] = useState([]);
  const [search, setSearch] = useState("");
  const [rangeDays, setRangeDays] = useState("30");
  const [showMA, setShowMA] = useState(true);
  const [showPred, setShowPred] = useState(false);
  const [selectedSymbol, setSelectedSymbol] = useState(null);
  const [error, setError] = useState("");
  const [gainers, setGainers] = useState([]);
  const [losers, setLosers] = useState([]);
  const [summary, setSummary] = useState(null);
  const [priceChart, setPriceChart] = useState(null);
  const [compareChart, setCompareChart] = useState(null);
  const [view, setView] = useState("detail");
  const [compareMeta, setCompareMeta] = useState({ title: "", subtitle: "" });

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return companies.filter((c) => {
      const hay = `${c.display_symbol} ${c.name || ""}`.toLowerCase();
      return !q || hay.includes(q);
    });
  }, [companies, search]);

  const loadTopMovers = useCallback(async (days) => {
    try {
      const m = await fetchJSON(`/top-movers?days=${days}`);
      setGainers(m.top_gainers || []);
      setLosers(m.top_losers || []);
    } catch (e) {
      console.warn(e);
    }
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const data = await fetchJSON("/companies");
        setCompanies(data.companies || []);
        const m = await fetchJSON("/top-movers?days=30");
        setGainers(m.top_gainers || []);
        setLosers(m.top_losers || []);
      } catch (e) {
        setError(e.message);
      }
    })();
  }, []);

  const loadDetail = useCallback(async (symbol) => {
    setError("");
    const days = parseInt(rangeDays, 10);
    const predPromise = showPred
      ? fetchJSON(`/predict/${encodeURIComponent(symbol)}?days=${days}`).catch(() => null)
      : Promise.resolve(null);

    const [series, sum, pred] = await Promise.all([
      fetchJSON(`/data/${encodeURIComponent(symbol)}?days=${days}`),
      fetchJSON(`/summary/${encodeURIComponent(symbol)}`),
      predPromise,
    ]);

    setSummary(sum);
    setPriceChart(buildPriceDatasets(series, showMA, pred));
  }, [rangeDays, showMA, showPred]);

  useEffect(() => {
    if (!selectedSymbol) return;
    let cancelled = false;
    loadDetail(selectedSymbol).catch((e) => {
      if (!cancelled) setError(e.message);
    });
    return () => {
      cancelled = true;
    };
  }, [selectedSymbol, rangeDays, showMA, showPred, loadDetail]);

  const pickCompany = (symbol) => {
    setView("detail");
    setSelectedSymbol(symbol);
  };

  const onRangeChange = async (v) => {
    setRangeDays(v);
    await loadTopMovers(v);
  };

  const runCompare = async (s1, s2) => {
    if (!s1 || !s2) return;
    setError("");
    setView("compare");
    const days = Math.max(parseInt(rangeDays, 10), 30);
    const data = await fetchJSON(
      `/compare?symbol1=${encodeURIComponent(s1)}&symbol2=${encodeURIComponent(s2)}&days=${days}`
    );
    setCompareMeta({
      title: `${data.symbol1} vs ${data.symbol2}`,
      subtitle: `Return: ${data.symbol1} ${data.total_return_pct_symbol1}% · ${data.symbol2} ${data.total_return_pct_symbol2}% · corr ${data.return_correlation ?? "—"}`,
    });
    const labels = data.series.map((p) => p.date);
    setCompareChart({
      labels,
      datasets: [
        {
          label: data.symbol1,
          data: data.series.map((p) => p.norm1),
          borderColor: "#3d9eff",
          tension: 0.15,
          pointRadius: 0,
        },
        {
          label: data.symbol2,
          data: data.series.map((p) => p.norm2),
          borderColor: "#5ce1c5",
          tension: 0.15,
          pointRadius: 0,
        },
      ],
    });
  };

  const [cmpA, setCmpA] = useState("");
  const [cmpB, setCmpB] = useState("");

  useEffect(() => {
    if (!companies.length) return;
    setCmpA(companies[0]?.display_symbol ?? "");
    setCmpB(companies[1]?.display_symbol ?? companies[0]?.display_symbol ?? "");
  }, [companies]);

  const compareOptions = useMemo(
    () => ({
      ...chartOpts,
      scales: {
        ...chartOpts.scales,
        y: {
          ...chartOpts.scales.y,
          title: { display: true, text: "Indexed to 100 at start", color: "#8b9bb4" },
        },
      },
    }),
    []
  );

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-line bg-card/80 px-4 py-4 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Stock Data Intelligence</h1>
          <p className="text-sm text-muted mt-1">
            NSE via yfinance · metrics · compare · demo ML trend
          </p>
        </div>
        <div className="flex flex-wrap gap-4 text-sm items-center">
          <label className="flex items-center gap-2 text-muted">
            Range
            <select
              className="bg-page border border-line rounded px-2 py-1 text-slate-200"
              value={rangeDays}
              onChange={(e) => onRangeChange(e.target.value)}
            >
              <option value="30">30 days</option>
              <option value="90">90 days</option>
            </select>
          </label>
          <label className="flex items-center gap-2 text-muted cursor-pointer">
            <input type="checkbox" checked={showMA} onChange={(e) => setShowMA(e.target.checked)} />
            Show 7d MA
          </label>
          <label className="flex items-center gap-2 text-muted cursor-pointer">
            <input
              type="checkbox"
              checked={showPred}
              onChange={(e) => setShowPred(e.target.checked)}
            />
            ML trend (linear)
          </label>
        </div>
      </header>

      <div className="flex-1 flex flex-col md:flex-row min-h-0">
        <aside className="w-full md:w-72 shrink-0 border-b md:border-b-0 md:border-r border-line p-4 space-y-6 overflow-y-auto max-h-[40vh] md:max-h-none">
          <div>
            <h2 className="text-sm font-semibold text-muted uppercase tracking-wide">Companies</h2>
            <input
              type="search"
              placeholder="Filter…"
              className="mt-2 w-full bg-page border border-line rounded px-2 py-1.5 text-sm"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <ul className="mt-2 space-y-1 max-h-48 overflow-y-auto">
              {filtered.map((c) => (
                <li key={c.display_symbol}>
                  <button
                    type="button"
                    onClick={() => pickCompany(c.display_symbol)}
                    className={`w-full text-left rounded px-2 py-1.5 text-sm hover:bg-card border border-transparent ${
                      c.display_symbol === selectedSymbol ? "bg-card border-line" : ""
                    }`}
                  >
                    <span className="font-medium text-accent">{c.display_symbol}</span>
                    <span className="block text-xs text-muted truncate">{c.name || ""}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-muted">Compare</h3>
            <div className="mt-2 flex flex-col gap-2">
              <select
                className="bg-page border border-line rounded px-2 py-1 text-sm"
                value={cmpA}
                onChange={(e) => setCmpA(e.target.value)}
              >
                {companies.map((c) => (
                  <option key={`a-${c.display_symbol}`} value={c.display_symbol}>
                    {c.display_symbol} — {c.name || ""}
                  </option>
                ))}
              </select>
              <select
                className="bg-page border border-line rounded px-2 py-1 text-sm"
                value={cmpB}
                onChange={(e) => setCmpB(e.target.value)}
              >
                {companies.map((c) => (
                  <option key={`b-${c.display_symbol}`} value={c.display_symbol}>
                    {c.display_symbol} — {c.name || ""}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="bg-accent/20 text-accent border border-accent/40 rounded py-1.5 text-sm font-medium hover:bg-accent/30"
                onClick={() => runCompare(cmpA, cmpB).catch((e) => setError(e.message))}
              >
                Compare
              </button>
            </div>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-muted">
              Top movers <span className="font-normal">({rangeDays}d)</span>
            </h3>
            <div className="mt-2 grid grid-cols-2 gap-3 text-xs">
              <div>
                <h4 className="text-mint mb-1">Gainers</h4>
                <ul className="space-y-1">
                  {gainers.map((x) => (
                    <li key={x.symbol} className="flex justify-between gap-2">
                      <span>{x.symbol}</span>
                      <span className="text-mint">+{x.return_pct}%</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h4 className="text-danger mb-1">Losers</h4>
                <ul className="space-y-1">
                  {losers.map((x) => (
                    <li key={x.symbol} className="flex justify-between gap-2">
                      <span>{x.symbol}</span>
                      <span className="text-danger">{x.return_pct}%</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </aside>

        <main className="flex-1 p-4 space-y-4 overflow-y-auto">
          {error ? (
            <p className="text-danger text-sm border border-danger/40 rounded p-3 bg-danger/10">{error}</p>
          ) : null}

          {view === "detail" && selectedSymbol && priceChart ? (
            <>
              <section className="rounded-lg border border-line bg-card p-4">
                <h2 className="text-lg font-semibold">{selectedSymbol}</h2>
                <p className="text-sm text-muted mt-1">
                  {priceChart.labels.length} points · chart updates when you change range / toggles
                </p>
                <div className="mt-4 h-72">
                  <Line key={priceChart.chartKey} data={priceChart} options={chartOpts} />
                </div>
              </section>

              {summary ? (
                <section className="rounded-lg border border-line bg-card p-4">
                  <h3 className="font-semibold mb-3">Summary</h3>
                  <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2 text-sm">
                    <dt className="text-muted">52-week high</dt>
                    <dd>{summary.week52_high?.toFixed(2) ?? "—"}</dd>
                    <dt className="text-muted">52-week low</dt>
                    <dd>{summary.week52_low?.toFixed(2) ?? "—"}</dd>
                    <dt className="text-muted">Average close (all history)</dt>
                    <dd>{summary.average_close?.toFixed(2) ?? "—"}</dd>
                    <dt className="text-muted">Last close</dt>
                    <dd>{summary.last_close?.toFixed(2) ?? "—"}</dd>
                    <dt className="text-muted">Latest vol (ann.)</dt>
                    <dd>
                      {summary.latest_volatility != null
                        ? summary.latest_volatility.toFixed(4)
                        : "—"}
                    </dd>
                  </dl>
                </section>
              ) : null}
            </>
          ) : null}

          {view === "compare" && compareChart ? (
            <section className="rounded-lg border border-line bg-card p-4">
              <h2 className="text-lg font-semibold">{compareMeta.title}</h2>
              <p className="text-sm text-muted mt-1">{compareMeta.subtitle}</p>
              <div className="mt-4 h-72">
                <Line data={compareChart} options={compareOptions} />
              </div>
              <button
                type="button"
                className="mt-4 text-sm text-accent underline"
                onClick={() => setView("detail")}
              >
                Back to single stock
              </button>
            </section>
          ) : null}

          {!selectedSymbol && !error ? (
            <p className="text-muted text-sm">Pick a company from the left to load the chart.</p>
          ) : null}
        </main>
      </div>

      <footer className="border-t border-line px-4 py-3 text-xs text-muted flex flex-wrap gap-4 items-center justify-between">
        <span>Educational demo — not investment advice.</span>
        <div className="flex flex-wrap gap-x-4 gap-y-2">
          <a
            className="text-accent hover:underline"
            href={LIVE_APP_URL}
            target="_blank"
            rel="noreferrer"
          >
            Live app (Vercel)
          </a>
          <a className="text-accent hover:underline" href={docsUrl} target="_blank" rel="noreferrer">
            Swagger UI (API)
          </a>
        </div>
      </footer>
    </div>
  );
}
