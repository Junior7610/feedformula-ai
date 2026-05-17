// Playwright configuration for FeedFormula AI end-to-end QA.
// It validates the deployed-like FastAPI + static frontend experience locally.

const { defineConfig, devices } = require("@playwright/test");

const PORT = process.env.PORT || "8000";
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || `http://127.0.0.1:${PORT}`;

module.exports = defineConfig({
  testDir: "./tests/e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]],
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  webServer: {
    command: `python -m uvicorn backend.main:app --host 127.0.0.1 --port ${PORT} --log-level warning`,
    url: `${BASE_URL}/sante`,
    reuseExistingServer: true,
    timeout: 120_000,
    env: {
      APP_ENV: "test",
      AFRI_API_KEY: process.env.AFRI_API_KEY || "",
      FEDAPAY_SECRET_KEY: process.env.FEDAPAY_SECRET_KEY || "",
    },
  },
  projects: [
    {
      name: "mobile-chrome",
      use: {
        ...devices["Pixel 5"],
        viewport: { width: 393, height: 851 },
      },
    },
    {
      name: "tablet",
      use: {
        ...devices["iPad (gen 7)"],
      },
    },
    {
      name: "desktop-chrome",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1000 },
      },
    },
  ],
});
