import { defineConfig } from "@playwright/test";

/**
 * Brief deliverable 5: a smoke test confirming the landing page renders,
 * the hero animation completes, and the reduced-motion fallback renders
 * correctly — cheap insurance against a regression silently breaking the
 * GSAP timeline entirely, not a full visual regression suite.
 *
 * Points at a locally-installed Chrome (see CHROME_PATH) rather than a
 * Playwright-managed browser download — this machine already has one at
 * C:\chrome-win64\chrome.exe (used for the Lighthouse pass too), and
 * downloading Playwright's own Chromium build is unnecessary weight for a
 * single smoke-test file.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: {
    baseURL: "http://localhost:3000",
    launchOptions: {
      executablePath: process.env.CHROME_PATH || "C:\\chrome-win64\\chrome.exe",
    },
  },
  webServer: {
    command: "pnpm start",
    url: "http://localhost:3000",
    reuseExistingServer: true,
    timeout: 30_000,
  },
});
