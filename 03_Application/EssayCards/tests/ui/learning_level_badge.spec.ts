/**
 * UI tests — EssayCards — Sprint12_FSRSAndUXOverhaul
 *
 * Covers the [UI] scenario "Learning-level badge shows a tooltip naming all
 * four milestones" from 10_test_spec.md: the compact 0-4 badge on the essay
 * overview row (and the essay header) exposes an accessible explanation
 * naming all four milestones and their current true/false state, reachable
 * without requiring the user to already know the scoring scheme.
 *
 * Tests run against http://atlas-shell via the shared atlas-playwright
 * container, using the live production database.
 */

import { test, expect } from '@playwright/test';

test('learning-level badge on the overview row exposes an accessible explanation of all four milestones', async ({ page }) => {
  await page.goto('/essaycards');
  await expect(page.getByRole('heading', { name: 'Essays', level: 2 })).toBeVisible();

  // The badge renders as "N/4" (see LearningLevelBadge in src/ShellEntry.tsx).
  const badge = page.getByRole('button', { name: /^Learning level \d \/ 4/ }).first();
  await expect(badge).toBeVisible();

  const explanation = await badge.getAttribute('aria-label');
  expect(explanation).toBeTruthy();
  expect(explanation).toMatch(/Learning level \d \/ 4/);
  expect(explanation).toContain('All active cards seen');
  expect(explanation).toContain('All active cards reviewed, next due in 24h+');
  expect(explanation).toContain('Guided oral exam passed');
  expect(explanation).toContain('Unguided oral exam passed');
  // Accessible without hover: title (hover tooltip) carries the same text,
  // but aria-label alone already makes it screen-reader-reachable.
  await expect(badge).toHaveAttribute('title', explanation!);
});

test('learning-level badge is also present on the essay header', async ({ page }) => {
  await page.goto('/essaycards');
  const firstRow = page.locator('div[style*="cursor: pointer"]').first();
  await firstRow.click();
  await expect(page).toHaveURL(/\/essaycards\/essays\//);

  const badge = page.getByRole('button', { name: /^Learning level \d \/ 4/ });
  await expect(badge).toBeVisible();
});
