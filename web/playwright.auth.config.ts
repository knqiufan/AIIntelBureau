import { defineConfig } from "@playwright/test";

/** An isolated server verifies the optional public-demo activity passcode path. */
export default defineConfig({
  testDir: "./e2e",
  testMatch: "access-gate.spec.ts",
  use: { baseURL: "http://127.0.0.1:5174", trace: "retain-on-failure" },
  webServer: [
    {
      command: "python -m uvicorn app.main:app --host 127.0.0.1 --port 8001",
      cwd: "../backend",
      url: "http://127.0.0.1:8001/api/readyz",
      env: { DEMO_MEMORY_ADAPTER: "in_memory", DEMO_STATE_DB_PATH: ":memory:", DEMO_LOG_LEVEL: "WARNING", DEMO_ACCESS_KEY: "e2e-activity-key" },
      reuseExistingServer: !process.env.CI,
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5174",
      url: "http://127.0.0.1:5174",
      env: { DEMO_API_URL: "http://127.0.0.1:8001" },
      reuseExistingServer: !process.env.CI,
    },
  ],
});
