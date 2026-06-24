import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy /api to the FastAPI backend in dev so the frontend and backend share
// an origin (no CORS friction) and the same code works in production behind a
// single reverse proxy.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        // Use 127.0.0.1 (not "localhost") so the proxy always hits the
        // backend's IPv4 listener — on Windows "localhost" can resolve to IPv6
        // (::1) first, which the backend isn't bound to, causing the proxy to
        // fall back to serving index.html for /api requests.
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
