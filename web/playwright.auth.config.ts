import { defineConfig } from "@playwright/test";

/** An isolated server verifies separate operator and stage access paths. */
export default defineConfig({
  testDir: "./e2e",
  testMatch: "access-gate.spec.ts",
  use: { baseURL: "http://127.0.0.1:5184", trace: "retain-on-failure" },
  webServer: [
    {
      command: "python -m uvicorn app.main:app --host 127.0.0.1 --port 8014",
      cwd: "../backend",
      url: "http://127.0.0.1:8014/api/readyz",
      env: { DEMO_MODE: "degrade", DEMO_MEMORY_ADAPTER: "in_memory", DEMO_STATE_DB_PATH: ":memory:", DEMO_LOG_LEVEL: "WARNING", DEMO_WARMUP: "false", DEMO_OPERATOR_ACCESS_KEY: "e2e-activity-key", DEMO_STAGE_ACCESS_KEY: "e2e-stage-key", DEMO_ACCESS_COOKIE_SECURE: "false" },
      reuseExistingServer: false,
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5184",
      url: "http://127.0.0.1:5184",
      env: { DEMO_API_URL: "http://127.0.0.1:8014" },
      reuseExistingServer: false,
    },
  ],
});
