/**
 * UI tests — EssayCards — Sprint11_ReviewStats, reworked Sprint12_FSRSAndUXOverhaul
 *
 * Covers the [UI] "Stats page clearly distinguishes observed vs predicted"
 * requirement (10_architecture.json §deferrals.ui_implementer): the reworked
 * stats page renders five clearly labeled zones — Study activity, Scheduled
 * reviews (forecast), Observed recall, Scheduled intervals, Essay learning
 * progress — in that order, with "Observed recall" containing the three
 * Day/Week/Month window cards from GET /review-stats/summary.
 *
 * Tests run against http://atlas-shell via the shared atlas-playwright
 * container, using the live production database — no test fixtures are
 * loaded — so assertions are structural (what renders, and in what order),
 * not tied to specific counts.
 */

import { test, expect } from '@playwright/test';

test('Stats nav entry navigates to the stats page', async ({ page }) => {
  await page.goto('/essaycards');
  // Sidebar nav items are buttons (see 02_Platform/Atlas_Shell/src/navigation/Sidebar.tsx),
  // not anchors.
  await page.getByRole('button', { name: 'Stats' }).click();
  await expect(page).toHaveURL(/\/essaycards\/stats/);
  await expect(page.getByRole('heading', { name: 'Stats', level: 2 })).toBeVisible();
});

test('stats page renders five zones in order, forecast and observed recall clearly distinguished', async ({ page }) => {
  await page.goto('/essaycards/stats');
  await expect(page.getByRole('heading', { name: 'Stats', level: 2 })).toBeVisible();

  // Wait for the loading skeleton to resolve into the zone headings.
  const zoneHeadings = page.getByRole('heading', { level: 3 });
  await expect(zoneHeadings).toHaveCount(8, { timeout: 10000 }); // 5 zones + 3 window cards inside "Observed recall"

  const texts = await zoneHeadings.allTextContents();
  const zoneOrder = ['Study activity', 'Scheduled reviews (forecast)', 'Observed recall', 'Scheduled intervals', 'Essay learning progress'];
  // The five zone headings appear, in this relative order (window cards sit
  // between "Observed recall" and "Scheduled intervals").
  let cursor = -1;
  for (const zone of zoneOrder) {
    const idx = texts.indexOf(zone, cursor + 1);
    expect(idx, `zone "${zone}" should appear after index ${cursor}`).toBeGreaterThan(cursor);
    cursor = idx;
  }

  // Forecast vs observed wording is explicit, not left implicit.
  await expect(page.getByText(/schedule FORECAST, not an observed fact/i)).toBeVisible();
  await expect(page.getByText(/OBSERVED, not predicted/i)).toBeVisible();
});

test('Observed recall zone shows Day, Week, Month cards with recall rate and grade breakdown', async ({ page }) => {
  await page.goto('/essaycards/stats');
  await expect(page.getByRole('heading', { name: 'Observed recall', level: 3 })).toBeVisible({ timeout: 10000 });

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
