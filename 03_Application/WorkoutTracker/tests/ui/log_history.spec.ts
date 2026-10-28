/**
 * UI tests — WorkoutTracker — P1: Log, Session detail, Exercise history.
 *
 * The Workout API is mocked from fixtures (page.route): deterministic, nothing touches the real
 * database, independent of any active workout. Every write request is recorded, so "browsing
 * is read-only" is asserted, not assumed. Writes only happen at the explicit confirm steps and
 * are answered by the mock.
 *
 * Screenshots (mobile) go to /tmp/wt-shots inside the container.
 */

import { test, expect, type Page } from '@playwright/test';

const SHOTS = '/tmp/wt-shots';
type Sets = (number | null)[];

const exRow = (id: string, exercise: string, weight: number | null, s: Sets, delta: number | null, sid: string, date: string, split: string, comment: string | null = null) => ({
  id, exercise, status: 'done', weight_kg: weight, workout_date: date, split, comment, session_id: sid,
  set1_reps: s[0] ?? null, set2_reps: s[1] ?? null, set3_reps: s[2] ?? null, set4_reps: s[3] ?? null, set5_reps: s[4] ?? null,
  total_reps: s.reduce<number>((a, v) => a + (v ?? 0), 0), delta,
});

const SESSIONS = [
  { id: 's4', workout_date: '2026-06-05', split: 'Pull', ex: [['Straight-arm leg raise', null, [20, 20, 20, 17], 3], ['Pull up', null, [8, 7, 6], -2], ['Dumbbell Row', 35, [10, 10, 10, 10, 9], 0], ['Squats 40', 40, [10, 10, 10], null]] },
  { id: 's3', workout_date: '2026-06-02', split: 'Push', ex: [['Incline bench', 55, [9, 9, 9], 3], ['Dips', null, [8, 8, 7], 0], ['Overhead Press', 30, [8, 8, 6], -1]] },
  { id: 's2', workout_date: '2026-05-29', split: 'Pull', ex: [['Straight-arm leg raise', null, [20, 20, 17], null], ['Pull up', null, [8, 8, 6], 2]] },
  { id: 's1', workout_date: '2026-05-20', split: 'Push Hotel', ex: [['Dips', null, [8, 8], null]] },
];
const sessionRows = (s: (typeof SESSIONS)[number]) =>
  s.ex.map((e, i) => exRow(`${s.id}-${i}`, e[0] as string, e[1] as number | null, e[2] as Sets, e[3] as number | null, s.id, s.workout_date, s.split));

// Bench-press history with an uneven calendar (a 16-day and a 15-day gap) and varying weights
const BENCH_DATES = ['2026-02-18', '2026-02-23', '2026-02-27', '2026-03-09', '2026-03-12', '2026-03-16', '2026-03-21', '2026-04-07', '2026-04-10', '2026-04-13', '2026-04-23', '2026-05-08', '2026-05-26', '2026-06-02'];
const BENCH = BENCH_DATES.map((d, i) =>
  exRow(`b${i}`, 'Bench Press', i < 6 ? 60 : i < 10 ? 65 : i < 13 ? 70 : 75, [12 - (i % 3), 11 - (i % 2), 10, i % 2 ? 9 : null], null, i === 13 ? 's4' : `bs${i}`, d, 'Push',
    i === 13 ? 'Shoulder felt a bit unstable on the last set.' : i === 12 ? 'Felt strong today.' : null));

// Timing is measured for the 3 newest occurrences only; older ones must show nothing (never invented)
const TIMING: Record<number, object> = {
  13: { time_of_day: '17:42', duration_sec: 480, rest_avg_sec: 120 },
  12: { time_of_day: '18:05', duration_sec: 75 },
  11: { rest_avg_sec: 95 },
};
BENCH.forEach((r, i) => Object.assign(r, { time_of_day: null, duration_sec: null, rest_avg_sec: null, ...(TIMING[i] ?? {}) }));

const ds = (rows: unknown[], total = rows.length) => ({ meta: { object_type: 'x', label: 'x', total, page: 1, page_size: rows.length || 1 }, schema: [], rows });
const writes: string[] = [];
let sessions = [...SESSIONS];

async function mockApi(page: Page) {
  writes.length = 0;
  sessions = [...SESSIONS];
  await page.route(/\/api\/workout\//, async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const p = url.pathname.replace('/api/workout', '');
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (req.method() !== 'GET') {
      writes.push(`${req.method()} ${p}`);
      if (p === '/sessions/start') return json(ds([{ id: 'new1', split: 'Pull', workout_date: '2026-10-28', started_at: 'x' }]));
      if (req.method() === 'DELETE' && p.startsWith('/sessions/')) {
        const id = p.split('/')[2];
        sessions = sessions.filter((s) => s.id !== id);
        return json(ds([]));
      }
      return json({ error: { code: 'UNEXPECTED_WRITE', message: `unexpected ${req.method()} ${p}`, request_id: 'm' } }, 400);
    }
    if (p === '/archetypes') return json(ds(['Pull', 'Push', 'Push Hotel'].map((s) => ({ id: s, split: s, session_count: 3, last_date: '2026-06-05' }))));
    if (p === '/sessions/active') return json(ds([]));
    if (p === '/sessions') {
      const split = (url.searchParams.get('split') ?? '').toLowerCase();
      const list = sessions.filter((s) => !split || s.split.toLowerCase() === split);
      return json(ds(list.map((s) => ({ id: s.id, workout_date: s.workout_date, split: s.split, status: 'finished', exercise_count: s.ex.length,
        exercises: sessionRows(s).map((r) => ({ id: r.id, exercise: r.exercise, weight_kg: r.weight_kg, set1_reps: r.set1_reps, set2_reps: r.set2_reps, set3_reps: r.set3_reps, set4_reps: r.set4_reps, set5_reps: r.set5_reps, delta: r.delta })) })), list.length));
    }
    const m = p.match(/^\/sessions\/([^/]+)\/exercises$/);
    if (m) { const s = sessions.find((x) => x.id === m[1]); return s ? json(ds(sessionRows(s))) : json({ error: { code: 'NOT_FOUND', message: 'nf', request_id: 'm' } }, 404); }
    if (p === '/exercises/history') {
      const name = (url.searchParams.get('name') ?? '').toLowerCase();
      if (name === 'bench press') return json(ds(BENCH));
      const rows = SESSIONS.flatMap((s) => sessionRows(s)).filter((r) => r.exercise.toLowerCase() === name).reverse();
      return json(ds(rows));
    }
    if (p === '/exercises/names') return json(ds([]));
    return json({ error: { code: 'NOT_FOUND', message: 'not mocked', request_id: 'm' } }, 404);
  });
}

async function noOverflow(page: Page, label: string) {
  const o = await page.evaluate(() => {
    const c = document.querySelector('.shell-content') as HTMLElement | null;
    return { doc: document.documentElement.scrollWidth - window.innerWidth, content: c ? c.scrollWidth - c.clientWidth : 0 };
  });
  expect(o.doc, `${label}: document overflow`).toBeLessThanOrEqual(0);
  expect(o.content, `${label}: content overflow`).toBeLessThanOrEqual(0);
}

async function swipe(page: Page, target: ReturnType<Page['locator']>, dx: number) {
  const b = (await target.boundingBox())!;
  const y = b.y + b.height / 2, x0 = b.x + b.width / 2;
  await page.mouse.move(x0, y);
  await page.mouse.down();
  await page.mouse.move(x0 + dx / 3, y, { steps: 4 });
  await page.mouse.move(x0 + dx, y, { steps: 6 });
  return async () => { await page.mouse.up(); };
}

test.describe('P1 at 393px', () => {
  test.use({ viewport: { width: 393, height: 800 }, hasTouch: true, isMobile: true });

  test('log list, filter, navigation are read-only; swipe actions confirm first', async ({ page }) => {
    await mockApi(page);
    await page.goto('/workout/log');
    await expect(page.getByRole('heading', { name: 'Log' })).toBeVisible();
    await expect(page.getByRole('article')).toHaveCount(4);
    await noOverflow(page, 'log');
    // reverse chronological
    const labels = await page.getByRole('article').evaluateAll((els) => els.map((e) => e.getAttribute('aria-label')));
    expect(labels[0]).toContain('Jun 5, 2026');
    expect(labels[3]).toContain('May 20, 2026');
    // no overall score / exercise-count badge text like "4 ex"
    await expect(page.getByText(/\d+ ex$/)).toHaveCount(0);
    await page.screenshot({ path: `${SHOTS}/p1_1_log.png` });

    // filter by an actual archetype
    await page.getByRole('button', { name: 'Pull', exact: true }).click();
    await expect(page.getByRole('article')).toHaveCount(2);
    await expect(page.getByText('Pull · 2 sessions')).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/p1_2_log_filtered.png` });
    await page.getByRole('button', { name: 'All', exact: true }).click();
    await expect(page.getByRole('article')).toHaveCount(4);

    // exercise row → history (read-only), then back
    await page.getByRole('article').first().getByRole('button', { name: /^Pull up/ }).click();
    await expect(page).toHaveURL(/\/workout\/log\/exercise\?name=Pull%20up/);
    await page.getByRole('button', { name: 'Back', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Log' })).toBeVisible();

    // session → detail (read-only), back
    await page.getByRole('article').first().getByRole('button', { name: /^Open Pull session/ }).click();
    await expect(page).toHaveURL(/\/workout\/log\/s4$/);
    await page.getByRole('button', { name: 'Back', exact: true }).click();
    expect(writes, 'browsing must not write').toEqual([]);

    // swipe LEFT → delete confirmation; cancel keeps everything, no write
    const card = page.getByRole('article').nth(1).locator('xpath=..');
    let release = await swipe(page, card, -120);
    await page.screenshot({ path: `${SHOTS}/p1_3_swipe_left.png` });
    await release();
    const del = page.getByRole('dialog', { name: 'Delete this session?' });
    await expect(del).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/p1_4_delete_confirm.png` });
    await del.getByRole('button', { name: 'Cancel' }).click();
    await expect(page.getByRole('article')).toHaveCount(4);
    expect(writes).toEqual([]);

    // swipe RIGHT → repeat confirmation; cancel → no write
    release = await swipe(page, page.getByRole('article').first().locator('xpath=..'), 120);
    await page.screenshot({ path: `${SHOTS}/p1_5_swipe_right.png` });
    await release();
    const rep = page.getByRole('dialog', { name: /again\?/ });
    await expect(rep).toBeVisible();
    await rep.getByRole('button', { name: 'Cancel' }).click();
    expect(writes).toEqual([]);

    // a short swipe does nothing and a plain tap still opens the session
    release = await swipe(page, page.getByRole('article').first().locator('xpath=..'), 30);
    await release();
    await expect(page.getByRole('dialog', { name: /again\?|Delete this session\?/ })).toHaveCount(0);

    // confirmed delete: exactly one DELETE for that session; others untouched
    release = await swipe(page, page.getByRole('article').nth(1).locator('xpath=..'), -120);
    await release();
    await page.getByRole('dialog', { name: 'Delete this session?' }).getByRole('button', { name: 'Delete' }).click();
    await expect(page.getByRole('article')).toHaveCount(3);
    expect(writes).toEqual(['DELETE /sessions/s3']);

    // confirmed repeat: POST start from that session, then the Session tab
    release = await swipe(page, page.getByRole('article').first().locator('xpath=..'), 120);
    await release();
    await page.getByRole('dialog', { name: /again\?/ }).getByRole('button', { name: 'Start workout' }).click();
    await expect(page).toHaveURL(/\/workout$/);
    expect(writes).toEqual(['DELETE /sessions/s3', 'POST /sessions/start']);
  });

  test('exercise history: Sessions vs Timeline spacing, selection, read-only', async ({ page }) => {
    await mockApi(page);
    await page.goto('/workout/log/exercise?name=Bench%20Press');
    await expect(page.getByRole('heading', { name: 'Bench Press' })).toBeVisible();
    const cols = page.getByRole('group', { name: /recorded sessions/ }).getByRole('button');
    await expect(cols).toHaveCount(BENCH.length);
    await noOverflow(page, 'history sessions');

    const xs = async () => (await cols.evaluateAll((els) => els.map((e) => Math.round(e.getBoundingClientRect().x))));
    const diffs = (a: number[]) => a.slice(1).map((v, i) => v - a[i]);

    // Sessions: equally spaced
    const dS = diffs(await xs());
    expect(Math.max(...dS) - Math.min(...dS), `sessions spacing ${dS}`).toBeLessThanOrEqual(1);
    await page.screenshot({ path: `${SHOTS}/p1_6_history_sessions.png` });

    // Timing metadata: compact line for measured sessions only; unmeasured ones show none
    const timing = page.getByTestId('timing');
    await expect(timing).toHaveCount(3);   // list rows with something measured; the other 11 show nothing
    await expect(timing.first()).toHaveText('17:42 · 8 min · rest 2:00');
    await expect(timing.filter({ hasText: '18:05 · 75 s' })).toHaveCount(1);
    await expect(timing.filter({ hasText: /^rest 1:35$/ })).toHaveCount(1);
    await cols.last().click();             // select the newest session: its detail card shows the same line
    await expect(timing).toHaveCount(4);
    await page.screenshot({ path: `${SHOTS}/p2_history_timing.png` });

    // Timeline: same occurrences, spacing follows the calendar (real gaps)
    await page.getByRole('button', { name: 'Timeline', exact: true }).click();
    await expect(cols).toHaveCount(BENCH.length);
    const dT = diffs(await xs());
    expect(Math.max(...dT), `timeline spacing ${dT}`).toBeGreaterThan(Math.min(...dT) * 1.8);
    await noOverflow(page, 'history timeline');

    // exact weight + reps are available on every column without selecting
    await expect(page.getByRole('button', { name: /Feb 18, 2026, 60 kg, reps 12, 11, 10/ })).toBeVisible();

    // select a column → date, weight, sets, reps, note
    await cols.nth(13).click();
    const detail = page.getByRole('region', { name: 'Selected session' });
    await expect(detail).toContainText('Jun 2, 2026');
    await expect(detail).toContainText('75 kg');
    await expect(detail).toContainText('Shoulder felt a bit unstable');
    await page.screenshot({ path: `${SHOTS}/p1_7_history_timeline_selected.png` });
    await detail.getByRole('button', { name: 'Previous session' }).click();
    await expect(detail).toContainText('May 26, 2026');

    // list under the chart: newest first, comment inline, no extra click
    const list = page.getByRole('region', { name: 'All sessions' });
    await expect(list.getByRole('listitem').first()).toContainText('Jun 2, 2026');
    await expect(list.getByRole('listitem').first()).toContainText('Shoulder felt a bit unstable on the last set.');
    await list.scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${SHOTS}/p1_8_history_list.png` });

    // selecting never writes; 'Open session' navigates read-only
    await detail.getByRole('button', { name: 'Next session' }).click();
    await detail.getByRole('button', { name: 'Open session' }).click();
    await expect(page).toHaveURL(/\/workout\/log\/s4$/);
    expect(writes, 'history browsing must not write').toEqual([]);
  });

  test('session detail is read-only until Edit; editing is explicit', async ({ page }) => {
    await mockApi(page);
    await page.goto('/workout/log/s4');
    await expect(page.getByRole('heading', { name: 'Pull' })).toBeVisible();
    await noOverflow(page, 'session detail');
    await expect(page.getByRole('button', { name: 'Edit', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: '+ Add Exercise' })).toHaveCount(0);
    await page.screenshot({ path: `${SHOTS}/p1_9_session_detail.png` });

    // tapping an exercise opens its history, not an editor
    await page.getByRole('button', { name: /^Pull up, open history/ }).click();
    await expect(page).toHaveURL(/log\/exercise\?name=Pull%20up/);
    await page.getByRole('button', { name: 'Back', exact: true }).click();

    // explicit Edit workflow
    await page.getByRole('button', { name: 'Edit', exact: true }).click();
    await expect(page.getByRole('status')).toContainText('Editing a past workout');
    await expect(page.getByRole('button', { name: '+ Add Exercise' })).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/p1_10_session_edit_mode.png` });
    await page.getByRole('button', { name: /^Edit Pull up/ }).click();
    await expect(page.getByRole('button', { name: 'Save' })).toBeVisible();
    await page.getByRole('button', { name: 'Back without saving' }).click();
    await page.evaluate(() => { try { Object.keys(localStorage).filter((k) => k.startsWith('workout_')).forEach((k) => localStorage.removeItem(k)); } catch { /* ignore */ } });
    expect(writes, 'opening the editor without saving must not write').toEqual([]);
  });
});

for (const width of [360, 412]) {
  test.describe(`P1 smoke at ${width}px`, () => {
    test.use({ viewport: { width, height: 800 }, hasTouch: true, isMobile: true });
    test(`no overflow on log, history, detail`, async ({ page }) => {
      await mockApi(page);
      await page.goto('/workout/log');
      await expect(page.getByRole('article')).toHaveCount(4);
      await noOverflow(page, 'log');
      await page.screenshot({ path: `${SHOTS}/p1_vp${width}_log.png` });
      await page.goto('/workout/log/exercise?name=Bench%20Press');
      await expect(page.getByRole('group', { name: /recorded sessions/ }).getByRole('button')).toHaveCount(BENCH.length);
      await noOverflow(page, 'history');
      await page.getByRole('button', { name: 'Timeline', exact: true }).click();
      await noOverflow(page, 'timeline');
      await page.screenshot({ path: `${SHOTS}/p1_vp${width}_history.png` });
      await page.goto('/workout/log/s4');
      await expect(page.getByRole('heading', { name: 'Pull' })).toBeVisible();
      await noOverflow(page, 'detail');
      expect(writes).toEqual([]);
    });
  });
}
