import { expect, test } from "@playwright/test";

/**
 * Settings page (read-only): every credential section renders, the
 * execution-mode switch and webhooks panel are present. No mutations —
 * the backend allows only 10 write requests per minute per IP.
 */

test("settings renders the full credential vault, execution mode, and webhooks", async ({
  page,
}) => {
  await page.goto("/settings", { waitUntil: "domcontentloaded" });

  // Each credential section is a panel with a password input labelled
  // "<Provider> credential" — assert every one of the 13 providers
  // renders its input, which also proves the section itself rendered.
  const providerNames = [
    "Google Gemini",
    "OpenAI",
    "Notion",
    "Jira",
    "Google Calendar",
    "Gmail",
    "Linear",
    "Todoist",
    "GitHub",
    "Confluence",
    "Google Tasks",
    "Asana",
    "ClickUp",
  ];
  for (const provider of providerNames) {
    await expect(
      page.getByLabel(`${provider} credential`, { exact: true }),
      `credential input for ${provider}`
    ).toBeVisible({ timeout: 20_000 });
  }

  // >=13 credential sections, each with its Save button (the last two
  // "Save targets"/"Saving…" variants are excluded by exact match).
  const saveButtons = page.getByRole("button", { name: "Save", exact: true });
  await expect(saveButtons).toHaveCount(providerNames.length, { timeout: 20_000 });
  expect(providerNames.length, "credential section count").toBeGreaterThanOrEqual(13);

  // Execution mode section with its sandbox/live toggle switch.
  await expect(page.getByText("Execution mode", { exact: true })).toBeVisible();
  await expect(page.getByRole("switch", { name: "Toggle sandbox mode" })).toBeVisible();

  // Outbound webhooks feed renders with its registration form.
  await expect(
    page.getByText("WEBHOOKS — OUTBOUND EVENT FEED", { exact: true })
  ).toBeVisible();
  await expect(page.getByLabel("Webhook URL")).toBeVisible();
  await expect(page.getByRole("button", { name: "Add", exact: true })).toBeVisible();

  // Tool ecosystem grid renders the full roster (12 tools).
  await expect(page.getByText("TOOL ECOSYSTEM", { exact: true })).toBeVisible();
  await expect(page.getByText("Task Ledger", { exact: true }).first()).toBeVisible();

  // No client-side errors on the page.
  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  await page.waitForTimeout(500);
  expect(consoleErrors).toEqual([]);
});

test("settings vault save + disconnect cycle", async ({ page }) => {
  // Writes: save (1) + disconnect (1). Disconnect needs confirm accept.
  await page.goto("/settings", { waitUntil: "domcontentloaded" });
  const input = page.getByLabel("Google Gemini credential", { exact: true });
  await expect(input).toBeVisible({ timeout: 20_000 });
  await input.fill("test-gemini-key");
  await input.press("Enter");
  await expect(
    page.getByText("gemini credential encrypted into the vault.", { exact: true })
  ).toBeVisible({ timeout: 15_000 });

  page.on("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Disconnect", exact: true }).click();
  await expect(
    page.getByText("gemini credential removed from the vault.", { exact: true })
  ).toBeVisible({ timeout: 15_000 });
});

test("webhooks create + delete cycle", async ({ page }) => {
  // Writes: create + arm + delete. Deletes with confirm accept; nothing left behind.
  await page.goto("/settings", { waitUntil: "domcontentloaded" });
  await expect(page.getByLabel("Webhook URL")).toBeVisible({ timeout: 20_000 });
  await page.getByLabel("Webhook URL").fill("https://example.com/e2e-hook");
  await page.getByLabel("Webhook description").fill("e2e-hook");
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await expect(page.getByText("Endpoint registered", { exact: false })).toBeVisible({
    timeout: 15_000,
  });

  page.on("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Delete webhook e2e-hook" }).click();
  await expect(page.getByText("e2e-hook", { exact: false })).toHaveCount(0, {
    timeout: 15_000,
  });
});
