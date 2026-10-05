/**
 * UI tests — EssayCards — Sprint14_SectionProgressionAndRevalidation
 *
 * Covers the [UI] scenario "Revalidation session shows remaining count and
 * completes". The live database has no flagged cards, so the revalidation queue
 * and review endpoint are stubbed with page.route; the UI is the real bundle.
 */

import { test, expect, type Route } from '@playwright/test';

const ESSAY = 'ea000012-0000-0000-0000-000000000012';
const dataset = (rows: unknown[]) => ({ meta: { object_type: 'flashcard', total: rows.length, page: 1, page_size: rows.length }, schema: [], rows });
const json = (route: Route, body: unknown) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });

const card = (n: number) => ({
  id: `c${n}`, flashcard_id: `c${n}`, question: `Revalidation question ${n}`, answer: `answer ${n}`, essay_id: ESSAY,
  section_id: 's1', anchor_slug: 'fix-violet-1', next_due_at: '2027-01-01T00:00:00+00:00', is_new: false, is_recent: false,
  scheduled_interval_seconds: 3456000, nugget_id: null,
});

test('[UI] revalidation session shows remaining count and completes', async ({ page }) => {
  let queue = [card(1), card(2), card(3)];
  const grades: string[] = [];
  let statsCalls = 0;

  await page.route('**/api/essaycards/flashcards/revalidation**', r => json(r, dataset(queue)));
  await page.route('**/api/essaycards/flashcards/stats**', r => { statsCalls++; return json(r, dataset([])); });
  await page.route('**/api/essaycards/review-stats/today**', r => { statsCalls++; return json(r, dataset([])); });
  await page.route('**/api/essaycards/flashcards/*/review', async r => {
    const id = r.request().url().split('/flashcards/')[1].split('/')[0];
    const grade = JSON.parse(r.request().postData() ?? '{}').grade;
    grades.push(grade);
    queue = queue.filter(c => c.flashcard_id !== id);
    await json(r, {
      flashcard_id: id, last_reviewed_at: '2026-09-01T00:00:00+00:00', next_due_at: '2027-01-01T00:00:00+00:00',
      revalidation_outcome: grade === 'again' ? 'failed' : 'preserved',
    });
  });

  await page.goto(`/essaycards/review?revalidate=1&essay_id=${ESSAY}`);

  // Labelled Revalidation, with a remaining count, and no interval forecast.
  await expect(page.getByText('Revalidation', { exact: true })).toBeVisible();
  await expect(page.getByText('3 remaining')).toBeVisible();
  expect(statsCalls).toBe(0);

  await page.getByRole('button', { name: 'Flip' }).click();
  // Only the two revalidation buttons — no four-grade row, no Hard.
  await expect(page.getByRole('button', { name: 'Correct', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Incorrect', exact: true })).toBeVisible();
  for (const g of ['Again', 'Hard', 'Good', 'Easy']) {
    await expect(page.getByRole('button', { name: g, exact: true })).toHaveCount(0);
  }

  await page.getByRole('button', { name: 'Correct', exact: true }).click();
  await expect(page.getByText('2 remaining')).toBeVisible();
  await page.getByRole('button', { name: 'Flip' }).click();
  await page.getByRole('button', { name: 'Correct', exact: true }).click();
  await expect(page.getByText('1 remaining')).toBeVisible();
  await page.getByRole('button', { name: 'Flip' }).click();
  await page.getByRole('button', { name: 'Incorrect', exact: true }).click();

  await expect(page.getByText('Revalidation complete')).toBeVisible();
  expect(grades).toEqual(['good', 'good', 'again']);   // Correct -> good, Incorrect -> again
  await page.getByRole('button', { name: 'Back to all essays' }).click();
  await expect(page).toHaveURL(/\/essaycards$/);
});
