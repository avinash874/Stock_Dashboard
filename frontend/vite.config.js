import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const api = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/companies": api,
      "/data": api,
      "/summary": api,
      "/compare": api,
      "/top-movers": api,
      "/predict": api,
      "/health": api,
      "/docs": api,
      "/openapi.json": api,
      "/admin": api,
    },
  },
});
