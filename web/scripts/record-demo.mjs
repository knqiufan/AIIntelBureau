import { spawn } from "node:child_process";
import { resolve } from "node:path";

const playwrightCli = resolve("node_modules/@playwright/test/cli.js");
const child = spawn(process.execPath, [playwrightCli, "test", "e2e/offline-recording.spec.ts", "--reporter=line"], {
  stdio: "inherit",
  env: { ...process.env, PLAYWRIGHT_RECORDING: "1" },
});

child.on("exit", (code) => { process.exitCode = code ?? 1; });
