import { expect, test } from "@playwright/test";

/**
 * All-dismiss flow: ingest -> review -> "Dismiss all" -> submit with zero
 * approvals -> history. Guards the regression where the sticky bar was
 * disabled when approvedCount === 0, making a full-dismiss review
 * unsubmittable (the backend contract always accepted all-REJECT).
 *
 * Write-budget: exactly 2 mutation calls (ingest + approve) against
 * the backend's 10/min in-process write limiter.
 */

const nonce = Date.now().toString(36);

const TRANSCRIPT = [
  `Session marker: dismiss-all-${nonce}`,
  "Sarah: Alex, please file a high priority ticket for the checkout crash bug by tomorrow morning.",
  "Alex: Sure Sarah, I will schedule a review meeting with the frontend team on Thursday at 2 PM to go over the fix.",
].join("\n");

test.setTimeout(120_000);

test("ingest -> dismiss all -> submit -> history", async ({ page }) => {
  test.setTimeout(120_000);

  await page.goto("/", { waitUntil: "domcontentloaded" });
  const editor = page.getByPlaceholder("Paste raw conversation, transcript, or unstructured notes…");
  await expect(editor).toBeVisible({ timeout: 15_000 });
  await editor.fill(TRANSCRIPT);

  await page.getByRole("button", { name: "Extract actions", exact: true }).click();
  await page.waitForURL(/\/review\/[0-9a-f][0-9a-f-]{7,}$/, { timeout: 30_000 });

  const batchId = page.url().split("/").pop() as string;

  const dismissButtons = page.getByRole("button", { name: "Dismiss", exact: true });
  await expect(dismissButtons.first()).toBeVisible({ timeout: 30_000 });
  const cardCount = await dismissButtons.count();
  expect(cardCount, "extracted action card count").toBeGreaterThanOrEqual(2);

  // Dismiss everything via the bulk button.
  await page.getByRole("button", { name: "Dismiss all", exact: true }).click();
  await expect(page.getByText(`${cardCount} dismissed`, { exact: true })).toBeVisible();

  // The sticky bar offers "Dismiss N" and it must be enabled.
  const dismissAll = page.getByRole("button", { name: new RegExp(`^Dismiss ${cardCount} actions?$`) });
  await expect(dismissAll).toBeVisible();
  await expect(dismissAll).toBeEnabled();
  await dismissAll.click();
  await page.waitForURL((url) => !url.pathname.startsWith(`/review/${batchId}`), {
    timeout: 60_000,
  });

  // Batch lands in history (all-dismissed batches complete).
  await page.goto("/history", { waitUntil: "domcontentloaded" });
  await expect(page.getByText(batchId.slice(0, 8), { exact: false }).first()).toBeVisible({
    timeout: 30_000,
  });
});
