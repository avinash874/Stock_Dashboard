import { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchCompanies,
  fetchCompare,
  fetchPredict,
  fetchStockData,
  fetchSummary,
  fetchTopMovers,
} from "../services/api";
import { buildCompareChartData, buildCompareMeta } from "../logic/compareChartDatasets";
import { buildPriceDatasets } from "../logic/priceChartDatasets";
import { compareLineChartOptions } from "../logic/chartOptions";

export function useStockDashboard() {
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
  const [cmpA, setCmpA] = useState("");
  const [cmpB, setCmpB] = useState("");

  const filteredCompanies = useMemo(() => {
    const q = search.toLowerCase();
    return companies.filter((c) => {
      const hay = `${c.display_symbol} ${c.name || ""}`.toLowerCase();
      return !q || hay.includes(q);
    });
  }, [companies, search]);

  const loadTopMovers = useCallback(async (days) => {
    try {
      const m = await fetchTopMovers(days);
      setGainers(m.top_gainers || []);
      setLosers(m.top_losers || []);
    } catch (e) {
      console.warn(e);
    }
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const data = await fetchCompanies();
        setCompanies(data.companies || []);
        const m = await fetchTopMovers(30);
        setGainers(m.top_gainers || []);
        setLosers(m.top_losers || []);
      } catch (e) {
        setError(e.message);
      }
    })();
  }, []);

  const loadDetail = useCallback(
    async (symbol) => {
      setError("");
      const days = parseInt(rangeDays, 10);
      const predPromise = showPred
        ? fetchPredict(symbol, days).catch(() => null)
        : Promise.resolve(null);

      const [series, sum, pred] = await Promise.all([
        fetchStockData(symbol, days),
        fetchSummary(symbol),
        predPromise,
      ]);

      setSummary(sum);
      setPriceChart(buildPriceDatasets(series, showMA, pred));
    },
    [rangeDays, showMA, showPred]
  );

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

  useEffect(() => {
    if (!companies.length) return;
    setCmpA(companies[0]?.display_symbol ?? "");
    setCmpB(companies[1]?.display_symbol ?? companies[0]?.display_symbol ?? "");
  }, [companies]);

  const pickCompany = useCallback((symbol) => {
    setView("detail");
    setSelectedSymbol(symbol);
  }, []);

  const onRangeChange = useCallback(
    async (v) => {
      setRangeDays(v);
      await loadTopMovers(v);
    },
    [loadTopMovers]
  );

  const runCompare = useCallback(
    async (s1, s2) => {
      if (!s1 || !s2) return;
      setError("");
      setView("compare");
      const days = Math.max(parseInt(rangeDays, 10), 30);
      const data = await fetchCompare(s1, s2, days);
      setCompareMeta(buildCompareMeta(data));
      setCompareChart(buildCompareChartData(data));
    },
    [rangeDays]
  );

  const compareOptions = useMemo(() => compareLineChartOptions(), []);

  return {
    companies,
    filteredCompanies,
    search,
    setSearch,
    rangeDays,
    showMA,
    setShowMA,
    showPred,
    setShowPred,
    selectedSymbol,
    error,
    gainers,
    losers,
    summary,
    priceChart,
    compareChart,
    view,
    setView,
    compareMeta,
    cmpA,
    setCmpA,
    cmpB,
    setCmpB,
    pickCompany,
    onRangeChange,
    runCompare,
    compareOptions,
    setError,
  };
}
