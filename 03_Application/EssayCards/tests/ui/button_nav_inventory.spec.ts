/**
 * UI tests — EssayCards — Sprint12_FSRSAndUXOverhaul (fix iteration 1)
 *
 * Covers the test-spec scenario "Every pre-existing button/action remains
 * reachable after consolidation" (not [UI]-tagged in 10_test_spec.md, but
 * backed by the self-contained `10_architecture.json §button_nav_inventory`
 * block). That block lists every pre-sprint action and its post-sprint
 * location; this spec walks the full list and confirms each one is still
 * reachable in the live UI, via the new ActionMenu primary+dropdown pattern
 * where consolidated.
 *
 * Three existing specs (essay_action_menu, category_collapse,
 * section_progress_overview — the Sprint12 learning_level_badge spec was retired in Sprint14) each already cover their own narrower [UI] scenario
 * and only incidentally touch a subset of this inventory. This spec is the
 * first to walk the whole list — overview page-level actions, essay-header
 * actions, section-end actions, and the regrouped main nav.
 *
 * Tests run against http://atlas-shell via the shared atlas-playwright
 * container, using the live production database — no test fixtures are
 * loaded — same convention as the other three Sprint12 UI specs.
 */

import { test, expect } from '@playwright/test';

test('overview page exposes every pre-existing page-level and category-level action', async ({ page }) => {
  await page.goto('/essaycards');
  await expect(page.getByRole('heading', { name: 'Essays', level: 2 })).toBeVisible();

  // Page-level actions: Images / Import exam results / Import exploration live
  // in the header's "More" menu (the "Due for review" button was removed —
  // it is a primary item of the Shell nav on every viewport).
  const main = page.getByRole('main');
  await main.getByRole('button', { name: 'More actions' }).click();
  await expect(main.getByRole('menuitem', { name: 'Images', exact: true })).toBeVisible();
  await expect(main.getByRole('menuitem', { name: 'Import exam results', exact: true })).toBeVisible();
  await expect(main.getByRole('menuitem', { name: 'Import exploration', exact: true })).toBeVisible();

  // Per-category Study button — only rendered for a named topic category
  // with at least one essay carrying progress (tot > 0). Assert it exists
  // for at least one category heading, without pinning to a specific name.
  const categoryStudyButtons = main.getByRole('button', { name: 'Study', exact: true });
  expect(await categoryStudyButtons.count()).toBeGreaterThan(0);
});

test('essay header action menu exposes every pre-existing essay-level action', async ({ page }) => {
  await page.goto('/essaycards');
  const firstRow = page.locator('div[style*="cursor: pointer"]').first();
  await firstRow.click();
  await expect(page).toHaveURL(/\/essaycards\/essays\//);

  // "← All essays" — standalone, never folded into the menu.
  await expect(page.getByRole('button', { name: '← All essays' })).toBeVisible();

  // The essay header's ActionMenu is the first "More actions" trigger in
  // document order (section ActionMenus come after it).
  const essayMoreTrigger = page.getByRole('button', { name: 'More actions' }).first();
  await expect(essayMoreTrigger).toBeVisible();

  // Primary is "Study" (essay has cards) or "Question overview" (fallback
  // for a cardless essay) — exactly one of the two, per internal_flow step 9.
  const primaryStudy = page.getByRole('button', { name: 'Study', exact: true }).first();
  const primaryQuestions = page.getByRole('button', { name: 'Question overview', exact: true });
  const hasPrimaryStudy = await primaryStudy.count() > 0 && await primaryStudy.isVisible();

  await essayMoreTrigger.click();
  const menu = page.getByRole('menu').first();
  await expect(menu).toBeVisible();

  // "Question overview" is reachable either as the primary action or as a
  // secondary menu item — never both, never neither.
  if (!hasPrimaryStudy) {
    await expect(primaryQuestions).toBeVisible();
  } else {
    await expect(menu.getByRole('menuitem', { name: 'Question overview', exact: true })).toBeVisible();
  }

  // Guided / Unguided oral exam — always present as menu items (gated on
  // status === 'complete' via `disabled`, not hidden — "reachable" per the
  // inventory means present in the menu, same gate as pre-sprint).
  await expect(menu.getByRole('menuitem', { name: 'Guided oral exam', exact: true })).toBeVisible();
  await expect(menu.getByRole('menuitem', { name: 'Unguided oral exam', exact: true })).toBeVisible();

  // Export essay / Import essay → — same toggle-to-Import pattern as before.
  await expect(menu.getByRole('menuitem', { name: /^(Export essay|Import essay →)$/ })).toBeVisible();

  // + New nugget — gated on sections.length > 0; assert only when present,
  // since not every essay on a live overview is guaranteed to have sections.
  const newNuggetItem = menu.getByRole('menuitem', { name: '+ New nugget', exact: true });
  if (await newNuggetItem.count() > 0) {
    await expect(newNuggetItem).toBeVisible();
  }

  await page.keyboard.press('Escape');
  await expect(menu).toBeHidden();
});

test('section-end action menu and examination history remain reachable after consolidation', async ({ page }) => {
  await page.goto('/essaycards');
  const firstRow = page.locator('div[style*="cursor: pointer"]').first();
  await firstRow.click();
  await expect(page).toHaveURL(/\/essaycards\/essays\//);
  // Sprint14: wait for the reader to finish loading before counting (the overview/reader
  // now make additional parallel fetches, so an immediate count() can race the skeleton).
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();

  // Section-end ActionMenus come after the essay header's in document
  // order — if this essay has no sections, fall back to the first essay
  // that does (walking the overview list) so the scenario is still exercised.
  // The section ActionMenu has no primary button any more (the old "Review this
  // section" button was removed); it is just a "More actions" trigger. An essay
  // with sections therefore shows >= 2 triggers (header + first section).
  const moreTriggers = page.getByRole('button', { name: 'More actions' });
  if (await moreTriggers.count() < 2) {
    await page.goto('/essaycards');
    const rows = page.locator('div[style*="cursor: pointer"]');
    await expect(rows.first()).toBeVisible();
    const rowCount = await rows.count();
    for (let i = 1; i < rowCount && (await moreTriggers.count()) < 2; i++) {
      await rows.nth(i).click();
      await expect(page).toHaveURL(/\/essaycards\/essays\//);
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
      if (await moreTriggers.count() < 2) await page.goBack();
    }
  }
  expect(await moreTriggers.count()).toBeGreaterThanOrEqual(2);

  // The first section's "More actions" trigger is the SECOND one in
  // document order (index 1) — the essay header's is index 0.
  const sectionMoreTrigger = page.getByRole('button', { name: 'More actions' }).nth(1);
  await expect(sectionMoreTrigger).toBeVisible();
  await sectionMoreTrigger.click();

  const sectionMenu = page.getByRole('menu').first();
  await expect(sectionMenu).toBeVisible();
  // Sprint14: the section menu also offers the two section-scope oral exams.
  await expect(sectionMenu.getByRole('menuitem', { name: 'Guided oral (section)', exact: true })).toBeVisible();
  await expect(sectionMenu.getByRole('menuitem', { name: 'Unguided oral (section)', exact: true })).toBeVisible();
  await expect(sectionMenu.getByRole('menuitem', { name: /^(Export section|Import section →)$/ })).toBeVisible();
  await expect(sectionMenu.getByRole('menuitem', { name: /^(Insert section after|Import insertion →)$/ })).toBeVisible();

  await expect(sectionMenu.getByRole('menuitem', { name: /^(Improve section|Import improved section →)$/ })).toBeVisible();
  // Examination history is a section-menu item (toggle) — it opens the history panel below the section.
  const historyItem = sectionMenu.getByRole('menuitem', { name: 'Examination history', exact: true });
  await expect(historyItem).toBeVisible();
  await historyItem.click();
  await expect(page.getByText(/^Examination history/).first()).toBeVisible();
});

test('desktop nav reflects the Sprint12 regrouping — Experiment removed, Add / Update Essay retained', async ({ page }) => {
  await page.goto('/essaycards');

  const sidebar = page.getByRole('navigation', { name: 'Application navigation' });
  await expect(sidebar.getByRole('button', { name: 'Essays', exact: true })).toBeVisible();
  await expect(sidebar.getByRole('button', { name: 'Due for review', exact: true })).toBeVisible();
  await expect(sidebar.getByRole('button', { name: 'Add / Update Essay', exact: true })).toBeVisible();
  await expect(sidebar.getByRole('button', { name: 'Stats', exact: true })).toBeVisible();

  // The Experiment nav entry (and its dashboard) is retired in full.
  await expect(sidebar.getByRole('button', { name: 'Experiment', exact: true })).toHaveCount(0);
});
