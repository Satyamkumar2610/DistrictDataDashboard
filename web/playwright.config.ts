import { defineConfig } from "@playwright/test";

// Runs against the real API and the built app (npm run build first). Uses the installed Chrome.
export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  use: { baseURL: "http://127.0.0.1:8765", channel: process.env.PW_CHANNEL ?? "chrome", viewport: { width: 1360, height: 860 } },
  webServer: {
    command: ".venv/bin/uvicorn district_evolution.release.api:app --port 8765",
    cwd: "..",
    env: { PYTHONPATH: "." },
    url: "http://127.0.0.1:8765/api/meta",
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
