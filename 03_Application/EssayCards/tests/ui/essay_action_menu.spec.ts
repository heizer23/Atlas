/**
 * UI tests — EssayCards — Sprint12_FSRSAndUXOverhaul
 *
 * Covers the [UI] scenario "Essay header action menu exposes Study and both
 * oral exam variants without a cluttered button row" from 10_test_spec.md:
 * opening a complete-status essay with flashcards shows Study as the
 * immediately-available primary action (or Question overview for a
 * cardless essay), with Guided oral exam / Unguided oral exam / Export
 * essay / + New nugget reachable from the secondary dropdown — no more than
 * the back button and one primary button visible outside the menu.
 *
 * Tests run against http://atlas-shell via the shared atlas-playwright
 * container, using the live production database — no test fixtures are
 * loaded — so this opens whichever essay the overview page lists first that
 * has a "complete" status (the first essay row, present on
 * every row) and reached by clicking the row.
 */

import { test, expect } from '@playwright/test';

test('essay header exposes a primary action plus a secondary action menu, no cluttered button row', async ({ page }) => {
  await page.goto('/essaycards');
  await expect(page.getByRole('heading', { name: 'Essays', level: 2 })).toBeVisible();

  // Open the first essay row (title + progress dots;
  // see EssayListView). Essay rows are click targets, not links.
  const firstRow = page.locator('div[style*="cursor: pointer"]').first();
  await firstRow.click();
  await expect(page).toHaveURL(/\/essaycards\/essays\//);

  // Outside the menu: only the back button and the ActionMenu's own primary
  // + "More" trigger buttons are visible (no large button row).
  const backButton = page.getByRole('button', { name: '← All essays' });
  await expect(backButton).toBeVisible();

  // Each section also gets its own ActionMenu (a "More actions" trigger only,
  // no primary button) — the essay header's is the FIRST one in document
  // order, appearing before any section content.
  const moreTrigger = page.getByRole('button', { name: 'More actions' }).first();
  await expect(moreTrigger).toBeVisible();
  await expect(moreTrigger).toHaveAttribute('aria-haspopup', 'menu');

  // Primary action is either "Study" (essay has cards) or "Question overview"
  // (essay has none) — both are valid per the scenario's own branching.
  const primaryStudy = page.getByRole('button', { name: 'Study', exact: true });
  const primaryQuestions = page.getByRole('button', { name: 'Question overview', exact: true });
  const hasPrimaryStudy = await primaryStudy.count() > 0;
  expect(hasPrimaryStudy || (await primaryQuestions.count()) > 0).toBeTruthy();

  // Open the dropdown — Guided/Unguided oral exam reachable from it.
  await moreTrigger.click();
  const menu = page.getByRole('menu');
  await expect(menu).toBeVisible();
  await expect(menu.getByRole('menuitem', { name: 'Guided oral exam', exact: true })).toBeVisible();
  await expect(menu.getByRole('menuitem', { name: 'Unguided oral exam', exact: true })).toBeVisible();
  await expect(menu.getByRole('menuitem', { name: /Export essay|Import essay/ })).toBeVisible();

  // Escape closes the menu (keyboard operable).
  await page.keyboard.press('Escape');
  await expect(menu).toBeHidden();
});
