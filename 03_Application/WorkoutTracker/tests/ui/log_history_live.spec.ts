/**
 * UI tests — WorkoutTracker — P1 on REAL data, strictly read-only.
 *
 * Browses the live Log, an exercise history (both chart modes, column selection) and a session
 * detail. The test fails if the app issues ANY non-GET request to /api/workout, so it can never
 * create or modify a workout. Safe to run while a workout is active.
 * Screenshots go to /tmp/wt-shots inside the container.
 */

import { test, expect } from '@playwright/test';

test.use({ viewport: { width: 393, height: 800 }, hasTouch: true, isMobile: true });

test('live data: browse log, history, session detail without writing', async ({ page }) => {
  const writes: string[] = [];
  page.on('request', (r) => {
    if (r.url().includes('/api/workout') && r.method() !== 'GET') writes.push(`${r.method()} ${new URL(r.url()).pathname}`);
  });

  await page.goto('/workout/log');
  await expect(page.getByRole('heading', { name: 'Log' })).toBeVisible();
  await expect(page.getByRole('article').first()).toBeVisible();
  await page.waitForTimeout(500);
  await page.screenshot({ path: '/tmp/wt-shots/live_1_log.png' });

  // open the first exercise of the first session → history
  const firstRow = page.getByRole('article').first().getByRole('list').getByRole('button').first();
  await firstRow.click();
  await expect(page).toHaveURL(/\/workout\/log\/exercise\?name=/);
  const cols = page.getByRole('group', { name: /recorded sessions/ }).getByRole('button');
  await expect(cols.first()).toBeVisible();
  const n = await cols.count();
  expect(n).toBeGreaterThan(0);
  await page.screenshot({ path: '/tmp/wt-shots/live_2_history_sessions.png' });

  await page.getByRole('button', { name: 'Timeline', exact: true }).click();
  await expect(cols).toHaveCount(n); // same occurrences in both modes
  await cols.last().click();
  await expect(page.getByRole('region', { name: 'Selected session' })).toBeVisible();
  await page.screenshot({ path: '/tmp/wt-shots/live_3_history_timeline.png' });

  await page.getByRole('region', { name: 'Selected session' }).getByRole('button', { name: 'Open session' }).click();
  await expect(page).toHaveURL(/\/workout\/log\/[0-9a-f-]{36}$/);
  await expect(page.getByRole('button', { name: 'Edit', exact: true })).toBeVisible();
  await page.screenshot({ path: '/tmp/wt-shots/live_4_session_detail.png' });

  expect(writes, 'live browsing must be read-only').toEqual([]);
});
