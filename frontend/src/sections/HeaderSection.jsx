export function HeaderSection({
  rangeDays,
  onRangeChange,
  showMA,
  setShowMA,
  showPred,
  setShowPred,
}) {
  return (
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
  );
}
