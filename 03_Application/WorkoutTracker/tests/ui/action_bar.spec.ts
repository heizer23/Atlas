/**
 * UI test — the overview's "Add Exercise" / "Finish Workout" bar sits directly above the bottom
 * navigation, for a short list (no scrolling) and a long list (scrolled to the top). Mocked API.
 */
import { test, expect, type Page } from '@playwright/test';

const SID = '77777777-7777-7777-7777-777777777777';
const ex = (i: number) => ({
  id: String(i), exercise: `Exercise number ${i}`, status: 'planned', weight_kg: 20, workout_date: '2026-10-28', split: 'Pull',
  comment: null, total_reps: 0, delta: null, set1_reps: null, set2_reps: null, set3_reps: null, set4_reps: null, set5_reps: null,
});
const ds = (rows: unknown[]) => ({ meta: { object_type: 'x', label: 'x', total: rows.length, page: 1, page_size: rows.length || 1 }, schema: [], rows });

async function mock(page: Page, n: number) {
  await page.route(/\/api\/workout\//, async (route) => {
    const p = new URL(route.request().url()).pathname;
    const json = (b: unknown) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(b) });
    if (route.request().method() !== 'GET') throw new Error(`unexpected write ${p}`);
    if (p.endsWith('/sessions/active')) return json(ds([{ id: SID, split: 'Pull', workout_date: '2026-10-28', started_at: 'x' }]));
    if (p.endsWith(`/sessions/${SID}/exercises`)) return json(ds(Array.from({ length: n }, (_, i) => ex(i + 1))));
    return json(ds([]));
  });
}

test.use({ viewport: { width: 393, height: 800 }, hasTouch: true, isMobile: true });

for (const n of [1, 3, 12]) {
  test(`action bar is pinned above the bottom nav with ${n} exercise(s)`, async ({ page }) => {
    await mock(page, n);
    await page.goto('/workout');
    const finish = page.getByRole('button', { name: 'Finish Workout' });
    await expect(finish).toBeVisible();
    await page.waitForTimeout(400);
    const nav = (await page.locator('.shell-bottom-nav').boundingBox())!;
    const add = (await page.getByRole('button', { name: '+ Add Exercise' }).boundingBox())!;
    const fin = (await finish.boundingBox())!;
    // buttons end just above the nav (bar padding only), never mid-screen or under the nav
    expect(nav.y - (fin.y + fin.height), `gap above nav (n=${n})`).toBeLessThanOrEqual(14);
    expect(nav.y - (fin.y + fin.height)).toBeGreaterThanOrEqual(0);
    expect(add.y + add.height).toBeLessThanOrEqual(nav.y);
    await page.screenshot({ path: `/tmp/wt-shots/bar_${n}.png` });
    // still pinned after scrolling to the bottom of a long list
    await page.locator('.shell-content').evaluate((el) => (el.scrollTop = el.scrollHeight));
    const fin2 = (await finish.boundingBox())!;
    expect(Math.abs(fin2.y - fin.y)).toBeLessThanOrEqual(1);
  });
}
