import { defaultLineChartOptions } from "../logic/chartOptions";
import { CompareLineChart } from "../components/CompareLineChart";
import { PriceLineChart } from "../components/PriceLineChart";

export function MainSection({
  error,
  view,
  setView,
  selectedSymbol,
  priceChart,
  summary,
  compareChart,
  compareMeta,
  compareOptions,
}) {
  return (
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
            <PriceLineChart
              labels={priceChart.labels}
              datasets={priceChart.datasets}
              chartKey={priceChart.chartKey}
              options={defaultLineChartOptions}
            />
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
          <CompareLineChart chartData={compareChart} options={compareOptions} />
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
  );
}
