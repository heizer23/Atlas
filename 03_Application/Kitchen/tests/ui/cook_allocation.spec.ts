/**
 * UI tests — Kitchen — cooked batch management (mobile viewport).
 *
 * Runs against the deployed shell (http://atlas-shell) in the shared atlas-playwright container.
 * The live database has no fixture world, so Kitchen API responses are stubbed with page.route;
 * the UI under test is the real bundle. The request bodies the UI sends are asserted.
 */

import { test, expect, type Page, type Route } from '@playwright/test';

test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

const PLAN_ID = 'a0000000-0000-0000-0000-000000000001';
const COOK_ID = 'a0000000-0000-0000-0000-0000000000c1';
const EAT_ID = 'a0000000-0000-0000-0000-0000000000e1';
const DAL_ID = 'b0000000-0000-0000-0000-0000000000d1';

const dataset = (rows: unknown[]) => ({ meta: { object_type: 'x', total: rows.length, page: 1, page_size: rows.length }, schema: [], rows });
const json = (route: Route, body: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

const meal = (over: Record<string, unknown>) => ({
  id: COOK_ID, plan_id: PLAN_ID, recipe_id: DAL_ID, recipe_name: 'Coconut Lentil Dal', recipe_kind: 'base', kind: 'cook',
  day: '2030-01-07', slot: 'dinner', portions: 4, status: 'planned', produced_qty: null, batch_item_id: null,
  recipe_servings: 4, shelf_life_days: 4, freezer_shelf_life_days: null, thawed_shelf_life_days: null,
  expiry_warning: null, bases: [], ...over,
});

const batch = (over: Record<string, unknown>) => ({
  id: 1, name: 'Coconut Lentil Dal 2030-01-07', recipe_id: DAL_ID, quantity: 2, unit: 'portions', location: 'Fridge',
  storage: 'fridge', expires_at: '2099-01-11', expiry_status: null, produced_at: '2030-01-07',
  suggested_freeze_expires_at: null, suggested_thaw_expires_at: null, ...over,
});

async function stub(page: Page, meals: unknown[], batches: unknown[], captured: { cooked?: any; thaw?: any } = {}) {
  await page.route('**/api/kitchen/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace('/api/kitchen', '');
    if (path === '/plans') return json(route, dataset([{ id: PLAN_ID, week_start: '2030-01-07', days: 3 }]));
    if (path === `/plans/${PLAN_ID}`) return json(route, dataset([{ id: PLAN_ID, week_start: '2030-01-07', days: 3, meals }]));
    if (path === '/recipes') return json(route, dataset([{ id: DAL_ID, name: 'Coconut Lentil Dal', kind: 'base', status: 'active', servings: 4, yield_unit: 'portions' }]));
    if (path === '/batches') return json(route, dataset(batches));
    if (path === `/meals/${COOK_ID}/cooked`) { captured.cooked = route.request().postDataJSON(); return json(route, { replayed: false }); }
    if (/\/batches\/\d+\/thaw$/.test(path)) { captured.thaw = route.request().postDataJSON(); return json(route, dataset([{}])); }
    return json(route, dataset([]));
  });
}

test('cooking dialog splits portions between fridge and freezer and requires the freezer shelf life', async ({ page }) => {
  const captured: { cooked?: any } = {};
  await stub(page, [meal({})], [], captured);
  await page.goto('/kitchen');

  await page.getByRole('button', { name: 'Cooked…' }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText('Coconut Lentil Dal')).toBeVisible();
  await expect(dialog.getByText('Refrigerator', { exact: true })).toBeVisible();
  await expect(dialog.getByText('Freezer', { exact: true })).toBeVisible();
  await expect(dialog.getByText('Short-term storage')).toBeVisible();
  await expect(dialog.getByText('Long-term storage')).toBeVisible();
  await expect(dialog.getByText('4 / 4')).toBeVisible();

  // mobile: the sheet fits the viewport width and the save button is reachable
  const box = await dialog.locator('.kitchen-sheet').boundingBox();
  expect(box!.width).toBeLessThanOrEqual(390);
  await page.screenshot({ path: '/tmp/playwright-results/kitchen-cook-dialog.png' });

  // move two portions to the freezer: allocation stays exactly 4 / 4, but the freezer needs its shelf life
  const more = dialog.getByRole('button', { name: 'Freezer portions: more' });
  await more.click(); await more.click();
  await expect(dialog.getByText('4 / 4')).toBeVisible();
  await expect(dialog.getByText('Enter the freezer shelf life')).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Save cooking' })).toBeDisabled();

  await dialog.getByLabel('Freezer shelf life in days').fill('60');
  await expect(dialog.getByRole('button', { name: 'Save cooking' })).toBeEnabled();
  await dialog.getByRole('button', { name: 'Save cooking' }).click();

  await expect.poll(() => captured.cooked).toBeTruthy();
  expect(captured.cooked.produced_qty).toBe(4);
  expect(captured.cooked.allocations).toEqual([
    { location: 'fridge', qty: 2, shelf_life_days: 4 },
    { location: 'freezer', qty: 2, shelf_life_days: 60 },
  ]);
  expect(captured.cooked.remember_shelf_life).toBe(true);   // recipe had no freezer default
});

test('all portions in the fridge needs no freezer data; produced amount can be corrected', async ({ page }) => {
  const captured: { cooked?: any } = {};
  await stub(page, [meal({})], [], captured);
  await page.goto('/kitchen');
  await page.getByRole('button', { name: 'Cooked…' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('Portions produced').fill('3');
  await expect(dialog.getByText('3 / 3')).toBeVisible();
  await dialog.getByRole('button', { name: 'Save cooking' }).click();
  await expect.poll(() => captured.cooked).toBeTruthy();
  expect(captured.cooked.produced_qty).toBe(3);
  expect(captured.cooked.allocations).toEqual([{ location: 'fridge', qty: 3, shelf_life_days: 4 }]);
});

test('batches show their location; frozen batches must be thawed with an explicit date; meals show availability', async ({ page }) => {
  const captured: { thaw?: any } = {};
  const eat = meal({
    id: EAT_ID, recipe_id: null, recipe_name: 'Dal with Eggs and Spinach', recipe_kind: 'derived', kind: 'meal', portions: 2,
    bases: [{ base_recipe_id: DAL_ID, name: 'Coconut Lentil Dal', needed: 2, ready: 0, frozen: 2, planned_cook: 0, status: 'needs_thaw' }],
  });
  await stub(page, [eat], [
    batch({ id: 1, storage: 'fridge', location: 'Fridge', quantity: 1 }),
    batch({ id: 2, storage: 'freezer', location: 'Freezer', quantity: 2, expires_at: '2099-03-01', suggested_thaw_expires_at: '2099-01-09' }),
  ], captured);
  await page.goto('/kitchen');

  await expect(page.getByText('Coconut Lentil Dal: requires thawing (2 in freezer)')).toBeVisible();
  await expect(page.locator('.kitchen-chip', { hasText: /^Fridge$/ })).toBeVisible();
  await expect(page.locator('.kitchen-chip.frozen')).toBeVisible();
  await expect(page.getByText('thaw before use')).toBeVisible();

  await page.getByRole('button', { name: 'Thaw', exact: true }).click();
  const date = page.getByLabel('New best-before date');
  await expect(date).toHaveValue('2099-01-09');                      // pre-filled from the thawing policy, editable
  await date.fill('');
  await expect(page.getByRole('button', { name: 'Move to refrigerator' })).toBeDisabled();   // never implicit
  await date.fill('2099-01-10');
  await page.getByRole('button', { name: 'Move to refrigerator' }).click();
  await expect.poll(() => captured.thaw).toEqual({ expires_at: '2099-01-10' });
  await page.screenshot({ path: '/tmp/playwright-results/kitchen-batches.png', fullPage: true });
});

test('no horizontal scroll on the plan page at 390px', async ({ page }) => {
  await stub(page, [meal({})], [batch({})]);
  await page.goto('/kitchen');
  await expect(page.getByText('Cooked bases in stock')).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});
