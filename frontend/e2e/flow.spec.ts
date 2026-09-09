import { expect, test } from "@playwright/test";

/**
 * Flagship flow: ingest -> review -> approve -> executed.
 *
 * The transcript is the review-page fixture (meeting preset): 4 speaker
 * lines, each hitting a deterministic-extractor rule (Jira keyword,
 * Calendar keyword, Notion keyword, action-keyword fallback to the
 * ledger) so the deterministic extractor (APP_ENV=test) yields exactly
 * 4 action items every run. A per-run nonce goes into the leading
 * "Session marker" line: it carries no action/calendar/jira/notion
 * keyword, so the extractor drops it (verified: 4 items, no marker
 * item). Batches are fresh uuid4 rows per ingest — no text-level
 * idempotency dedupe exists — but the unique text additionally keeps
 * concurrent e2e runs from colliding in the shared history view.
 *
 * Write-budget: exactly 2 mutation calls (ingest + approve) against
 * the backend's 10/min in-process write limiter.
 */

const nonce = Date.now().toString(36);

const TRANSCRIPT = [
  `Session marker: e2e-${nonce}`,
  "Sarah: Alex, please file a high priority ticket for the checkout crash bug by tomorrow morning.",
  "Alex: Sure Sarah, I will schedule a review meeting with the frontend team on Thursday at 2 PM to go over the fix.",
  "John: I will update the technical spec doc in the roadmap wiki and share it with leadership.",
  "Sarah: Let's also make sure someone follows up on the billing invoices discrepancy.",
].join("\n");

test.setTimeout(120_000);

test("ingest -> review -> approve one, dismiss one -> executed banner -> history", async ({
  page,
}) => {
  test.setTimeout(120_000);

  // ── a. Ingest: editor visible, paste the transcript ──────────────
  await page.goto("/", { waitUntil: "domcontentloaded" });
  const editor = page.getByPlaceholder("Paste raw conversation, transcript, or unstructured notes…");
  await expect(editor).toBeVisible({ timeout: 15_000 });
  await editor.fill(TRANSCRIPT);

  // ── b. Submit via the real button; app router.pushes to /review ──
  await page.getByRole("button", { name: "Extract actions", exact: true }).click();
  await page.waitForURL(/\/review\/[0-9a-f][0-9a-f-]{7,}$/, { timeout: 30_000 });

  const batchId = page.url().split("/").pop() as string;

  // ── c. Review page: >=3 action cards + source lines ──────────────
  // Every card starts seeded-APPROVED: its buttons read "Dismiss" and
  // "Approved" (not "Approve"), so cards are counted via "Dismiss".
  const dismissButtons = page.getByRole("button", { name: "Dismiss", exact: true });
  await expect(dismissButtons.first()).toBeVisible({ timeout: 30_000 });
  const cardCount = await dismissButtons.count();
  expect(cardCount, "extracted action card count").toBeGreaterThanOrEqual(3);

  // Source viewer renders the transcript as numbered lines.
  const sourceLines = page.locator(".source-line");
  await expect(sourceLines.first()).toBeVisible();
  expect(await sourceLines.count(), "rendered source lines").toBeGreaterThanOrEqual(5);

  // ── d. Dismiss the first card, keep the rest approved. The first ──
  // card flips to a "Dismissed" (danger) button; the exec bar's
  // approved/dismissed counters update reactively.
  await dismissButtons.first().click();
  await expect(
    page.getByRole("button", { name: "Dismissed", exact: true }).first()
  ).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("1 dismissed", { exact: true })).toBeVisible();

  // The remaining cards still show their seeded "Approved" state.
  await expect(
    page.getByRole("button", { name: "Approved", exact: true }).first()
  ).toBeVisible({ timeout: 15_000 });

  // ── e. Execute via the sticky bar; success router.pushes to ───────
  // /history — wait for the navigation away from the review page.
  const execute = page.getByRole("button", { name: /^Execute \d+ actions?$/ });
  await expect(execute).toBeVisible();
  await expect(execute).toContainText(String(cardCount - 1));
  await execute.click();
  await page.waitForURL((url) => !url.pathname.startsWith(`/review/${batchId}`), {
    timeout: 60_000,
  });

  // ── f. Banner on the batch page: "Executed — N ran, 1 dismissed." ──
  await page.goto(`/review/${batchId}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByText("Executed —", { exact: false }).first()).toBeVisible({
    timeout: 60_000,
  });
  // Parts, not the full string (N depends on extracted item count).
  await expect(page.getByText(" ran", { exact: false }).first()).toBeVisible();
  await expect(page.getByText(", 1 dismissed", { exact: false }).first()).toBeVisible();

  // Per-item outcome chips reflect the decision: the dismissed card
  // shows the "Dismissed" outcome tag (read-only mode).
  await expect(page.locator(".tag", { hasText: "Dismissed" }).first()).toBeVisible({
    timeout: 15_000,
  });

  // ── g. History: the batch appears with the Completed status label ──
  // and a View link (terminal status).
  await page.goto("/history", { waitUntil: "domcontentloaded" });
  const row = page.locator(".panel", { hasText: batchId.slice(0, 8) }).first();
  await expect(row).toBeVisible({ timeout: 30_000 });
  await expect(row.getByText("Completed", { exact: true })).toBeVisible();
  await expect(row.getByRole("link", { name: "View" })).toBeVisible();
});
