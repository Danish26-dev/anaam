import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The Release Studio API is the local Python server (tools/studio/server.py).
// In development, Vite proxies /api to it; in production the server serves dist/.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: { "/api": { target: "http://127.0.0.1:8765", changeOrigin: false } },
  },
  build: { outDir: "dist", sourcemap: false, chunkSizeWarningLimit: 900 },
});
