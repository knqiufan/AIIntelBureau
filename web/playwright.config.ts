import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testIgnore: "access-gate.spec.ts",
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    // `npm run record:demo` enables a durable local WebM for the runbook.
    video: process.env.PLAYWRIGHT_RECORDING === "1" ? "on" : "retain-on-failure",
  },
  webServer: [
    {
      command: "python -m uvicorn app.main:app --host 127.0.0.1 --port 8000",
      cwd: "../backend",
      url: "http://127.0.0.1:8000/api/readyz",
      // Keep normal offline UI tests independent from a developer's optional
      // public-demo passcode in ../.env. The auth config exercises that path.
      env: { DEMO_MEMORY_ADAPTER: "in_memory", DEMO_STATE_DB_PATH: ":memory:", DEMO_LOG_LEVEL: "WARNING", DEMO_ACCESS_KEY: "", DEMO_ACCESS_COOKIE_SECURE: "false" },
      reuseExistingServer: !process.env.CI,
    },
    {
      command: "npm run dev -- --host 127.0.0.1",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: !process.env.CI,
    },
  ],
});
