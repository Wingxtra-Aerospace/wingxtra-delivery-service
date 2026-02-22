import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const apiBaseUrl = env.VITE_API_BASE_URL || "http://localhost:8000";
  const apiTarget = new URL(apiBaseUrl).origin;

  return {
    plugins: [react()],
    server: {
      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true
        },
        "/health": {
          target: apiTarget,
          changeOrigin: true
        },
        "/ready": {
          target: apiTarget,
          changeOrigin: true
        },
        "/metrics": {
          target: apiTarget,
          changeOrigin: true
        }
      }
    }
  };
});
