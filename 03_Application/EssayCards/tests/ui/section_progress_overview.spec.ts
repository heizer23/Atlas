/**
 * UI tests — EssayCards — Sprint14_SectionProgressionAndRevalidation
 *
 * Covers the [UI] scenarios of 10_test_spec.md for the overview, reader,
 * oral import and question overview:
 *   - Sprint16: markers = guided-level fill + recall ring; no flashcard progress; legend

 *   - Revalidate entry appears only with pending cards
 *   - Locked section is visibly locked in the reader
 *   - Section and essay oral actions are distinct
 *   - Import result shows recall rating; Oral Recall queue is separate from flashcards
 *   - Locked cards are marked in the question overview
 *
 * Tests run against http://atlas-shell via the shared atlas-playwright
 * container. The live database has no fixture world, so the API responses these
 * scenarios depend on are stubbed with page.route (the UI under test is the
 * real, deployed bundle).
 */

import { test, expect, type Page, type Route } from '@playwright/test';

const ESSAY_YELLOW = 'ea00000d-0000-0000-0000-00000000000d';
const ESSAY_LOCKED = 'ea00000c-0000-0000-0000-00000000000c';
const SEC_Y1 = 'ec000018-0000-0000-0000-000000000018';
const SEC_Y2 = 'ec000019-0000-0000-0000-000000000019';
const SEC_L1 = 'ec000017-0000-0000-0000-000000000017';

const dataset = (rows: unknown[]) => ({ meta: { object_type: 'x', total: rows.length, page: 1, page_size: rows.length }, schema: [], rows });
const json = (route: Route, body: unknown) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });

function essayRow(over: Record<string, unknown>) {
  return {
    id: ESSAY_YELLOW, title: 'Yellow essay', slug: 'fix-essay-yellow', category: 'Philosophy', sort_index: 1,
    status: 'complete', progress_total: 2, progress_established: 1, open_count: 0,
    created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
    essay_state: 'yellow', essay_next_step: 'cards_learned', essay_guided_passed: true, essay_unguided_passed: false,
    essay_guided_latest_score: 5, essay_unguided_latest_score: null, essay_guided_passed_at: '2026-01-01T00:00:00Z',
    essay_unguided_passed_at: null, cards_learned_count: 0, sections_total: 2, sections_unguided_passed_count: 0,
    revalidation_pending_count: 0,
    essay_recall_status: 'not_established', essay_recall_next_due_at: null, recall_due_count: 0, ...over,
  };
}

function sectionRow(over: Record<string, unknown>) {
  return {
    section_id: SEC_Y1, essay_id: ESSAY_YELLOW, heading: 'Yellow 1', anchor_slug: 'fix-yellow-1', order_index: 0,
    state: 'yellow', next_step: 'guided_next', next_guided_level: 2, guided_level: 1,
    guided_passed: true, unguided_passed: false, unguided_suggested: false,
    recall_status: 'not_established', recall_next_due_at: null, recall_last_reviewed_at: null, recall_last_rating: null,
    guided_pass_source: 'exam', guided_latest_score: 5, unguided_latest_score: null, guided_passed_at: null,
    unguided_passed_at: null, cards_total: 2, cards_established: 1, is_locked: false, ...over,
  };
}

async function stubOverview(page: Page, essays: unknown[], sections: unknown[]) {
  await page.route('**/api/essaycards/essays', r => json(r, dataset(essays)));
  await page.route('**/api/essaycards/progress/sections', r => json(r, dataset(sections)));
}

test('[UI] overview shows understanding/recall markers and no flashcard progress', async ({ page }) => {
  await stubOverview(
    page,
    [
      essayRow({ essay_recall_status: 'current', essay_recall_next_due_at: '2030-01-01T00:00:00Z', recall_due_count: 1 }),
      essayRow({ id: ESSAY_LOCKED, title: 'Locked essay', slug: 'fix-essay-locked', essay_state: 'grey',
        essay_next_step: 'guided_essay_oral', progress_total: 2, progress_established: 0, sections_total: 1 }),
    ],
    [
      sectionRow({}),
      sectionRow({ section_id: SEC_Y2, heading: 'Yellow 2', order_index: 1, cards_total: 0, guided_level: 6,
        next_step: 'recall_due', recall_status: 'due', recall_next_due_at: '2026-01-01T00:00:00Z' }),
      sectionRow({ section_id: SEC_L1, essay_id: ESSAY_LOCKED, heading: 'Locked 1', state: 'grey',
        next_step: 'guided_oral', guided_level: 0, guided_passed: false, is_locked: true }),
    ],
  );
  await page.goto('/essaycards');
  await expect(page.getByRole('heading', { name: 'Essays', level: 2 })).toBeVisible();

  // Only the essay with an established recall gets an essay-level (ring-only) marker.
  await expect(page.getByRole('button', { name: /^Whole-essay recall/ })).toHaveCount(1);
  await expect(page.getByRole('button', { name: /^Section: / })).toHaveCount(3);

  const rows = page.locator('div[style*="cursor: pointer"]');
  await expect(rows).toHaveCount(2);
  const text = (await rows.allTextContents()).join(' ');
  expect(text).not.toMatch(/planned|complete/i);
  expect(text).not.toMatch(/\d\s*\/\s*\d/);   // no "x / y" progress, no numbers in the dots
  expect(text).not.toMatch(/Open:/);

  // Category summary: recall due only; flashcard progress is gone.
  await expect(page.getByText(/1 recall due/)).toBeVisible();
  await expect(page.getByText(/established · \d+ open/)).toHaveCount(0);
});

test('[UI] fill and ring are independent: ring style follows recall status', async ({ page }) => {
  await stubOverview(page, [essayRow({})], [
    sectionRow({ section_id: 'a', heading: 'A', order_index: 0, guided_level: 6, recall_status: 'not_established' }),
    sectionRow({ section_id: 'b', heading: 'B', order_index: 1, guided_level: 6, recall_status: 'current',
      recall_next_due_at: '2030-01-01T00:00:00Z' }),
    sectionRow({ section_id: 'c', heading: 'C', order_index: 2, guided_level: 6, recall_status: 'due',
      recall_next_due_at: '2026-01-01T00:00:00Z' }),
  ]);
  await page.goto('/essaycards');

  const ring = (name: string) => page.getByRole('button', { name: new RegExp(`^Section: ${name}\\.`) }).locator('svg circle');
  await expect(ring('A')).toHaveCount(1);                       // dot only: no ring
  await expect(ring('B')).toHaveCount(2);                       // dot + solid ring
  await expect(ring('B').nth(1)).not.toHaveAttribute('stroke-dasharray', /.+/);
  await expect(ring('C')).toHaveCount(2);                       // dot + dashed ring
  await expect(ring('C').nth(1)).toHaveAttribute('stroke-dasharray', /.+/);
  // same fill (Level 6) for all three
  const fills = await Promise.all(['A', 'B', 'C'].map(n => ring(n).first().getAttribute('fill')));
  expect(new Set(fills).size).toBe(1);
});

test('[UI] dot caption names level, recall status and the next step', async ({ page }) => {
  await stubOverview(page, [essayRow({})], [sectionRow({}), sectionRow({ section_id: SEC_Y2, heading: 'Yellow 2', order_index: 1 })]);
  await page.goto('/essaycards');

  const dot = page.getByRole('button', { name: /^Section: Yellow 1/ }).first();
  const label = await dot.getAttribute('aria-label');
  expect(label).toContain('Guided Level 1 of 6');
  expect(label).toContain('Recall not established');
  await expect(dot).toHaveAttribute('title', /Yellow 1/);

  await dot.click();                                // tap/click opens the caption (not hover-only)
  const tip = page.getByRole('status');
  await expect(tip).toContainText('Yellow 1');
  await expect(tip).toContainText('Orientation');
  await expect(tip).toContainText('Next: Next guided level (Level 2)');
  await expect(page).toHaveURL(/\/essaycards$/);   // the click did not navigate the essay row
});

test('[UI] legend explains fill and ring', async ({ page }) => {
  await stubOverview(page, [essayRow({})], [sectionRow({})]);
  await page.goto('/essaycards');

  const legend = page.locator('details', { hasText: 'Legend' });
  await expect(legend).toBeVisible();
  await expect(page.getByText('solid: current')).toBeHidden();   // collapsed by default

  await legend.locator('summary').click();
  for (const t of ['understanding (guided level)', 'oral recall', 'none: not established', 'solid: current', 'dashed: due']) {
    await expect(legend.getByText(t, { exact: false }).first()).toBeVisible();
  }
});

test('[UI] Revalidate entry appears only with pending cards', async ({ page }) => {
  await stubOverview(
    page,
    [essayRow({ revalidation_pending_count: 3 }), essayRow({ id: ESSAY_LOCKED, title: 'Other essay', slug: 'other' })],
    [sectionRow({})],
  );
  await page.route('**/api/essaycards/flashcards/revalidation**', r => json(r, dataset([])));
  await page.goto('/essaycards');

  await expect(page.getByRole('button', { name: 'Revalidate (3)' })).toHaveCount(1);
  await expect(page.getByRole('button', { name: /^Revalidate/ })).toHaveCount(1);
  await page.getByRole('button', { name: 'Revalidate (3)' }).click();
  await expect(page).toHaveURL(new RegExp(`/essaycards/review\\?revalidate=1&essay_id=${ESSAY_YELLOW}`));
});

async function stubReader(page: Page, onPackage?: (url: string) => void) {
  const section = (id: string, heading: string, anchor: string, order: number) => ({
    id, heading, anchor_slug: anchor, order_index: order, body_markdown: `${heading} body.`, nuggets: [],
    created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
  });
  await page.route(`**/api/essaycards/essays/${ESSAY_LOCKED}`, r => json(r, dataset([{
    ...essayRow({ id: ESSAY_LOCKED, title: 'Locked essay', slug: 'fix-essay-locked', essay_state: 'grey', progress_total: 2 }),
    main_spine_markdown: '', main_spine_nuggets: [], sections: [section(SEC_L1, 'Locked 1', 'fix-locked-1', 0)],
  }])));
  await page.route(`**/api/essaycards/progress/sections?essay_id=${ESSAY_LOCKED}`, r => json(r, dataset([
    sectionRow({ section_id: SEC_L1, essay_id: ESSAY_LOCKED, heading: 'Locked 1', state: 'grey', next_step: 'guided_oral',
      guided_passed: false, is_locked: true }),
  ])));
  await page.route(`**/api/essaycards/essays/${ESSAY_LOCKED}/sentences`, r => json(r, dataset([])));
  await page.route(`**/api/essaycards/essays/${ESSAY_LOCKED}/sentence-feedback`, r => json(r, dataset([])));
  await page.route(`**/api/essaycards/essays/${ESSAY_LOCKED}/examination-package**`, r => {
    onPackage?.(r.request().url());
    return json(r, { essay_id: ESSAY_LOCKED, scope: 'section', sections: [] });
  });
}

test('[UI] locked section is visibly locked in the reader', async ({ page }) => {
  await stubReader(page);
  await page.goto(`/essaycards/essays/${ESSAY_LOCKED}`);
  await expect(page.getByRole('heading', { name: /Locked 1/ })).toBeVisible();

  await expect(page.getByText(/Flashcards locked — pass the guided oral for this section/)).toBeVisible();

  // A guided-oral action is offered for that section.
  await page.getByRole('button', { name: 'More actions' }).nth(1).click();
  await expect(page.getByRole('menuitem', { name: /^Guided learning — Level [1-6]$/ })).toBeVisible();
});

test('[UI] section and essay oral actions are distinct', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  const urls: string[] = [];
  await stubReader(page, u => urls.push(u));
  await page.goto(`/essaycards/essays/${ESSAY_LOCKED}`);
  await expect(page.getByRole('heading', { name: /Locked 1/ })).toBeVisible();

  // Essay menu: whole-essay orals (no section orals here).
  await page.getByRole('button', { name: 'More actions' }).nth(0).click();
  const essayMenu = page.getByRole('menu').first();
  await expect(essayMenu.getByRole('menuitem', { name: 'Guided oral exam (essay)', exact: true })).toBeVisible();
  await expect(essayMenu.getByRole('menuitem', { name: 'Oral recall (whole essay)', exact: true })).toBeVisible();
  await expect(essayMenu.getByRole('menuitem', { name: /\(section\)/ })).toHaveCount(0);
  await essayMenu.getByRole('menuitem', { name: 'Guided oral exam (essay)', exact: true }).click();
  await expect.poll(() => urls.length).toBe(1);
  expect(urls[0]).toContain('scope=essay');
  expect(urls[0]).not.toContain('section_id');

  // Section menu: section orals.
  await page.getByRole('button', { name: 'More actions' }).nth(1).click();
  const sectionMenu = page.getByRole('menu').first();
  await expect(sectionMenu.getByRole('menuitem', { name: /^Guided learning — Level [1-6]$/ })).toBeVisible();
  await expect(sectionMenu.getByRole('menuitem', { name: 'Oral recall (section)', exact: true })).toBeVisible();
  await sectionMenu.getByRole('menuitem', { name: 'Oral recall (section)', exact: true }).click();
  await expect.poll(() => urls.length).toBe(2);
  expect(urls[1]).toContain('scope=section');
  expect(urls[1]).toContain(`section_id=${SEC_L1}`);
  expect(urls[1]).toContain('exam_type=unguided');
});

test('[UI] import result shows the recall rating and next review date', async ({ page }) => {
  await page.route('**/api/essaycards/examinations/import', r => json(r, {
    imported: 1,
    results: [{
      id: 'x1', scope: 'section', essay_id: ESSAY_YELLOW, section_id: SEC_Y1, examined_at: '2026-09-02T10:00:00+00:00',
      exam_type: 'unguided', rating: 'hard', next_due_at: '2030-03-04T10:00:00+00:00', recall_status: 'current',
      score: null, passed: null, score_percent: null,
      effects: [{ effect: 'recall_established', scope: 'section', section_id: SEC_Y1 }],
    }],
    revalidation: [],
  }));
  await page.goto('/essaycards/examinations/import');
  await page.locator('textarea').fill('{"results": []}');
  await page.getByRole('button', { name: 'Submit' }).click();

  await expect(page.getByText('Import succeeded')).toBeVisible();
  await expect(page.getByText('hard', { exact: true })).toBeVisible();
  await expect(page.getByText(/next recall/)).toBeVisible();
  await expect(page.getByText('Oral recall established')).toBeVisible();
  await expect(page.getByRole('alert')).toHaveCount(0);
});

test('[UI] Oral Recall queue is separate from the flashcard review and lists only due recall', async ({ page }) => {
  await page.route('**/api/essaycards/recall/due', r => json(r, dataset([{
    id: 'r1', scope: 'section', essay_id: ESSAY_YELLOW, section_id: SEC_Y1, essay_title: 'Yellow essay', category: 'Philosophy',
    section_heading: 'Yellow 1', anchor_slug: 'fix-yellow-1', last_reviewed_at: '2026-01-01T00:00:00Z',
    next_due_at: '2026-01-05T00:00:00Z', last_rating: 'good', review_count: 2, lapse_count: 0,
  }, {
    id: 'r2', scope: 'essay', essay_id: ESSAY_YELLOW, section_id: null, essay_title: 'Yellow essay', category: 'Philosophy',
    section_heading: null, anchor_slug: null, last_reviewed_at: '2026-01-01T00:00:00Z',
    next_due_at: '2026-01-05T00:00:00Z', last_rating: 'again', review_count: 3, lapse_count: 1,
  }])));
  let flashcardCalls = 0;
  await page.route('**/api/essaycards/flashcards/**', r => { flashcardCalls++; return json(r, dataset([])); });
  await page.goto('/essaycards/recall');

  await expect(page.getByRole('heading', { name: 'Oral Recall', level: 2 })).toBeVisible();
  await expect(page.getByText('2 due')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Start recall' })).toHaveCount(2);
  await expect(page.getByText('Whole essay')).toBeVisible();
  expect(flashcardCalls).toBe(0);                      // never queries or mixes flashcards
});

test('[UI] locked cards are marked in the question overview', async ({ page }) => {
  const q = (key: string, locked: boolean, state: string) => ({
    id: `id-${key}`, card_key: key, question: `Question ${key}`, answer: 'a', level: 1, section_id: SEC_L1,
    section_anchor_slug: 'fix-locked-1', section_heading: 'Locked 1', section_order_index: 0, section_nuggets: [],
    nugget_id: null, is_locked: locked, card_state: state, needs_revalidation: false,
  });
  await page.route(`**/api/essaycards/essays/${ESSAY_LOCKED}`, r => json(r, dataset([{
    ...essayRow({ id: ESSAY_LOCKED, title: 'Locked essay' }), main_spine_markdown: '', main_spine_nuggets: [],
    sections: [{ id: SEC_L1, heading: 'Locked 1', anchor_slug: 'fix-locked-1', order_index: 0, body_markdown: 'b', nuggets: [] }],
  }])));
  await page.route(`**/api/essaycards/essays/${ESSAY_LOCKED}/questions`, r =>
    json(r, dataset([q('locked-card', true, 'locked'), q('open-card', false, 'established')])));
  await page.route('**/api/essaycards/nuggets', r => json(r, dataset([])));
  await page.goto(`/essaycards/essays/${ESSAY_LOCKED}/questions`);

  const states = page.getByTestId('card-state');
  await expect(states).toHaveCount(2);
  await expect(states.nth(0)).toContainText('Locked');
  await expect(states.nth(0)).not.toContainText('State:');
  await expect(states.nth(1)).toContainText('State: established');
});
