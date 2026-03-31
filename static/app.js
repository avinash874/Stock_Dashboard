const API = "";

let chart;
let compareChart;
let companies = [];
let selectedSymbol = null;

function $(id) {
  return document.getElementById(id);
}

function showError(msg) {
  const el = $("err");
  el.textContent = msg || "";
  el.classList.toggle("hidden", !msg);
}

async function fetchJSON(path) {
  const r = await fetch(`${API}${path}`);
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json();
}

function renderCompanyList(list) {
  const ul = $("companyList");
  ul.innerHTML = "";
  const q = ($("companySearch").value || "").toLowerCase();
  list
    .filter((c) => {
      const hay = `${c.display_symbol} ${c.name || ""}`.toLowerCase();
      return !q || hay.includes(q);
    })
    .forEach((c) => {
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.dataset.symbol = c.display_symbol;
      btn.innerHTML = `<span class="name">${c.display_symbol}</span><span class="full">${c.name || ""}</span>`;
      if (c.display_symbol === selectedSymbol) btn.classList.add("active");
      btn.addEventListener("click", () => selectCompany(c.display_symbol));
      li.appendChild(btn);
      ul.appendChild(li);
    });
}

function fillCompareSelects() {
  const a = $("cmpA");
  const b = $("cmpB");
  a.innerHTML = "";
  b.innerHTML = "";
  companies.forEach((c, i) => {
    a.appendChild(new Option(`${c.display_symbol} — ${c.name || ""}`, c.display_symbol));
    b.appendChild(new Option(`${c.display_symbol} — ${c.name || ""}`, c.display_symbol));
  });
  if (companies.length > 1) {
    b.selectedIndex = 1;
  }
}

async function loadCompanies() {
  const data = await fetchJSON("/companies");
  companies = data.companies || [];
  renderCompanyList(companies);
  fillCompareSelects();
  const days = $("rangeDays").value;
  $("moverWindow").textContent = `(${days}d)`;
  await loadTopMovers(days);
}

async function loadTopMovers(days) {
  try {
    const m = await fetchJSON(`/top-movers?days=${days}`);
    const g = $("gainers");
    const l = $("losers");
    g.innerHTML = "";
    l.innerHTML = "";
    (m.top_gainers || []).forEach((x) => {
      const li = document.createElement("li");
      li.innerHTML = `<span>${x.symbol}</span><span><span style="color:var(--accent2)">+${x.return_pct}%</span></span>`;
      g.appendChild(li);
    });
    (m.top_losers || []).forEach((x) => {
      const li = document.createElement("li");
      li.innerHTML = `<span>${x.symbol}</span><span><span style="color:var(--danger)">${x.return_pct}%</span></span>`;
      l.appendChild(li);
    });
  } catch (e) {
    console.warn(e);
  }
}

async function loadPredict(symbol, days) {
  try {
    return await fetchJSON(`/predict/${encodeURIComponent(symbol)}?days=${days}`);
  } catch {
    return null;
  }
}

async function selectCompany(symbol) {
  selectedSymbol = symbol;
  showError("");
  renderCompanyList(companies);
  const days = parseInt($("rangeDays").value, 10);
  $("chartCard").classList.remove("hidden");
  $("summaryCard").classList.remove("hidden");
  $("compareCard").classList.add("hidden");

  $("chartTitle").textContent = symbol;
  $("chartMeta").textContent = "Loading…";

  const [series, summary, pred] = await Promise.all([
    fetchJSON(`/data/${encodeURIComponent(symbol)}?days=${days}`),
    fetchJSON(`/summary/${encodeURIComponent(symbol)}`),
    $("showPred").checked ? loadPredict(symbol, days) : Promise.resolve(null),
  ]);

  const labels = series.data.map((d) => d.date);
  const closes = series.data.map((d) => d.close);
  const ma7 = series.data.map((d) => d.ma7);
  $("chartMeta").textContent = `${series.days} rows · last close ${closes.at(-1)?.toFixed(2) ?? "—"}`;

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
  if ($("showMA").checked) {
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

    const bridgeApr = [
      ...Array(L - 1).fill(null),
      lastClose,
      ...pa,
      ...Array(nMay).fill(null),
    ];
    const bridgeMay =
      nMay > 0
        ? [
            ...Array(L + nApr - 1).fill(null),
            lastApr,
            ...pm,
          ]
        : null;

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
    if (chart) chart.destroy();
    chart = new Chart($("priceChart"), {
      type: "line",
      data: { labels: extLabels, datasets },
      options: {
        responsive: true,
        plugins: { legend: { labels: { color: "#8b9bb4" } } },
        scales: {
          x: { ticks: { color: "#8b9bb4", maxTicksLimit: 10 }, grid: { color: "#2d3a4d" } },
          y: { ticks: { color: "#8b9bb4" }, grid: { color: "#2d3a4d" } },
        },
      },
    });
  } else {
    if (chart) chart.destroy();
    chart = new Chart($("priceChart"), {
      type: "line",
      data: { labels, datasets },
      options: {
        responsive: true,
        plugins: { legend: { labels: { color: "#8b9bb4" } } },
        scales: {
          x: { ticks: { color: "#8b9bb4", maxTicksLimit: 8 }, grid: { color: "#2d3a4d" } },
          y: { ticks: { color: "#8b9bb4" }, grid: { color: "#2d3a4d" } },
        },
      },
    });
  }

  const dl = $("summaryDl");
  dl.innerHTML = "";
  const rows = [
    ["52-week high", summary.week52_high?.toFixed(2)],
    ["52-week low", summary.week52_low?.toFixed(2)],
    ["Average close (all history)", summary.average_close?.toFixed(2)],
    ["Last close", summary.last_close?.toFixed(2)],
    ["Latest vol (ann.)", summary.latest_volatility != null ? summary.latest_volatility.toFixed(4) : "—"],
  ];
  rows.forEach(([k, v]) => {
    const dt = document.createElement("dt");
    dt.textContent = k;
    const dd = document.createElement("dd");
    dd.textContent = v ?? "—";
    dl.appendChild(dt);
    dl.appendChild(dd);
  });
}

async function runCompare() {
  const s1 = $("cmpA").value;
  const s2 = $("cmpB").value;
  if (!s1 || !s2) return;
  showError("");
  $("compareCard").classList.remove("hidden");
  $("summaryCard").classList.add("hidden");
  $("chartCard").classList.add("hidden");

  const days = Math.max(parseInt($("rangeDays").value, 10), 30);
  const data = await fetchJSON(
    `/compare?symbol1=${encodeURIComponent(s1)}&symbol2=${encodeURIComponent(s2)}&days=${days}`
  );
  $("compareTitle").textContent = `${data.symbol1} vs ${data.symbol2}`;
  $("compareMeta").textContent = `Return: ${data.symbol1} ${data.total_return_pct_symbol1}% · ${data.symbol2} ${data.total_return_pct_symbol2}% · corr ${data.return_correlation ?? "—"}`;

  const labels = data.series.map((p) => p.date);
  if (compareChart) compareChart.destroy();
  compareChart = new Chart($("compareChart"), {
    type: "line",
    data: {
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
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: "#8b9bb4" } } },
      scales: {
        x: { ticks: { color: "#8b9bb4", maxTicksLimit: 8 }, grid: { color: "#2d3a4d" } },
        y: {
          ticks: { color: "#8b9bb4" },
          grid: { color: "#2d3a4d" },
          title: { display: true, text: "Indexed to 100 at start", color: "#8b9bb4" },
        },
      },
    },
  });
}

document.addEventListener("DOMContentLoaded", () => {
  $("companySearch").addEventListener("input", () => renderCompanyList(companies));
  $("rangeDays").addEventListener("change", async () => {
    const d = $("rangeDays").value;
    $("moverWindow").textContent = `(${d}d)`;
    await loadTopMovers(d);
    if (selectedSymbol) await selectCompany(selectedSymbol);
  });
  $("showMA").addEventListener("change", () => {
    if (selectedSymbol) selectCompany(selectedSymbol);
  });
  $("showPred").addEventListener("change", () => {
    if (selectedSymbol) selectCompany(selectedSymbol);
  });
  $("btnCompare").addEventListener("click", () => runCompare().catch((e) => showError(e.message)));

  loadCompanies().catch((e) => showError(e.message));
});
