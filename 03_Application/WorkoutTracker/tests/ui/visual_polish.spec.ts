/**
 * UI tests — WorkoutTracker — visual polish validation at common Android phone widths.
 *
 * The Workout API reads are mocked with fixtures (page.route), so this spec is deterministic,
 * never touches the real database and does not care whether a workout is active. Any write
 * (POST/PATCH/DELETE) to /api/workout fails the test.
 *
 * Fixture covers: very long exercise name, exercise with no history, 1-set and 5-set
 * exercises, logged and unlogged rows, varying weights, comments.
 * Checks: no horizontal overflow, mini charts same width and right-aligned, chip column
 * aligned, suggestion ("last N") shown as text while inputs stay empty.
 * Screenshots go to /tmp/wt-shots inside the container.
 */

import { test, expect, type Page } from '@playwright/test';

const SHOTS = '/tmp/wt-shots';
const LONG_NAME = 'Extremely long exercise name that must wrap gracefully without breaking the row layout';
const SID = '99999999-9999-9999-9999-999999999999';

type Sets = (number | null)[];
const occ = (id: number, date: string, w: number | null, s: Sets, comment: string | null = null) => ({
  id: String(id), workout_date: date, weight_kg: w, comment, split: 'Pull',
  set1_reps: s[0] ?? null, set2_reps: s[1] ?? null, set3_reps: s[2] ?? null, set4_reps: s[3] ?? null, set5_reps: s[4] ?? null,
});
const day = (i: number) => `2026-${String(3 + Math.floor(i / 9)).padStart(2, '0')}-${String(1 + (i % 9) * 3).padStart(2, '0')}`;

const HISTORY: Record<string, ReturnType<typeof occ>[]> = {
  'straight-arm leg raise': Array.from({ length: 16 }, (_, i) => occ(100 + i, day(i), null, [14 + (i >> 1), 14 + (i >> 1), 13 + (i >> 2), 12 + (i >> 2)], i === 15 ? 'Core felt strong' : null)),
  'pull up': Array.from({ length: 12 }, (_, i) => occ(200 + i, day(i), null, [5 + (i % 4), 5, 4 + (i % 3)], i === 11 ? 'Grip slipped on set 3' : null)),
  squats: [occ(300, '2026-04-02', 40, [10, 10, 9]), occ(301, '2026-04-09', 40, [10, 10, 10, 9], 'Knees fine'), occ(302, '2026-04-16', 45, [8, 8, 8])],
  'dumbbell row': Array.from({ length: 14 }, (_, i) => occ(400 + i, day(i), i < 8 ? 30 : i < 12 ? 32.5 : 35, [10, 10, 9, 9, i % 2 ? 8 : 9], i === 13 ? 'Shoulder a bit unstable on the last set.' : null)),
};

const ex = (id: string, exercise: string, status: 'done' | 'planned', weight: number | null, s: Sets, delta: number | null, comment: string | null = null) => ({
  id, exercise, status, weight_kg: weight, workout_date: '2026-10-28', split: 'Pull', comment,
  set1_reps: s[0] ?? null, set2_reps: s[1] ?? null, set3_reps: s[2] ?? null, set4_reps: s[3] ?? null, set5_reps: s[4] ?? null,
  total_reps: s.reduce<number>((a, v) => a + (v ?? 0), 0), delta,
});
const EXERCISES = [
  ex('1', 'Straight-arm leg raise', 'done', null, [20, 20, 20, 17], 3),
  ex('2', 'Pull up', 'done', null, [8, 7, 6], -2),
  ex('3', LONG_NAME, 'planned', 20, [], null),
  ex('4', 'Squats', 'planned', 40, [], null),
  ex('5', 'Dumbbell Row', 'done', 35, [10, 10, 10, 10, 9], 0),
  ex('6', 'Zz single set', 'done', null, [10], null),
];

const ds = (rows: unknown[]) => ({ meta: { object_type: 'x', label: 'x', total: rows.length, page: 1, page_size: rows.length || 1 }, schema: [], rows });

async function mockApi(page: Page) {
  await page.route(/\/api\/workout\//, async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    if (req.method() !== 'GET') {
      throw new Error(`unexpected write in visual spec: ${req.method()} ${url.pathname}`);
    }
    const json = (body: unknown) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    const p = url.pathname;
    if (p.endsWith('/sessions/active')) return json(ds([{ id: SID, split: 'Pull', workout_date: '2026-10-28', started_at: '2026-10-28 18:00' }]));
    if (p.endsWith(`/sessions/${SID}/exercises`)) return json(ds(EXERCISES));
    if (p.endsWith('/exercises/history')) {
      const name = (url.searchParams.get('name') ?? '').toLowerCase();
      return json(ds(HISTORY[name] ?? []));
    }
    if (p.endsWith('/exercises/names')) return json(ds(['Squats', 'Pull up', 'Straight-arm leg raise'].map((e) => ({ id: e, exercise: e, use_count: 5 }))));
    return route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ error: { code: 'NOT_FOUND', message: 'not mocked', request_id: 'mock' } }) });
  });
}

async function noHorizontalOverflow(page: Page, label: string) {
  const o = await page.evaluate(() => {
    const c = document.querySelector('.shell-content') as HTMLElement | null;
    return { doc: document.documentElement.scrollWidth - window.innerWidth, content: c ? c.scrollWidth - c.clientWidth : 0 };
  });
  expect(o.doc, `${label}: document overflow`).toBeLessThanOrEqual(0);
  expect(o.content, `${label}: content overflow`).toBeLessThanOrEqual(0);
}

for (const width of [360, 393, 412]) {
  test.describe(`width ${width}`, () => {
    test.use({ viewport: { width, height: 800 }, hasTouch: true, isMobile: true });

    test(`overview + exercise screens at ${width}px`, async ({ page }) => {
      await mockApi(page);
      await page.goto('/workout');
      await expect(page.getByRole('button', { name: 'Finish Workout' })).toBeVisible();
      await page.waitForTimeout(700); // charts load

      // ── overview invariants
      await noHorizontalOverflow(page, 'overview');
      const charts = page.locator('li [role="img"]');
      expect(await charts.count()).toBe(EXERCISES.length);
      const rights: number[] = [], widths: number[] = [];
      for (let i = 0; i < EXERCISES.length; i++) {
        const b = (await charts.nth(i).boundingBox())!;
        rights.push(Math.round(b.x + b.width));
        widths.push(Math.round(b.width));
      }
      expect(new Set(rights).size, `chart right edges ${rights}`).toBe(1);
      expect(new Set(widths).size, `chart widths ${widths}`).toBe(1);
      const chips = page.locator('li > button > span:nth-child(2)');
      const lefts = new Set<number>();
      for (let i = 0; i < (await chips.count()); i++) lefts.add(Math.round((await chips.nth(i).boundingBox())!.x));
      expect(lefts.size, 'chip column x positions').toBe(1);
      const longRow = await page.getByRole('button', { name: new RegExp(LONG_NAME.slice(0, 20)) }).boundingBox();
      expect(longRow!.x + longRow!.width).toBeLessThanOrEqual(width);
      await page.screenshot({ path: `${SHOTS}/vp${width}_1_overview.png` });

      // ── 5-set logged exercise with history + comment
      await page.getByRole('button', { name: /^Dumbbell Row/ }).click();
      await expect(page.getByLabel('Set 5 reps')).toHaveValue('9');
      await noHorizontalOverflow(page, 'exercise 5 sets');
      await page.screenshot({ path: `${SHOTS}/vp${width}_2_exercise_logged_5sets.png` });
      await page.getByRole('button', { name: 'Back without saving' }).click();

      // ── very long name, no history, nothing entered
      await page.getByRole('button', { name: new RegExp(LONG_NAME.slice(0, 20)) }).click();
      await expect(page.getByRole('button', { name: 'Save' })).toBeVisible();
      await noHorizontalOverflow(page, 'exercise long name');
      // long title wraps (multi-line, nothing clipped) instead of being cut off
      const title = page.getByLabel('Exercise name');
      const th = await title.evaluate((el) => ({ h: (el as HTMLElement).clientHeight, sh: (el as HTMLElement).scrollHeight }));
      expect(th.h, 'title is multi-line').toBeGreaterThan(40);
      expect(th.sh, 'title not clipped').toBeLessThanOrEqual(th.h + 1);
      await page.screenshot({ path: `${SHOTS}/vp${width}_3_exercise_long_name_no_history.png` });
      await page.getByRole('button', { name: 'Back without saving' }).click();

      // ── unlogged with history: suggestions are text, inputs empty; entering a value changes the row state
      await page.getByRole('button', { name: /^Squats/ }).click();
      await expect(page.getByLabel('Set 1 reps')).toHaveValue('');
      await expect(page.getByText('last 8').first()).toBeVisible();
      // carried-over weight is marked as a suggestion until touched
      await expect(page.getByText('from last session')).toBeVisible();
      await noHorizontalOverflow(page, 'exercise suggestions');
      await page.screenshot({ path: `${SHOTS}/vp${width}_4_exercise_suggestions.png` });
      await page.getByLabel('Weight (kg)').focus();
      await expect(page.getByText('from last session')).toHaveCount(0);
      await page.getByLabel('Set 1 reps').fill('11');
      await expect(page.getByLabel('Set 1 reps')).toHaveValue('11');
      await page.screenshot({ path: `${SHOTS}/vp${width}_5_exercise_entered.png` });
      await page.getByRole('button', { name: 'Back without saving' }).click();

      // ── Add Exercise: tappable name suggestions (replaces the old datalist)
      await page.getByRole('button', { name: '+ Add Exercise' }).click();
      await page.getByLabel('Exercise name').focus();
      const sugg = page.getByRole('list', { name: 'Exercise suggestions' });
      await expect(sugg).toBeVisible();
      await page.screenshot({ path: `${SHOTS}/vp${width}_6_add_exercise_suggestions.png` });
      await sugg.getByRole('button', { name: 'Pull up' }).click();
      await expect(page.getByLabel('Exercise name')).toHaveValue('Pull up');
      await expect(sugg).toHaveCount(0);
      await page.getByRole('button', { name: 'Back without saving' }).click();

      await page.evaluate(() => { try { Object.keys(localStorage).filter((k) => k.startsWith('workout_')).forEach((k) => localStorage.removeItem(k)); } catch { /* ignore */ } });
    });
  });
}
