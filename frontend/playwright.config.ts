import { defineConfig } from "@playwright/test";

/**
 * E2E configuration for the shared dev stack. The stack itself is owned
 * by scripts/e2e-stack.sh (worker + backend + frontend standalone) —
 * there is deliberately no webServer here; the script boots everything
 * and then runs `npx playwright test`, keeping CI one command.
 */

// 3000 is the operator's other dev app and 3100 is that app's e2e
// port — Kairos e2e defaults to 3200 to stay clear of both.
const frontendPort = process.env.E2E_FRONTEND_PORT || "3200";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  timeout: 90_000,
  use: {
    baseURL: `http://127.0.0.1:${frontendPort}`,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  expect: {
    timeout: 15_000,
  },
  // Matches the repo's .gitignore e2e-artifact rules.
  outputDir: "test-results",
});
