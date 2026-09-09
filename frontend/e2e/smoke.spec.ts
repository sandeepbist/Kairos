import { expect, test } from "@playwright/test";

/**
 * Page smokes: every public route renders its wordmark, nav, and hero
 * without a client-side console.error.
 */

const PAGES: Array<{ path: string; expectText: string }> = [
  { path: "/", expectText: "Conversations in." },
  { path: "/history", expectText: "Execution history" },
  { path: "/settings", expectText: "Settings" },
  { path: "/terms", expectText: "Terms of Service" },
  { path: "/privacy", expectText: "Privacy Policy" },
];

for (const { path, expectText } of PAGES) {
  test(`page ${path} renders cleanly`, async ({ page }) => {
    const consoleErrors: string[] = [];

    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });

    const response = await page.goto(path, { waitUntil: "domcontentloaded" });
    expect(response, `${path} responded`).not.toBeNull();
    expect(response!.status(), `${path} HTTP status`).toBeLessThan(400);

    // Wordmark + nav
    await expect(page.getByRole("link", { name: "Kairos", exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Ingest", exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "History", exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Settings", exact: true })).toBeVisible();

    // Route hero/heading
    await expect(page.getByText(expectText, { exact: false }).first()).toBeVisible({
      timeout: 20_000,
    });

    // Give client components a beat to surface any late errors, then read
    // the collected console output. Fetch failures of API routes surface as
    // console.error("GET /api/... 502") in Chromium — filter network noise
    // and only fail on genuine JS errors.
    await page.waitForTimeout(700);
    const jsErrors = consoleErrors.filter(
      (text) =>
        !/net::ERR/i.test(text) &&
        !/the server responded with a status of/i.test(text) &&
        !/Failed to load resource/i.test(text)
    );
    expect(jsErrors, `console.error output on ${path}`).toEqual([]);
  });
}
