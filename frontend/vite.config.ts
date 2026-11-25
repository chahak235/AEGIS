import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// During development the dashboard runs on http://localhost:5173 and the API on
// http://127.0.0.1:8000. The "proxy" forwards /api/... requests from the
// dashboard to the API, so the browser sees ONE address and no CORS setup is
// needed locally. In production, VITE_API_URL points at the hosted API instead.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
    },
  },
  test: {
    environment: "node", // our tests are pure logic; no browser simulation needed
  },
});
