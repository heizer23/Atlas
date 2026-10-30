/**
 * UI tests — EssayCards — Sprint13_ReviewStatsSentenceFeedback (Review page)
 *
 * Covers the [UI] Review page scenarios from 10_test_spec.md: no redundant
 * "Review" page label on a plain session, the Focus caption kept on a scoped
 * session, the five daily metrics in order, and one unlabeled six-number
 * interval row.
 *
 * Runs against http://atlas-shell with the live database, so assertions are
 * structural, not tied to counts.
 */

import { test, expect } from '@playwright/test';

test('plain review page shows no standalone Review caption', async ({ page }) => {
  await page.goto('/essaycards/review');
  await expect(page.getByTestId('review-daily-metrics')).toBeVisible({ timeout: 10000 });
  await expect(page.getByText('Review', { exact: true })).toHaveCount(0);
});

test('scoped review page keeps its Focus caption', async ({ page }) => {
  await page.goto('/essaycards/review?essay_id=00000000-0000-0000-0000-000000000000');
  await expect(page.getByText('Focus · this essay')).toBeVisible({ timeout: 10000 });
});

test('review page shows the five daily metrics in order', async ({ page }) => {
  await page.goto('/essaycards/review');
  const metrics = page.getByTestId('review-daily-metrics');
  await expect(metrics).toBeVisible({ timeout: 10000 });
  const texts = await metrics.locator('div > div:nth-child(2)').allTextContents();
  expect(texts).toEqual(['Due', 'New', 'Recalls', 'Unique', 'First']);
});

test('interval row is one unlabeled row of six numbers', async ({ page }) => {
  await page.goto('/essaycards/review');
  const row = page.getByTestId('review-interval-row');
  await expect(row).toBeVisible({ timeout: 10000 });
  await expect(row).not.toContainText('All');
  await expect(row).not.toContainText('Session');
  // six column headers
  for (const h of ['≤10m', '<1d', '<7d', '<30d', '<3mo', '≥3mo']) {
    await expect(row.getByText(h, { exact: true })).toBeVisible();
  }
});
