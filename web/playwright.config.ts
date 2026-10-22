import { existsSync } from "node:fs";
import { defineConfig } from "@playwright/test";

// Runs against the real API and the built app (npm run build first). Uses the installed Chrome.
// PW_BASE_URL tests a server that is already running instead (e.g. the container: docs/operations/deploy.md).
const external = process.env.PW_BASE_URL;
// the project venv locally; CI installs the package into the runner's Python instead
const uvicorn = existsSync("../.venv/bin/uvicorn") ? ".venv/bin/uvicorn" : "uvicorn";
export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  use: { baseURL: external ?? "http://127.0.0.1:8765", channel: process.env.PW_CHANNEL ?? "chrome", viewport: { width: 1360, height: 860 } },
  webServer: external ? undefined : {
    command: `${uvicorn} district_evolution.release.api:app --port 8765`,
    cwd: "..",
    env: { PYTHONPATH: "." },
    url: "http://127.0.0.1:8765/api/meta",
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
