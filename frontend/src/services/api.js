import { apiBase } from "./config";

export async function fetchJSON(path) {
  const url = `${apiBase}${path}`;
  const res = await fetch(url);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json();
}

export function fetchCompanies() {
  return fetchJSON("/companies");
}

export function fetchTopMovers(days) {
  return fetchJSON(`/top-movers?days=${days}`);
}

export function fetchStockData(symbol, days) {
  return fetchJSON(`/data/${encodeURIComponent(symbol)}?days=${days}`);
}

export function fetchSummary(symbol) {
  return fetchJSON(`/summary/${encodeURIComponent(symbol)}`);
}

export function fetchPredict(symbol, days) {
  return fetchJSON(`/predict/${encodeURIComponent(symbol)}?days=${days}`);
}

export function fetchCompare(symbol1, symbol2, days) {
  const q = new URLSearchParams({
    symbol1,
    symbol2,
    days: String(days),
  });
  return fetchJSON(`/compare?${q}`);
}
