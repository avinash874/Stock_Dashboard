/**
 * Turn `/data` + optional `/predict` payloads into Chart.js `data` + a stable `chartKey` for remounting.
 */
export function buildPriceDatasets(series, showMA, pred) {
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
