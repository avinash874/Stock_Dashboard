/** Build Chart.js data from `GET /compare` JSON */
export function buildCompareChartData(data) {
  const labels = data.series.map((p) => p.date);
  return {
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
  };
}

export function buildCompareMeta(data) {
  return {
    title: `${data.symbol1} vs ${data.symbol2}`,
    subtitle: `Return: ${data.symbol1} ${data.total_return_pct_symbol1}% · ${data.symbol2} ${data.total_return_pct_symbol2}% · corr ${data.return_correlation ?? "—"}`,
  };
}
