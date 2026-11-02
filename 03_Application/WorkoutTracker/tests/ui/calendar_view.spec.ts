/** Performance tab shows calendar, monthly race and streak ranking (mocked reads; no writes). */
import { test, expect } from '@playwright/test';

const ds = (rows: unknown[]) => ({ meta: { object_type: 'x', label: 'x', total: rows.length, page: 1, page_size: rows.length || 1 }, schema: [], rows });

test('performance tab holds the three charts', async ({ page }) => {
  await page.setViewportSize({ width: 393, height: 852 });
  const today = new Date().toLocaleDateString('en-CA');
  const year = Number(today.slice(0, 4));
  const days = Array.from({ length: 40 }, (_, i) => ({ id: i, date: new Date(Date.UTC(year, 0, 1 + i * 2)).toISOString().slice(0, 10), primary: ['workout', 'workout', 'running', 'other'][i % 4] }));
  const monthly = Array(12).fill(0).map((_, m) => (m < 10 ? 5 + m : null));
  const snap = {
    today, years: [year], monthly: { [year]: monthly }, frequency: { [year]: monthly.map((v) => (v === null ? null : 2)) },
    month: { year, month: 11, day: 2, count: 3, last_year_count: null, last_year_through: `${year - 1}-11-02`, ahead: null },
    today_counts: true, ranking: [{ rank: 1, start: `${year}-01-01`, end: `${year}-01-12`, length: 12, current: false }, { rank: 2, start: `${year}-02-01`, end: `${year}-02-03`, length: 3, current: false }],
    ranking_year: [], current: { length: 0, rank: null, total: 2, rank_year: null, total_year: 0 },
  };
  await page.route(/\/api\/workout\//, (route) => {
    const p = new URL(route.request().url()).pathname;
    const rows = p.endsWith('/calendar') ? days : p.endsWith('/progress') ? [{ id: today, ...snap }] : [];
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(ds(rows)) });
  });
  await page.goto('/workout/performance');
  await expect(page.getByRole('img', { name: /Activity calendar/ })).toBeVisible();
  await expect(page.getByText('Your monthly race')).toBeVisible();
  await expect(page.getByText(/CHAMPIONS LEAGUE/)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: '/tmp/wt-shots/performance.png', fullPage: true });
});
