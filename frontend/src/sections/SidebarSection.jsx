export function SidebarSection({
  search,
  setSearch,
  filteredCompanies,
  selectedSymbol,
  pickCompany,
  companies,
  cmpA,
  setCmpA,
  cmpB,
  setCmpB,
  runCompare,
  setError,
  rangeDays,
  gainers,
  losers,
}) {
  return (
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
          {filteredCompanies.map((c) => (
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
  );
}
