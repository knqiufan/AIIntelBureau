import path from "node:path";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const envDir = path.resolve(__dirname, "..");
  const env = loadEnv(mode, envDir, "");
  return {
    plugins: [react()],
    envDir,
    server: {
      port: 5173,
      proxy: { "/api": { target: env.DEMO_API_URL || "http://127.0.0.1:8000", changeOrigin: true } },
    },
    test: { exclude: ["e2e/**", "node_modules/**", "dist/**"] },
  };
});
