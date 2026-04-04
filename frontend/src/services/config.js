/**
 * API origin for fetch(). In dev, empty string uses Vite’s proxy (see vite.config.js).
 * On Vercel, `VITE_API_BASE` is often missing (`.env.production` not in git) — then we fall back
 * to the deployed FastAPI on Render so `/companies` does not hit *.vercel.app (404).
 */
/** FastAPI backend (Render) — used when VITE_API_BASE is empty in production builds */
const BACKEND_URL_DEFAULT = "https://stock-dashboard-1-0qoi.onrender.com";

function resolveApiBase() {
  const fromEnv = String(import.meta.env.VITE_API_BASE ?? "").trim().replace(/\/$/, "");
  if (fromEnv) return fromEnv;
  if (import.meta.env.DEV) return "";
  return BACKEND_URL_DEFAULT.replace(/\/$/, "");
}

export const apiBase = resolveApiBase();

export const docsUrl = apiBase ? `${apiBase}/docs` : "/docs";

export const liveAppUrl =
  import.meta.env.VITE_APP_LIVE_URL ?? "https://stock-dashboard-1-0qoi.onrender.com";
