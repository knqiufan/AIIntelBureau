import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testIgnore: "access-gate.spec.ts",
  use: {
    baseURL: "http://127.0.0.1:5183",
    trace: "retain-on-failure",
    // `npm run record:demo` enables a durable local WebM for the runbook.
    video: process.env.PLAYWRIGHT_RECORDING === "1" ? "on" : "retain-on-failure",
  },
  webServer: [
    {
      command: "python -m uvicorn app.main:app --host 127.0.0.1 --port 8013",
      cwd: "../backend",
      url: "http://127.0.0.1:8013/api/readyz",
      // Keep normal offline UI tests independent from a developer's optional
      // public-demo passcode in ../.env. The auth config exercises that path.
      env: { DEMO_MODE: "degrade", DEMO_MEMORY_ADAPTER: "in_memory", DEMO_STATE_DB_PATH: ":memory:", DEMO_LOG_LEVEL: "WARNING", DEMO_WARMUP: "false", DEMO_OPERATOR_ACCESS_KEY: "", DEMO_STAGE_ACCESS_KEY: "", DEMO_ACCESS_COOKIE_SECURE: "false" },
      reuseExistingServer: false,
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5183",
      url: "http://127.0.0.1:5183",
      env: { DEMO_API_URL: "http://127.0.0.1:8013" },
      reuseExistingServer: false,
    },
  ],
});
