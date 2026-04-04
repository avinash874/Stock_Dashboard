/**
 * Build-time env (Vite). See `.env`, `.env.production`, `.env.example`.
 */
export const apiBase = String(import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

export const docsUrl = apiBase ? `${apiBase}/docs` : "/docs";

export const liveAppUrl =
  import.meta.env.VITE_APP_LIVE_URL ?? "https://stock-dashboard-tawny-nine.vercel.app";
