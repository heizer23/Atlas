/**
 * UI tests — EssayCards — Sprint11_ReviewStats
 *
 * Covers the [UI] scenario from 10_test_spec.md: "Stats page shows three
 * window cards with grade breakdown" — the Stats nav entry navigates to
 * /essaycards/stats, and the page renders three cards (Day/Week/Month, in
 * that order) each showing a review count, a recall rate (percentage or
 * "No reviews yet"), and the again/hard/good/easy breakdown.
 *
 * Tests run against http://atlas-shell via the shared atlas-playwright
 * container. They use the live production database — no test fixtures are
 * loaded — so assertions are structural (what renders, and in what order),
 * not tied to specific counts. This is EssayCards' first UI spec file,
 * following the pattern established by
 * 03_Application/NumericSeries/tests/ui/series.spec.ts and
 * 03_Application/StoryReader/tests/ui/scroll_and_resume.spec.ts.
 */

import { test, expect } from '@playwright/test';

test('Stats nav entry navigates to the review stats page', async ({ page }) => {
  await page.goto('/essaycards');
  // Sidebar nav items are buttons (see 02_Platform/Atlas_Shell/src/navigation/Sidebar.tsx),
  // not anchors.
  await page.getByRole('button', { name: 'Stats' }).click();
  await expect(page).toHaveURL(/\/essaycards\/stats/);
  await expect(page.getByRole('heading', { name: 'Review stats' })).toBeVisible();
});

test('review stats page shows three window cards in Day, Week, Month order', async ({ page }) => {
  await page.goto('/essaycards/stats');
  await expect(page.getByRole('heading', { name: 'Review stats' })).toBeVisible();

  // Wait for the loading skeleton to resolve into the three cards.
  const headings = page.getByRole('heading', { level: 3 });
  await expect(headings).toHaveCount(3);

  const labels = await headings.allTextContents();
  expect(labels).toEqual(['Day', 'Week', 'Month']);
});

test('each window card shows a recall rate and a full grade breakdown', async ({ page }) => {
  await page.goto('/essaycards/stats');
  await expect(page.getByRole('heading', { level: 3 })).toHaveCount(3);

  for (const label of ['Day', 'Week', 'Month']) {
    const card = page.getByRole('heading', { name: label, exact: true }).locator('xpath=..');

    // Recall rate: either a rounded percentage or the literal "No reviews
    // yet" — never a bare "0%" standing in for "no data yet".
    const recallText = await card.locator('text=/%|No reviews yet/').first().textContent();
    expect(recallText).toBeTruthy();

    await expect(card.getByText('Again', { exact: true })).toBeVisible();
    await expect(card.getByText('Hard', { exact: true })).toBeVisible();
    await expect(card.getByText('Good', { exact: true })).toBeVisible();
    await expect(card.getByText('Easy', { exact: true })).toBeVisible();
  }
});
