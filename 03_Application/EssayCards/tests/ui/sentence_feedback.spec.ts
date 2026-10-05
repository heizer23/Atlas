/**
 * UI tests — EssayCards — Sprint13_ReviewStatsSentenceFeedback (essay reader)
 *
 * Covers the [UI] sentence-feedback scenarios from 10_test_spec.md: tapping a
 * sentence opens a two-button popover; both flags can be set independently
 * without closing it; marked sentences persist across reload.
 *
 * Runs against http://atlas-shell with the live database (no fixtures): it
 * opens the first essay that has readable sentences, and RESTORES any flag it
 * sets (toggles it back off) so no production data is left marked.
 */

import { test, expect, type Page } from '@playwright/test';

async function openFirstReadableEssay(page: Page) {
  const res = await page.request.get('/api/essaycards/essays');
  const essays = (await res.json()).rows as { id: string; progress_total: number }[];
  for (const e of essays) {
    const s = await page.request.get(`/api/essaycards/essays/${e.id}/sentences`);
    if ((await s.json()).rows?.length > 0) {
      await page.goto(`/essaycards/essays/${e.id}`);
      return;
    }
  }
  test.skip(true, 'no essay with sentences found');
}

test('tapping a sentence opens a popover; both flags toggle independently; difficult persists after reload', async ({ page }) => {
  await openFirstReadableEssay(page);

  // Pick a sentence span without existing indicators so we leave data as found.
  const sentence = page.locator('[data-sentence-index]:not(:has([data-testid="sentence-indicator"]))').first();
  await expect(sentence).toBeVisible({ timeout: 10000 });
  await sentence.click({ position: { x: 3, y: 3 } });

  const popover = page.getByTestId('sentence-feedback-popover');
  await expect(popover).toBeVisible();
  const difficult = popover.getByRole('button', { name: /Difficult/ });
  const thumbs = popover.getByRole('button', { name: /Thumbs up/ });
  await expect(difficult).toHaveAttribute('aria-pressed', 'false');

  await difficult.click();
  await thumbs.click();
  await expect(difficult).toHaveAttribute('aria-pressed', 'true');
  await expect(thumbs).toHaveAttribute('aria-pressed', 'true');

  // Persistence: reload and look for a trailing indicator without the popover open.
  await page.reload();
  await expect(page.getByTestId('sentence-indicator').first()).toBeVisible({ timeout: 10000 });
  await expect(page.getByTestId('sentence-feedback-popover')).toHaveCount(0);

  // Cleanup: clear both flags on the sentence we marked.
  await page.getByTestId('sentence-indicator').first().locator('xpath=..').click({ position: { x: 3, y: 3 } });
  const pop2 = page.getByTestId('sentence-feedback-popover');
  await pop2.getByRole('button', { name: /Difficult/ }).click();
  await pop2.getByRole('button', { name: /Thumbs up/ }).click();
  await expect(pop2.getByRole('button', { name: /Difficult/ })).toHaveAttribute('aria-pressed', 'false');
});
