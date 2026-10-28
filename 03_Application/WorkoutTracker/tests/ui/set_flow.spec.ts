/**
 * UI tests — WorkoutTracker — P1.5/P2 capture: tap a set to start it, checkmark to confirm it.
 *
 * The Workout API is a stateful mock of the server contract (page.route): it stamps start / end
 * times itself, is idempotent, and records every write, so ordering, idempotency, retry and
 * "nothing is written until the checkmark" are asserted. Nothing touches the real database.
 * Screenshots go to /tmp/wt-shots inside the container.
 */

import { test, expect, type Page } from '@playwright/test';

const SHOTS = '/tmp/wt-shots';
const SID = '88888888-8888-8888-8888-888888888888';

type Row = Record<string, unknown> & { id: string };
const blank = (id: string, exercise: string, status: string, weight: number | null): Row => ({
  id, exercise, status, weight_kg: weight, workout_date: '2026-10-28', split: 'Pull', comment: null, total_reps: 0, delta: null,
  ...Object.fromEntries([1, 2, 3, 4, 5].flatMap((n) => [[`set${n}_reps`, null], [`set${n}_started_at`, null], [`set${n}_ended_at`, null]])),
});
const ds = (rows: unknown[]) => ({ meta: { object_type: 'x', label: 'x', total: rows.length, page: 1, page_size: rows.length || 1 }, schema: [], rows });
const hist = (id: number, date: string, s: number[]) => ({
  id: String(id), workout_date: date, weight_kg: 10, comment: null, split: 'Pull',
  set1_reps: s[0] ?? null, set2_reps: s[1] ?? null, set3_reps: s[2] ?? null, set4_reps: s[3] ?? null, set5_reps: s[4] ?? null,
});

let rows: Row[] = [];
let writes: string[] = [];
let clock = 0;
let failNext = 0; // number of upcoming set events to fail as a network error
let nextId = 10;

async function mockApi(page: Page) {
  rows = [blank('1', 'Pull up', 'planned', 10), blank('2', 'Dips', 'planned', null)];
  writes = [];
  clock = 0;
  failNext = 0;
  const stamp = () => new Date(Date.now() + clock++).toISOString(); // monotonic, close to the browser clock
  await page.route(/\/api\/workout\//, async (route) => {
    const req = route.request();
    const p = new URL(req.url()).pathname.replace('/api/workout', '');
    const json = (b: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(b) });
    if (req.method() === 'GET') {
      if (p === '/sessions/active') return json(ds([{ id: SID, split: 'Pull', workout_date: '2026-10-28', started_at: '2026-10-28 18:00' }]));
      if (p === `/sessions/${SID}/exercises`) return json(ds(rows));
      if (p === '/exercises/history') return json(ds([hist(900, '2026-10-20', [8, 7, 6]), hist(901, '2026-10-24', [9, 8, 8])]));
      if (p === '/exercises/names') return json(ds(['Pull up', 'Dips', 'Row'].map((e) => ({ id: e, exercise: e, use_count: 3 }))));
      return json({ error: { code: 'NOT_FOUND', message: 'not mocked', request_id: 'm' } }, 404);
    }
    writes.push(`${req.method()} ${p}`);
    const body = req.postDataJSON?.() ?? {};
    if (p === `/sessions/${SID}/exercises`) {
      rows.push({ ...blank(String(nextId++), body.exercise, body.status, body.weight_kg) });
      return json(ds(rows));
    }
    const m = p.match(/^\/exercises\/(\d+)\/(sets\/(\d)\/(start|confirm|unconfirm)|details)$/);
    if (!m) return json({ error: { code: 'UNEXPECTED_WRITE', message: p, request_id: 'm' } }, 400);
    if (m[3] && failNext > 0) {
      failNext--;
      return route.abort('connectionfailed');
    }
    const row = rows.find((r) => r.id === m[1])!;
    if (m[2] === 'details') {
      Object.assign(row, { exercise: body.exercise, weight_kg: body.weight_kg, comment: body.comment });
      return json(ds(rows));
    }
    const n = m[3];
    if (m[4] === 'start' && !row[`set${n}_started_at`] && !row[`set${n}_ended_at`]) row[`set${n}_started_at`] = stamp();
    if (m[4] === 'confirm') {
      row[`set${n}_reps`] = body.reps;
      row.weight_kg = body.weight_kg;
      row.status = 'done';
      if (!row[`set${n}_ended_at`]) row[`set${n}_ended_at`] = stamp();
    }
    if (m[4] === 'unconfirm') {
      row[`set${n}_reps`] = null; row[`set${n}_started_at`] = null; row[`set${n}_ended_at`] = null;
      if (![1, 2, 3, 4, 5].some((k) => row[`set${k}_reps`] != null)) row.status = 'planned';
    }
    return json(ds(rows));
  });
}

test.use({ viewport: { width: 393, height: 820 }, hasTouch: true, isMobile: true });

const setRow = (page: Page, n: number) => page.getByRole('group', { name: `Set ${n}`, exact: true });

test.beforeEach(async ({ page }) => {
  await mockApi(page);
  await page.goto('/workout');
  await page.evaluate(() => { try { Object.keys(localStorage).filter((k) => k.startsWith('workout_')).forEach((k) => localStorage.removeItem(k)); } catch { /* ignore */ } });
  await page.goto('/workout');
  await page.getByRole('button', { name: /^Pull up/ }).click();
  await expect(setRow(page, 1)).toBeVisible();
});

test('prefill is a dashed suggestion; nothing is written until the checkmark', async ({ page }) => {
  await expect(page.getByLabel('Set 1 reps')).toHaveValue('9'); // last session
  expect(await page.getByLabel('Set 1 reps').evaluate((el) => getComputedStyle(el).borderTopStyle)).toBe('dashed');
  await expect(setRow(page, 1)).toHaveAttribute('data-state', 'idle');
  await page.screenshot({ path: `${SHOTS}/p15_1_prefilled.png` });
  await page.getByLabel('Set 1: more reps').click();           // editing the suggestion is not confirming
  await page.getByRole('button', { name: 'Done' }).click();     // leaving does not confirm either
  await expect(page.getByRole('button', { name: 'Finish Workout' })).toBeVisible();
  expect(writes).toEqual([]);
  expect(rows[0].status).toBe('planned');
});

test('tap starts once; checkmark confirms with the shown reps; events arrive in order', async ({ page }) => {
  await page.getByRole('button', { name: 'Start set 1' }).click();
  await expect(setRow(page, 1)).toHaveAttribute('data-state', 'active');
  await page.getByRole('button', { name: 'Start set 1' }).click();       // second tap: no second event
  await page.screenshot({ path: `${SHOTS}/p15_2_active.png` });
  await page.getByRole('button', { name: 'Confirm set 1' }).click();
  await expect(setRow(page, 1)).toHaveAttribute('data-state', 'done');
  await page.screenshot({ path: `${SHOTS}/p15_3_confirmed.png` });
  await expect.poll(() => writes.length).toBe(2);
  expect(writes).toEqual(['POST /exercises/1/sets/1/start', 'POST /exercises/1/sets/1/confirm']);
  expect(rows[0]).toMatchObject({ status: 'done', set1_reps: 9 });
  expect(rows[0].set1_started_at).not.toBeNull();
  expect(new Date(rows[0].set1_ended_at as string) >= new Date(rows[0].set1_started_at as string)).toBe(true);
});

test('confirming without a start tap keeps the start empty', async ({ page }) => {
  await page.getByRole('button', { name: 'Confirm set 2' }).click();
  await expect.poll(() => writes.length).toBe(1);
  expect(writes[0]).toBe('POST /exercises/1/sets/2/confirm');
  expect(rows[0].set2_started_at).toBeNull();
  expect(rows[0].set2_ended_at).not.toBeNull();
});

test('correcting a confirmed set re-sends the confirmation without moving timing; undo clears it', async ({ page }) => {
  await page.getByRole('button', { name: 'Start set 1' }).click();
  await page.getByRole('button', { name: 'Confirm set 1' }).click();
  await expect.poll(() => writes.length).toBe(2);
  const ended = rows[0].set1_ended_at;
  await page.getByLabel('Set 1: fewer reps').click();
  await expect.poll(() => rows[0].set1_reps).toBe(8);
  expect(rows[0].set1_ended_at).toBe(ended);
  // undo needs an explicit confirmation
  await page.getByRole('button', { name: 'Set 1 confirmed, tap to undo' }).click();
  await page.getByRole('dialog', { name: /Undo set 1/ }).getByRole('button', { name: 'Undo set' }).click();
  await expect(setRow(page, 1)).toHaveAttribute('data-state', 'idle');
  await expect.poll(() => rows[0].status).toBe('planned');
  expect(rows[0]).toMatchObject({ set1_reps: null, set1_started_at: null, set1_ended_at: null });
});

test('reopening restores confirmed and in-progress sets from the server', async ({ page }) => {
  await page.getByRole('button', { name: 'Confirm set 1' }).click();
  await page.getByRole('button', { name: 'Start set 2' }).click();
  await expect.poll(() => writes.length).toBe(2);
  await page.reload();
  await expect(setRow(page, 1)).toHaveAttribute('data-state', 'done');
  await expect(setRow(page, 2)).toHaveAttribute('data-state', 'active');
  await expect(setRow(page, 3)).toHaveAttribute('data-state', 'idle');
});

test('offline taps are kept, retried and delivered in order', async ({ page }) => {
  failNext = 1;
  await page.getByRole('button', { name: 'Start set 1' }).click();
  await page.getByRole('button', { name: 'Confirm set 1' }).click();
  await expect(setRow(page, 1)).toHaveAttribute('data-state', 'done');     // UI answers immediately
  await expect(page.getByRole('status').filter({ hasText: 'retrying' })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/p15_4_retrying.png` });
  await expect.poll(() => rows[0].set1_ended_at, { timeout: 8000 }).not.toBeNull();
  expect(writes.filter((w) => !w.includes('start')).length).toBe(1);
  expect(rows[0].set1_started_at).not.toBeNull();                          // start landed before the end
  await expect(page.getByRole('status').filter({ hasText: 'retrying' })).toHaveCount(0);
});

test('a new exercise gets its row on the first set tap; Done saves name, weight and notes only', async ({ page }) => {
  await page.getByRole('button', { name: 'Done' }).click();
  await page.getByRole('button', { name: '+ Add Exercise' }).click();
  await page.getByLabel('Exercise name').fill('Row');
  await page.getByLabel('Weight (kg)').fill('30');
  await page.getByLabel('Set 1 reps').fill('10');
  await page.getByLabel('Notes').fill('smooth');
  expect(writes).toEqual([]);                                              // typing alone writes nothing
  await page.getByRole('button', { name: 'Start set 1' }).click();
  await page.getByRole('button', { name: 'Confirm set 1' }).click();
  await expect.poll(() => writes.length).toBe(3);
  expect(writes.slice(0, 3)).toEqual(['POST /sessions/' + SID + '/exercises', 'POST /exercises/10/sets/1/start', 'POST /exercises/10/sets/1/confirm']);
  await page.getByRole('button', { name: 'Done' }).click();
  await expect(page.getByRole('button', { name: 'Finish Workout' })).toBeVisible();
  expect(writes[3]).toBe('PATCH /exercises/10/details');
  expect(rows.find((r) => r.id === '10')).toMatchObject({ exercise: 'Row', weight_kg: 30, comment: 'smooth', set1_reps: 10, status: 'done' });
});

test('starting a set needs an exercise name', async ({ page }) => {
  await page.getByRole('button', { name: 'Done' }).click();
  await page.getByRole('button', { name: '+ Add Exercise' }).click();
  await page.getByRole('button', { name: 'Start set 1' }).click();
  await expect(page.getByRole('alert')).toContainText('exercise name');
  expect(writes).toEqual([]);
});

test('a note typed after confirming a set survives a reload', async ({ page }) => {
  await page.getByRole('button', { name: 'Confirm set 1' }).click();
  await page.getByLabel('Notes').fill('typed, not saved yet');
  await expect.poll(() => writes.length).toBe(1);
  await page.reload();
  await expect(setRow(page, 1)).toHaveAttribute('data-state', 'done');
  await expect(page.getByLabel('Notes')).toHaveValue('typed, not saved yet');
});

test('timing line stays hidden until measured, then shows set and rest as secondary text', async ({ page }) => {
  await expect(page.getByTestId('live-timing')).toHaveCount(0);
  await page.getByRole('button', { name: 'Start set 1' }).click();
  await expect(page.getByTestId('live-timing')).toContainText(/Exercise \d+:\d\d · Set \d+:\d\d/);
  await page.getByRole('button', { name: 'Confirm set 1' }).click();
  await expect(page.getByTestId('live-timing')).toContainText(/Exercise \d+:\d\d · Rest \d+:\d\d/);
  await page.screenshot({ path: `${SHOTS}/p2_live_timing.png` });
  // a set confirmed without a start tap: no exercise elapsed, but the rest is still measured
  await page.getByRole('button', { name: 'Done' }).click();
  await page.getByRole('button', { name: /^Dips/ }).click();
  await page.getByLabel('Set 1 reps').fill('8');
  await page.getByRole('button', { name: 'Confirm set 1' }).click();
  await expect(page.getByTestId('live-timing')).toHaveText(/^Rest \d+:\d\d$/);
});
