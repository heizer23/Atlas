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
  await expect(zoneHeadings).toHaveCount(6, { timeout: 10000 }); // 5 zones + the one selected-period card inside "Observed recall"

  const texts = await zoneHeadings.allTextContents();
  const zoneOrder = ['Study activity', 'Scheduled reviews (forecast)', 'Observed recall', 'Scheduled intervals', 'Essay learning progress'];
  // The five zone headings appear, in this relative order (the period card sits
  // between "Observed recall" and "Scheduled intervals").
  let cursor = -1;
  for (const zone of zoneOrder) {
    const idx = texts.indexOf(zone, cursor + 1);
    expect(idx, `zone "${zone}" should appear after index ${cursor}`).toBeGreaterThan(cursor);
    cursor = idx;
  }

  // Forecast vs observed wording is explicit, not left implicit.
  await expect(page.getByText(/predicted to come due next/i)).toBeVisible();
  await expect(page.getByText(/What actually happened over the last day, week or month/i)).toBeVisible();
});

test('Observed recall selector switches the displayed period and shows four figures', async ({ page }) => {
  await page.goto('/essaycards/stats');
  await expect(page.getByRole('heading', { name: 'Observed recall', level: 3 })).toBeVisible({ timeout: 10000 });

  const group = page.getByRole('group', { name: 'Observed recall period' });
  const card = (label: string) => page.getByRole('heading', { name: label, level: 3, exact: true });

  // Default is Day; only one period's card is shown at a time.
  await expect(group.getByRole('button', { name: 'Day' })).toHaveAttribute('aria-pressed', 'true');
  await expect(card('Day')).toBeVisible();
  await expect(card('Week')).toHaveCount(0);

  await group.getByRole('button', { name: 'Week' }).click();
  await expect(group.getByRole('button', { name: 'Week' })).toHaveAttribute('aria-pressed', 'true');
  await expect(card('Week')).toBeVisible();
  await expect(card('Day')).toHaveCount(0);

  const weekCard = card('Week').locator('xpath=..');
  for (const label of ['Cards Seen', 'Unique Cards Seen', 'New Cards Seen', 'Recall Rate']) {
    await expect(weekCard.getByText(label, { exact: true })).toBeVisible();
  }
  // Recall rate: a rounded percentage or "No reviews yet" — never a bare 0% for no data.
  const recallText = await weekCard.locator('text=/%|No reviews yet/').first().textContent();
  expect(recallText).toBeTruthy();
});

test('Study activity chart shows stacked columns with a recall-rate label per day and a Repeat/Unique/First legend', async ({ page }) => {
  await page.goto('/essaycards/stats');
  const chart = page.getByTestId('daily-activity-chart');
  await expect(chart).toBeVisible({ timeout: 10000 });
  await expect(chart.getByTestId('activity-column')).toHaveCount(30);
  await expect(chart.getByTestId('activity-rate')).toHaveCount(30);
  await expect(chart).toContainText('Repeat');
  await expect(chart).toContainText('Unique');
  await expect(chart).toContainText('First');
});

test('[UI] essay progress zone shows traffic-light buckets', async ({ page }) => {
  await page.goto('/essaycards/stats');
  await expect(page.getByRole('heading', { name: 'Essay learning progress', level: 3 })).toBeVisible({ timeout: 10000 });

  // The zone's chart is labelled by essay state (Sprint14), never the 0/4..4/4 learning levels.
  const zone = page.locator('xpath=//h3[normalize-space()="Essay learning progress"]/following-sibling::*[position() <= 2]');
  const text = (await zone.allTextContents()).join(' ');
  for (const state of ['Grey', 'Yellow', 'Green', 'Blue', 'Violet']) {
    expect(text, `bucket ${state}`).toContain(state);
  }
  expect(text).not.toMatch(/\b[0-4]\/4\b/);
});
