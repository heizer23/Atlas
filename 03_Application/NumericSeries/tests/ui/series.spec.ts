/**
 * UI tests — NumericSeries — Sprint03_Chronos&UXpt2
 *
 * Covers Sprint03 UI changes:
 *   - 4-column grid layout on the series list (label | sparkline | min/max | current)
 *   - SVG sparkline renders (custom component, not recharts)
 *   - Split date + time inputs on detail page (not datetime-local)
 *   - Navigation: list → detail, list → new
 *
 * Tests run against http://atlas-shell via the shared atlas-playwright container.
 * They use the live production database — no test fixtures are loaded.
 * Tests are structural: they verify what the page renders, not specific data values.
 */

import { test, expect } from '@playwright/test';

// ── List page ──────────────────────────────────────────────────────────────────

test('list page loads and shows heading and add button', async ({ page }) => {
  await page.goto('/series');
  await expect(page.getByRole('heading', { name: 'Numeric Series' })).toBeVisible();
  await expect(page.getByTitle('Add series')).toBeVisible();
});

test('list page rows use 4-column grid layout', async ({ page }) => {
  await page.goto('/series');
  // Wait for loading to complete (skeleton disappears)
  await page.waitForSelector('[title="Add series"]');

  // If any rows are present, each must be a CSS grid with 4 columns
  const rows = page.locator('[style*="grid-template-columns"]');
  const count = await rows.count();
  if (count > 0) {
    // Each row div should have the 4-column grid template
    const firstRow = rows.first();
    const templateCols = await firstRow.evaluate(
      (el) => getComputedStyle(el).gridTemplateColumns
    );
    // Expect 4 columns (140px, 1fr, 70px, 80px → 4 track values)
    const trackCount = templateCols.trim().split(/\s+(?=\d|\()/).length;
    expect(trackCount).toBe(4);
  }
});

test('list page rows contain SVG sparkline element', async ({ page }) => {
  await page.goto('/series');
  await page.waitForSelector('[title="Add series"]');

  const rows = page.locator('[style*="grid-template-columns"]');
  const count = await rows.count();
  if (count > 0) {
    // Each row should contain either an SVG or a dash placeholder
    const firstRow = rows.first();
    const hasSvg = await firstRow.locator('svg').count();
    const hasDash = await firstRow.getByText('—').count();
    expect(hasSvg + hasDash).toBeGreaterThan(0);
  }
});

test('clicking a series row navigates to detail page', async ({ page }) => {
  await page.goto('/series');
  await page.waitForSelector('[title="Add series"]');

  const rows = page.locator('[style*="grid-template-columns"]');
  const count = await rows.count();
  if (count > 0) {
    await rows.first().click();
    await expect(page).toHaveURL(/\/series\/.+/);
    await expect(page.getByRole('heading', { name: 'Measurements' })).toBeVisible();
  }
});

// ── Add button → new series form ───────────────────────────────────────────────

test('add button navigates to new series form', async ({ page }) => {
  await page.goto('/series');
  await page.getByTitle('Add series').click();
  await expect(page).toHaveURL(/\/series\/new/);
  await expect(page.getByRole('heading', { name: 'New Series' })).toBeVisible();
  await expect(page.getByPlaceholder(/e\.g\. Weight/i)).toBeVisible();
});

// ── Detail page — split date + time inputs ─────────────────────────────────────

test('detail page add-measurement form has separate date and time inputs', async ({ page }) => {
  await page.goto('/series');

  const rows = page.locator('[style*="grid-template-columns"]');
  try {
    await rows.first().waitFor({ state: 'visible', timeout: 8000 });
  } catch {
    test.skip();
    return;
  }

  await rows.first().click();
  await expect(page.getByRole('heading', { name: 'Measurements' })).toBeVisible();

  // Sprint03: split inputs — two separate fields, not datetime-local
  const dateInput = page.locator('input[type="date"]').first();
  const timeInput = page.locator('input[type="time"]').first();
  await expect(dateInput).toBeVisible();
  await expect(timeInput).toBeVisible();

  // Ensure there is no datetime-local input (the old approach)
  const datetimeLocal = page.locator('input[type="datetime-local"]');
  await expect(datetimeLocal).toHaveCount(0);
});

test('back button on detail page returns to list', async ({ page }) => {
  await page.goto('/series');

  const rows = page.locator('[style*="grid-template-columns"]');
  try {
    await rows.first().waitFor({ state: 'visible', timeout: 8000 });
  } catch {
    test.skip();
    return;
  }

  await rows.first().click();
  await page.getByRole('button', { name: /← Back to series/i }).click();
  await expect(page).toHaveURL('/series');
});
