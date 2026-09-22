import { expect, test } from "@playwright/test";

/**
 * Keyboard review: j/k moves DOM focus between cards, x dismisses the
 * focused card. Locks the focus-follows-keyboard contract (scroll-only
 * focus leaves screen-reader users behind).
 *
 * Write-budget: 1 mutation call (ingest only, no approval POST).
 */

const nonce = Date.now().toString(36);

const TRANSCRIPT = [
  `Session marker: keyboard-${nonce}`,
  "Sarah: Alex, please file a high priority ticket for the checkout crash bug by tomorrow morning.",
  "Alex: Sure Sarah, I will schedule a review meeting with the frontend team on Thursday at 2 PM to go over the fix.",
].join("\n");

test.setTimeout(120_000);

test("keyboard review: j focuses cards, x dismisses focused", async ({ page }) => {
  test.setTimeout(120_000);

  await page.goto("/", { waitUntil: "domcontentloaded" });
  const editor = page.getByPlaceholder("Paste raw conversation, transcript, or unstructured notes…");
  await expect(editor).toBeVisible({ timeout: 15_000 });
  await editor.fill(TRANSCRIPT);

  await page.getByRole("button", { name: "Extract actions", exact: true }).click();
  await page.waitForURL(/\/review\/[0-9a-f][0-9a-f-]{7,}$/, { timeout: 30_000 });

  const cards = page.locator('div[tabindex="-1"][aria-label^="Action item"]');
  await expect(cards.first()).toBeVisible({ timeout: 30_000 });
  expect(await cards.count()).toBeGreaterThanOrEqual(2);

  // j lands DOM focus on the first card.
  await page.keyboard.press("j");
  await expect(cards.first()).toBeFocused();

  // Second j moves focus to the second card.
  await page.keyboard.press("j");
  await expect(cards.nth(1)).toBeFocused();

  // x dismisses the focused (second) card.
  await page.keyboard.press("x");
  await expect(
    page.getByRole("button", { name: "Dismissed", exact: true }).first()
  ).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("1 dismissed", { exact: true })).toBeVisible();

  // e opens the payload editor on the focused card with focus inside
  // the dialog; Escape closes and returns focus to the card.
  await page.keyboard.press("e");
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible({ timeout: 15_000 });
  const focusedTag = await page.evaluate(() => document.activeElement?.tagName);
  expect(["INPUT", "SELECT", "TEXTAREA"]).toContain(focusedTag);
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(cards.nth(1)).toBeFocused();
});
