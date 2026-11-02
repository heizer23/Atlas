/**
 * UI tests — WorkoutTracker — finish celebration (FinishModal), fully mocked (no DB writes).
 *
 * The idle Session screen logs a light activity day; the mocked POST returns a Celebration with ~60
 * streaks (before: current 9 days, after: 10 → crosses into the Champions League and climbs).
 * Checks: two-step flow and buttons stay visible, count/rank change after the animation, Champions
 * section + current outline, tab choice is remembered, expand shows dates, no horizontal overflow,
 * reduced motion shows the final state at once. Screenshots go to /tmp/wt-shots in the container.
 */

import { test, expect, type Page } from '@playwright/test';

const SHOTS = '/tmp/wt-shots';
const TODAY = '2026-11-12';

const ds = (rows: unknown[]) => ({ meta: { object_type: 'x', label: 'x', total: rows.length, page: 1, page_size: rows.length || 1 }, schema: [], rows });

function streaks(currentLen: number) {
  const hist = [92, 71, 63, 44, 31, 22, 15, 10, 10, 10, 9, 9, 7, 6, 5, 5, 4, 4, 4, 3, 3, 3, 3, ...Array(12).fill(2), ...Array(30).fill(1)];
  // Disjoint streaks walking back from September, one gap day between them (as real data is)
  let cursor = Date.UTC(2026, 9, 1);
  const rows = hist.map((length) => {
    const end = new Date(cursor - 86400000);
    const start = new Date(end.getTime() - (length - 1) * 86400000);
    cursor = start.getTime() - 86400000;
    return { start: start.toISOString().slice(0, 10), end: end.toISOString().slice(0, 10), length, current: false };
  });
  rows.push({ start: '2026-11-03', end: TODAY, length: currentLen, current: true });
  rows.sort((a, b) => b.length - a.length || Number(b.current) - Number(a.current) || b.end.localeCompare(a.end));
  return rows.map((r, i) => ({ ...r, rank: i + 1 }));
}

function snap(count: number, curLen: number) {
  const rank = streaks(curLen);
  const cur = rank.find((r) => r.current)!;
  const yr = rank.filter((r) => r.end >= '2026-01-01');
  const monthly = (n: number[]) => n;
  return {
    today: TODAY, years: [2024, 2025, 2026],
    monthly: {
      '2024': monthly([4, 6, 7, 10, 9, 8, 9, 12, 13, 10, 11, 9]),
      '2025': monthly([5, 7, 8, 8, 9, 9, 11, 14, 12, 12, 8, 7]),
      '2026': [...monthly([4, 6, 6, 7, 8, 9, 8, 11, 10, 12]), count, null],
    },
    frequency: {
      '2025': [1.1, 1.5, 1.7, 1.8, 1.9, 2.0, 2.1, 2.5, 2.7, 2.8, 2.7, 2.6],
      '2026': [0.9, 1.4, 1.5, 1.7, 1.8, 2.0, 2.1, 2.5, 2.7, 2.8, count === 9 ? 2.9 : 2.8, null],
    },
    month: { year: 2026, month: 11, day: 12, count, last_year_count: 8, last_year_through: '2025-11-12', ahead: count - 8 },
    today_counts: count === 9,
    ranking: rank, ranking_year: yr.map((r, i) => ({ ...r, rank: i + 1 })),
    current: { length: curLen, rank: cur.rank, total: rank.length, rank_year: 1, total_year: yr.length },
  };
}

const CELEBRATION = { before: snap(8, 9), after: snap(9, 10), changed: true, note: null, crossed_champions: true };

const CAL = [{ date: '2026-11-01', primary: 'workout' }, { date: '2026-11-03', primary: 'running' }, { date: TODAY, primary: 'other' }];

async function mockApi(page: Page, celebration: unknown) {
  await page.route(/\/api\/workout\//, async (route) => {
    const req = route.request();
    const p = new URL(req.url()).pathname;
    const json = (body: unknown) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    if (p.endsWith('/sessions/active')) return json(ds([]));
    if (p.endsWith('/calendar')) return json(ds(CAL));
    if (p.endsWith('/archetypes')) return json(ds([{ id: 'Pull', split: 'Pull', session_count: 17, last_date: '2026-06-05' }]));
    if (p.endsWith('/activity-days')) return req.method() === 'POST' ? json({ celebration, already_finished: false }) : json(ds([]));
    if (req.method() !== 'GET') throw new Error(`unexpected write: ${req.method()} ${p}`);
    return json(ds([]));
  });
}

async function open(page: Page, celebration: unknown = CELEBRATION) {
  await mockApi(page, celebration);
  await page.goto('/workout');
  await page.getByRole('button', { name: 'Stretch' }).click();
  await expect(page.locator('[aria-labelledby="finish-title"]')).toBeVisible();
}

for (const [w, h] of [[393, 852], [360, 740]]) {
  test(`two-step flow at ${w}x${h}`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: h });
    await page.addInitScript(() => localStorage.removeItem('workout_streak_view'));
    await open(page);
    await expect(page.getByText('Your year')).toBeVisible();
    await page.waitForTimeout(1500);
    await page.screenshot({ path: `${SHOTS}/finish_${w}_0.png` });
    await page.getByRole('button', { name: /See my month/ }).click();
    const next = page.getByRole('button', { name: /See my streak/ });
    await expect(page.getByText('Your monthly race')).toBeVisible();
    await expect(page.getByText('8 activity days')).toBeVisible();            // opens on the old statistics
    await page.screenshot({ path: `${SHOTS}/finish_${w}_1a.png` });
    await expect(page.getByText('9 activity days')).toBeVisible({ timeout: 4000 });
    await expect(page.getByText('1 ahead of last year')).toBeVisible();
    await page.waitForTimeout(1200);
    await page.screenshot({ path: `${SHOTS}/finish_${w}_1b.png` });
    expect(await next.boundingBox().then((b) => b!.y + b!.height)).toBeLessThanOrEqual(h);

    await next.click();
    await expect(page.getByText(/Rank 8? ?\d* of 63|Rank \d+ of/)).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/finish_${w}_2a.png` });
    await expect(page.getByText('Welcome to the Champions League.')).toBeVisible({ timeout: 6000 });
    await expect(page.getByText(/up 3 places/)).toBeVisible();
    await page.waitForTimeout(1000);
    await page.screenshot({ path: `${SHOTS}/finish_${w}_2b.png` });
    const cur = page.getByRole('listitem', { name: /current streak/ });
    await expect(cur).toHaveCount(1);
    await expect(page.getByText('CHAMPIONS LEAGUE · 10+ DAYS')).toBeVisible();

    // tab choice persists, expansion shows dates
    await page.getByRole('tab', { name: 'This year' }).click();
    expect(await page.evaluate(() => localStorage.getItem('workout_streak_view'))).toBe('year');
    await page.getByRole('tab', { name: 'All time' }).click();
    await page.getByRole('button', { name: 'Expand history' }).click();
    await page.waitForTimeout(1000);
    await page.screenshot({ path: `${SHOTS}/finish_${w}_2c.png` });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

    const done = page.getByRole('button', { name: 'Done' });
    expect(await done.boundingBox().then((b) => b!.y + b!.height)).toBeLessThanOrEqual(h);
    await done.click();
    await expect(page.locator('[aria-labelledby="finish-title"]')).toHaveCount(0);
  });
}

test('reduced motion shows the final state immediately', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.setViewportSize({ width: 393, height: 852 });
  await open(page);
  await page.getByRole('button', { name: /See my month/ }).click();
  await expect(page.getByText('9 activity days')).toBeVisible({ timeout: 500 });
  await page.getByRole('button', { name: /See my streak/ }).click();
  await expect(page.getByText('Welcome to the Champions League.')).toBeVisible({ timeout: 500 });
  await expect(page.getByText(/up 3 places/)).toBeVisible();
});

test('same-day repeat explains quietly and changes nothing', async ({ page }) => {
  const same = { before: snap(9, 10), after: snap(9, 10), changed: false, note: 'Today already counts.', crossed_champions: false };
  await page.setViewportSize({ width: 393, height: 852 });
  await open(page, same);
  await expect(page.getByText('Today already counts.')).toBeVisible();
  await page.getByRole('button', { name: /See my month/ }).click();
  await expect(page.getByText('Today already counts.')).toBeVisible();
  await expect(page.getByText('9 activity days')).toBeVisible();
  await page.getByRole('button', { name: /See my streak/ }).click();
  await expect(page.getByText('Today already counts.')).toBeVisible();
  await expect(page.getByText('Welcome to the Champions League.')).toHaveCount(0);
  await expect(page.getByText(/up \d+ place/)).toHaveCount(0);
});
