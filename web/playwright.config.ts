import { defineConfig } from "@playwright/test";

// One real server (throwaway database) plus the dev front end, so tests click through the real app.
// Tests share one database and run in order. Locally, point PW_CHROMIUM at an installed Chromium.
export default defineConfig({
  testDir: "./e2e",
  testMatch: "*.e2e.ts", // not *.test.ts, which Vitest runs
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
    launchOptions: { executablePath: process.env.PW_CHROMIUM || undefined },
  },
  webServer: [
    { command: "e2e/start-server.sh", url: "http://localhost:8000/health", timeout: 120_000 },
    { command: "npm run dev -- --port 5173 --strictPort", url: "http://localhost:5173", timeout: 60_000 },
  ],
});
