/**
 * UI tests - RunningTracker web (mobile viewport).
 *
 * Runs against the deployed shell (http://atlas-shell) in the shared atlas-playwright container.
 * The live database has no fixture world, so RunningTracker API responses are stubbed with page.route;
 * the UI under test is the real bundle. The request bodies the UI sends are asserted.
 */

import { test, expect, type Page, type Route } from '@playwright/test';

test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

const RUN_SYNCED = 'a0000000-0000-0000-0000-000000000001';
const RUN_PENDING = 'a0000000-0000-0000-0000-000000000002';
const RUN_NO_HR = 'a0000000-0000-0000-0000-000000000003';

const json = (route: Route, body: unknown, status = 200) =>
  route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
const dataset = (object_type: string, rows: unknown[], schema: unknown[] = []) =>
  ({ meta: { object_type, label: object_type, total: rows.length, page: 1, page_size: Math.max(rows.length, 1), row_actions: [] }, schema, rows });
const col = (key: string, type = 'number') => ({ key, label: key, type });

const run = (over: Record<string, unknown>) => ({
  id: RUN_SYNCED, run_type: 'continuous', status: 'complete', sync_state: 'synced',
  started_at: '2030-01-07T08:00:00Z', finished_at: '2030-01-07T08:30:00Z', elapsed_s: 1800, moving_s: 1750,
  distance_m: 5000, avg_pace_s_per_km: 350, avg_hr: 151.4, max_hr: 172, avg_cadence_spm: null, comment: 'tempo', device_name: 'Pixel',
  location_count: 1800, hr_count: 1790, ...over,
});

const series = (n: number) => dataset('run_series', Array.from({ length: n }, (_, i) => ({
  id: String(i), t_s: i * 5, t_label: `0:00:${String(i * 5).padStart(2, '0')}`, value: 300 + i,
})), [col('t_s'), col('t_label', 'string'), col('value')]);

async function stubHistory(page: Page, rows: unknown[]) {
  await page.route('**/api/runningtracker/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api/runningtracker', '');
    if (path === '/runs') return json(route, dataset('run', rows));
    return json(route, dataset('x', []));
  });
}

test('history list shows sync state', async ({ page }) => {
  await stubHistory(page, [
    run({}),
    run({ id: RUN_PENDING, status: 'uploading', sync_state: 'pending', started_at: '2030-01-06T08:00:00Z', avg_hr: null, moving_s: null, distance_m: 3200, elapsed_s: 1000, avg_pace_s_per_km: null }),
  ]);
  await page.goto('/running');
  await page.getByText('History', { exact: true }).first().click();
  await expect(page).toHaveURL(/\/running\/history$/);

  const rows = page.getByTestId('run-row');
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(0)).toContainText('Synced');
  await expect(rows.nth(0)).toContainText('5.00 km');
  await expect(rows.nth(0)).toContainText('30:00');
  await expect(rows.nth(0)).toContainText('5:50 /km');
  await expect(rows.nth(0)).toContainText('151 bpm');
  await expect(rows.nth(1)).toContainText('Pending sync');
  await expect(rows.nth(1)).toContainText('3.20 km');
  await expect(rows.nth(1).getByText('Avg HR').locator('..')).toContainText('–');
});

test('history shows an empty state', async ({ page }) => {
  await stubHistory(page, []);
  await page.goto('/running/history');
  await expect(page.getByTestId('empty-history')).toBeVisible();
  await expect(page.getByTestId('run-row')).toHaveCount(0);
});

test('run detail shows charts, splits and comment edit', async ({ page }) => {
  const captured: { patch?: any } = {};
  await page.route('**/api/runningtracker/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace('/api/runningtracker', '');
    const method = route.request().method();
    if (path === `/runs/${RUN_NO_HR}` && method === 'GET') return json(route, dataset('run', [run({ id: RUN_NO_HR, avg_hr: null, max_hr: null, hr_count: 0, comment: 'easy' })]));
    if (path === `/runs/${RUN_NO_HR}` && method === 'PATCH') { captured.patch = route.request().postDataJSON(); return json(route, dataset('run', [run({ id: RUN_NO_HR, avg_hr: null, comment: null })])); }
    if (path === `/runs/${RUN_NO_HR}/splits`) return json(route, dataset('run_split', [
      { id: '1', km: 1, distance_m: 1000, duration_s: 340, pace_s_per_km: 340, avg_hr: null, partial: false },
      { id: '2', km: 2, distance_m: 640, duration_s: 230, pace_s_per_km: 359.4, avg_hr: null, partial: true },
    ]));
    if (path === `/runs/${RUN_NO_HR}/series` && url.searchParams.get('metric') === 'pace') return json(route, series(8));
    if (path === `/runs/${RUN_NO_HR}/series`) return json(route, dataset('run_series', [], [col('t_s'), col('t_label', 'string'), col('value')]));
    return json(route, dataset('x', []));
  });

  await page.goto(`/running/history/${RUN_NO_HR}`);
  await expect(page.getByTestId('pace-chart').locator('svg').first()).toBeVisible();   // pace chart
  await expect(page.getByTestId('hr-chart')).toContainText('No heart-rate data');       // no HR: neutral note
  const splits = page.getByTestId('splits');
  await expect(splits.locator('tbody tr')).toHaveCount(2);
  await expect(splits).toContainText('5:40 /km');
  await expect(page.locator('canvas, .leaflet-container, [class*="map"]')).toHaveCount(0); // no map

  const box = page.getByLabel('Comment');
  await expect(box).toHaveValue('easy');
  await box.fill('');
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await expect.poll(() => captured.patch).toEqual({ comment: null, category: null }); // cleared fields are null, not omitted or ""
});

test('pair phone shows code, QR and expiry; revoke only on active devices', async ({ page }) => {
  let revoked: string | null = null;
  const devices = () => dataset('device', [
    { id: 'd-active', name: 'Pixel 8', created_at: '2030-01-01T00:00:00Z', last_used_at: '2030-01-05T10:00:00Z', revoked_at: null, is_revoked: false },
    { id: 'd-old', name: 'Old phone', created_at: '2029-01-01T00:00:00Z', last_used_at: null, revoked_at: '2029-06-01T00:00:00Z', is_revoked: true },
  ]);
  await page.route('**/api/runningtracker/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api/runningtracker', '');
    if (path === '/devices') return json(route, devices());
    if (path === '/devices/d-active/revoke') { revoked = 'd-active'; return json(route, dataset('device', [])); }
    if (path === '/pairing-codes') {
      const expires = new Date(Date.now() + 4000).toISOString(); // short TTL so the test can see it expire
      return json(route, dataset('pairing_code', [{ id: 'c1', code: 'K7M2QX9A', expires_at: expires, native_base_url: 'https://atlas.example.ts.net:8443' }]), 201);
    }
    return json(route, dataset('x', []));
  });

  await page.goto('/running/devices');
  await expect(page.getByTestId('device')).toHaveCount(2);
  await expect(page.getByRole('button', { name: 'Revoke Pixel 8' })).toBeVisible();
  await expect(page.getByRole('button', { name: /Revoke Old phone/ })).toHaveCount(0);
  await expect(page.getByTestId('device').nth(1)).toContainText('Revoked');

  await page.getByRole('button', { name: 'Pair phone' }).click();
  const code = page.getByTestId('pairing-code');
  await expect(code).toContainText('K7M2QX9A');
  await expect(code.locator('svg')).toBeVisible();     // QR
  await expect(code).toContainText('Expires in');
  await expect(page.getByTestId('pairing-code')).toHaveCount(0, { timeout: 8000 }); // disappears when expired

  await page.getByRole('button', { name: 'Revoke Pixel 8' }).click();
  await expect.poll(() => revoked).toBe('d-active');
});

test('prepared runs on the Run page: create, delete, expired marked, Free Run explained', async ({ page }) => {
  let rows: any[] = [
    { id: 'p-old', short_id: 'OLDONE', title: 'Old plan', planned_for: null, expires_at: '2020-01-01T00:00:00Z', is_expired: true, created_at: '2019-12-30T00:00:00Z' },
  ];
  const captured: { create?: any; deleted?: string } = {};
  await page.route('**/api/runningtracker/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api/runningtracker', '');
    const method = route.request().method();
    if (path === '/prepared-runs' && method === 'GET') return json(route, dataset('prepared_run', rows));
    if (path === '/prepared-runs' && method === 'POST') {
      captured.create = route.request().postDataJSON();
      const created = { id: 'p-new', short_id: 'ABC234', title: captured.create.title, planned_for: null, expires_at: '2099-01-01T00:00:00Z', is_expired: false, created_at: '2030-01-01T00:00:00Z' };
      rows = [created, ...rows];
      return json(route, dataset('prepared_run', [created]), 201);
    }
    if (method === 'DELETE') { captured.deleted = path; rows = rows.filter((r) => `/runs/${r.id}` !== path); return json(route, dataset('run', [])); }
    return json(route, dataset('x', []));
  });

  await page.goto('/running');
  await expect(page.getByText('Free Run is started on the phone')).toBeVisible();
  await expect(page.getByTestId('prepared-run')).toHaveCount(1);
  await expect(page.getByTestId('prepared-run').first()).toContainText('Expired');

  await page.getByLabel('Title').fill('Sunday long');
  await page.getByRole('button', { name: 'Prepare run' }).click();
  await expect(page.getByTestId('prepared-run')).toHaveCount(2);
  expect(captured.create).toEqual({ title: 'Sunday long', route_id: null, ghost: 'none' });
  await expect(page.getByTestId('prepared-run').first()).toContainText('Sunday long');

  await page.getByRole('button', { name: 'Delete Sunday long' }).click();
  await expect(page.getByTestId('prepared-run')).toHaveCount(1);
  expect(captured.deleted).toBe('/runs/p-new');
});

test('[UI] routes page lists routes with distance, runs and best time; empty state', async ({ page }) => {
  let routes: unknown[] = [{
    id: 'r-1', name: 'Stadtpark Small', description: 'near loop', reference_distance_m: 4150, is_loop: true,
    run_count: 2, latest_run_at: '2026-11-06T13:49:56Z', best_moving_s: 1936, created_at: '2026-11-08T10:00:00Z',
  }];
  await page.route('**/api/runningtracker/routes', (route) => json(route, dataset('route', routes)));
  await page.goto('/running/routes');
  const row = page.getByTestId('route-row');
  await expect(row).toHaveCount(1);
  await expect(row).toContainText('Stadtpark Small');
  await expect(row).toContainText('Loop');
  await expect(row).toContainText('4.15 km');
  await expect(row).toContainText('32:16');

  routes = [];
  await page.reload();
  await expect(page.getByTestId('empty-routes')).toBeVisible();
});


test('[UI] prepare a run on a route with a ghost: latest, fastest or a specific run', async ({ page }) => {
  let created: any = null;
  await page.route('**/api/runningtracker/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api/runningtracker', '');
    const method = route.request().method();
    if (path === '/routes') return json(route, dataset('route', [{ id: 'r-1', name: 'Stadtpark Small', description: null, reference_distance_m: 4217, is_loop: true, run_count: 2, latest_run_at: null, best_moving_s: 1936, created_at: '2026-11-08T10:00:00Z' }]));
    if (path === '/routes/r-1/runs') return json(route, dataset('route_run', [
      { id: 'g-2', started_at: '2026-11-06T13:49:56Z', moving_s: 1936, category: 'Easy Continuous', ghost_eligible: true, is_latest: true, is_fastest: true },
      { id: 'g-1', started_at: '2026-10-01T13:00:00Z', moving_s: 2100, category: null, ghost_eligible: true, is_latest: false, is_fastest: false },
      { id: 'g-0', started_at: '2026-09-01T13:00:00Z', moving_s: 1800, category: null, ghost_eligible: false, is_latest: false, is_fastest: false },
    ]));
    if (path === '/prepared-runs' && method === 'POST') {
      created = route.request().postDataJSON();
      return json(route, dataset('prepared_run', [{ id: 'p-1', short_id: 'ABC234', title: null, planned_for: null, expires_at: '2099-01-01T00:00:00Z', is_expired: false, created_at: '2030-01-01T00:00:00Z', route_name: 'Stadtpark Small', ghost_label: '2026-11-06 · 32:16' }]), 201);
    }
    return json(route, dataset('prepared_run', []));
  });
  await page.goto('/running');
  await expect(page.getByLabel('Ghost runner')).toHaveCount(0);          // no route, no ghost choice
  await page.getByLabel('Route').selectOption('r-1');
  const ghost = page.getByLabel('Ghost runner');
  await expect(ghost.locator('option')).toHaveCount(5);                  // none, latest, fastest and the 2 eligible runs (not g-0)
  await ghost.selectOption('fastest');
  await page.getByRole('button', { name: 'Prepare run' }).click();
  await expect.poll(() => created).toEqual({ title: null, route_id: 'r-1', ghost: 'fastest' });
});


test('run detail shows the Recovery card', async ({ page }) => {
  await page.route('**/api/runningtracker/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace('/api/runningtracker', '');
    const metric = url.searchParams.get('metric');
    if (path === `/runs/${RUN_SYNCED}`) return json(route, dataset('run', [run({})]));
    if (path === `/runs/${RUN_SYNCED}/splits`) return json(route, dataset('run_split', [
      { id: '1', km: 1, distance_m: 1000, duration_s: 340, pace_s_per_km: 340, avg_hr: 150, partial: false }]));
    if (path === `/runs/${RUN_SYNCED}/recovery`) return json(route, dataset('run_recovery', [
      { id: RUN_SYNCED, run_finished_at: '2030-01-07T08:30:00Z', recovery_s: 180, hr_end: 172, hr_60: 150, hr_120: 138, hrr60: 22, hrr120: 34 }]));
    if (path === `/runs/${RUN_SYNCED}/series` && metric === 'recovery_hr') return json(route, series(8));
    if (path === `/runs/${RUN_SYNCED}/series`) return json(route, series(8));
    return json(route, dataset('x', []));
  });
  await page.goto(`/running/history/${RUN_SYNCED}`);
  const card = page.getByTestId('recovery-card');
  await expect(card).toBeVisible();
  await expect(page.getByTestId('hrr60')).toHaveText('22 bpm');
  await expect(page.getByTestId('hrr120')).toHaveText('34 bpm');
  await expect(card).toContainText('172 bpm');
  await expect(card).toContainText('150 bpm');
  await expect(card).toContainText('138 bpm');
  await expect(card.locator('svg').first()).toBeVisible();                       // recovery chart
  await expect(card).toContainText('HRR is the drop after exercise, not the return to resting heart rate.');
  await expect(page.getByTestId('pace-chart').locator('svg').first()).toBeVisible(); // existing cards are still there
  await expect(page.getByTestId('hr-chart').locator('svg').first()).toBeVisible();
  await expect(page.getByTestId('splits').locator('tbody tr')).toHaveCount(1);
  await expect(page.getByLabel('Comment')).toHaveValue('tempo');
});

test('run detail hides the Recovery card without recovery and shows null values as a dash', async ({ page }) => {
  let withRow = false;
  await page.route('**/api/runningtracker/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace('/api/runningtracker', '');
    if (path === `/runs/${RUN_SYNCED}`) return json(route, dataset('run', [run({})]));
    if (path === `/runs/${RUN_SYNCED}/recovery`) return json(route, dataset('run_recovery', withRow ? [
      { id: RUN_SYNCED, run_finished_at: '2030-01-07T08:30:00Z', recovery_s: 30, hr_end: 170, hr_60: null, hr_120: null, hrr60: null, hrr120: null }] : []));
    return json(route, dataset('x', []));
  });
  await page.goto(`/running/history/${RUN_SYNCED}`);
  await expect(page.getByTestId('pace-chart')).toBeVisible();
  await expect(page.getByTestId('recovery-card')).toHaveCount(0);
  await expect(page.getByText(/error/i)).toHaveCount(0);

  withRow = true;
  await page.reload();
  await expect(page.getByTestId('recovery-card')).toBeVisible();
  await expect(page.getByTestId('hrr60')).toHaveText('–');
  await expect(page.getByTestId('hrr120')).toHaveText('–');
  await expect(page.getByTestId('recovery-card')).toContainText('170 bpm');
});


test('run detail shows cadence stat and card', async ({ page }) => {
  await page.route('**/api/runningtracker/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace('/api/runningtracker', '');
    const metric = url.searchParams.get('metric');
    if (path === `/runs/${RUN_SYNCED}`) return json(route, dataset('run', [run({ avg_cadence_spm: 170.6 })]));
    if (path === `/runs/${RUN_SYNCED}/splits`) return json(route, dataset('run_split', [
      { id: '1', km: 1, distance_m: 1000, duration_s: 340, pace_s_per_km: 340, avg_hr: 150, partial: false }]));
    if (path === `/runs/${RUN_SYNCED}/series` && metric === 'cadence') return json(route, series(8));
    if (path === `/runs/${RUN_SYNCED}/series`) return json(route, series(8));
    return json(route, dataset('x', []));
  });
  await page.goto(`/running/history/${RUN_SYNCED}`);
  await expect(page.getByTestId('avg-cadence')).toHaveText('171 spm');
  await expect(page.getByTestId('cadence-chart').locator('svg').first()).toBeVisible();
  await expect(page.getByTestId('pace-chart').locator('svg').first()).toBeVisible();
  await expect(page.getByTestId('hr-chart').locator('svg').first()).toBeVisible();
  await expect(page.getByTestId('splits').locator('tbody tr')).toHaveCount(1);
  await expect(page.getByLabel('Comment')).toHaveValue('tempo');
});

test('run detail without cadence shows a dash and the neutral note', async ({ page }) => {
  await page.route('**/api/runningtracker/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace('/api/runningtracker', '');
    const metric = url.searchParams.get('metric');
    if (path === `/runs/${RUN_SYNCED}`) return json(route, dataset('run', [run({ avg_cadence_spm: null })]));
    if (path === `/runs/${RUN_SYNCED}/splits`) return json(route, dataset('run_split', []));
    if (path === `/runs/${RUN_SYNCED}/series` && metric === 'cadence') return json(route, dataset('run_series', [], [col('t_s'), col('t_label', 'string'), col('value')]));
    if (path === `/runs/${RUN_SYNCED}/series`) return json(route, series(8));
    return json(route, dataset('x', []));
  });
  await page.goto(`/running/history/${RUN_SYNCED}`);
  await expect(page.getByTestId('avg-cadence')).toHaveText('–');
  await expect(page.getByTestId('cadence-chart')).toContainText('No cadence recorded.');
  await expect(page.getByTestId('pace-chart').locator('svg').first()).toBeVisible();
  await expect(page.getByLabel('Comment')).toHaveValue('tempo');
});

// ---- Sprint04 Ghost Coach ([UI] scenarios; the API is stubbed) ----------------------------------------------------

const analysisRow = (over: Record<string, unknown> = {}) => ({
  id: RUN_SYNCED, run_id: RUN_SYNCED, assessment: 'Steady run, heart rate drifted up late.', previous_effect: 'You followed the easy plan.',
  plan_rejected_reason: null, plan_id: 'p1', prompt_version: 'v1', model: 'm', analysed_at: '2030-01-07T09:00:00Z', ...over,
});

async function stubRunDetail(page: Page, coach: (path: string, method: string, route: Route) => Promise<boolean> | boolean) {
  await page.route('**/api/runningtracker/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace('/api/runningtracker', '');
    if (await coach(path, route.request().method(), route)) return;
    if (path === `/runs/${RUN_SYNCED}`) return json(route, dataset('run', [run({})]));
    if (path === `/runs/${RUN_SYNCED}/splits`) return json(route, dataset('run_split', []));
    return json(route, dataset('x', []));
  });
}

test('[UI] run detail shows the stored assessment as plain text', async ({ page }) => {
  await stubRunDetail(page, (path, _m, route) => {
    if (path === `/coach/runs/${RUN_SYNCED}/analysis`) { json(route, dataset('coach_analysis', [analysisRow({ assessment: '<b>bold</b> steady' })])); return true; }
    return false;
  });
  await page.goto(`/running/history/${RUN_SYNCED}`);
  await expect(page.getByTestId('coach-assessment')).toHaveText('<b>bold</b> steady');
  await expect(page.getByTestId('coach-previous')).toContainText('You followed the easy plan.');
  await expect(page.getByRole('button', { name: 'Analyse run' })).toHaveCount(0);
});

test('[UI] analyse run with consent missing disables the button while pending and links to the Coach page', async ({ page }) => {
  let release: () => void = () => {};
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await stubRunDetail(page, async (path, method, route) => {
    if (path === `/coach/runs/${RUN_SYNCED}/analysis` && method === 'POST') {
      await gate;
      await json(route, { error: { code: 'CONSENT_REQUIRED', message: 'Enable AI first.', request_id: 'r1' } }, 403);
      return true;
    }
    return false;
  });
  await page.goto(`/running/history/${RUN_SYNCED}`);
  const button = page.getByRole('button', { name: 'Analyse run' });
  await button.click();
  await expect(page.getByRole('button', { name: 'Analysing...' })).toBeDisabled();
  release();
  await expect(page.getByTestId('coach-error')).toContainText('Enable AI first.');
  await expect(page.getByTestId('coach-error').getByRole('link', { name: 'Go to the Coach page' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Analyse run' })).toBeEnabled();
});

test('[UI] analyse run success shows the assessment and a pointer to the Coach page; a 502 keeps the button usable', async ({ page }) => {
  let calls = 0;
  await stubRunDetail(page, (path, method, route) => {
    if (path === `/coach/runs/${RUN_SYNCED}/analysis` && method === 'POST') {
      calls += 1;
      if (calls === 1) json(route, { error: { code: 'AI_UNAVAILABLE', message: 'The AI provider is unavailable.', request_id: 'r2' } }, 502);
      else json(route, dataset('coach_analysis', [analysisRow()]));
      return true;
    }
    return false;
  });
  await page.goto(`/running/history/${RUN_SYNCED}`);
  await page.getByRole('button', { name: 'Analyse run' }).click();
  await expect(page.getByTestId('coach-error')).toContainText('The AI provider is unavailable.');
  await page.getByRole('button', { name: 'Analyse run' }).click();
  await expect(page.getByTestId('coach-assessment')).toContainText('heart rate drifted');
  await expect(page.getByTestId('coach-card').getByRole('link', { name: 'Open the Coach page' })).toBeVisible();
  await expect(page.getByTestId('coach-error')).toHaveCount(0);
});

const settings = (over: Record<string, unknown> = {}) => dataset('coach_settings', [{
  id: 'settings', ai_enabled: false, consent_current: false, consent_version_required: 3, consented_at: null, goal_text: null,
  key_configured: true, destination_host: 'api.anthropic.com', model: 'm', payload_version: 1, prompt_version: 'v1',
  calls_last_24h: 0, daily_cap: 10, ...over }]);
const planRow = (over: Record<string, unknown> = {}) => ({
  id: 'p1', status: 'recommended', plan_type: 'easy_continuous', title: 'Easy 40', summary: 'Easy continuous - 40 min - HR 130-145',
  rationale: 'Keep it relaxed.', total_s: 2400, target_distance_m: null, hr_min: 130, hr_max: 145, pace_fast_s_per_km: 330,
  pace_slow_s_per_km: 390, cad_min: 165, cad_max: 175, segment_count: 3, created_at: '2030-01-07T09:00:00Z', decided_at: null,
  run_id: null, outcome_summary: null, ...over });

interface CoachStub { settings?: unknown; plan?: unknown[]; plans?: unknown[]; profile?: unknown[]; captured: { patch?: any; plan?: any } }
async function stubCoach(page: Page, s: CoachStub) {
  await page.route('**/api/runningtracker/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace('/api/runningtracker', '');
    const method = route.request().method();
    if (path === '/coach/settings' && method === 'GET') return json(route, s.settings ?? settings());
    if (path === '/coach/settings' && method === 'PATCH') { s.captured.patch = route.request().postDataJSON(); return json(route, settings({ ai_enabled: true, consent_current: true })); }
    if (path === '/coach/next-session') return json(route, dataset('coach_plan', s.plan ?? []));
    if (path === '/coach/plans' && method === 'GET') return json(route, dataset('coach_plan', s.plans ?? s.plan ?? []));
    if (path.startsWith('/coach/plans/') && method === 'PATCH') { s.captured.plan = route.request().postDataJSON(); return json(route, dataset('coach_plan', [planRow({ status: 'accepted' })])); }
    if (path === '/coach/profile') return json(route, dataset('coach_profile_item', s.profile ?? []));
    if (path === '/coach/analysis-preview') return json(route, dataset('coach_preview', [{ id: RUN_SYNCED, destination_host: 'api.anthropic.com', model: 'm', prompt_version: 'v1', payload_version: 1, history_runs: 2, byte_size: 1234, payload_json: '{\n  "payload_version": 1\n}' }]));
    if (path === '/runs') return json(route, dataset('run', [run({})]));
    return json(route, dataset('x', []));
  });
}

test('[UI] consent flow: destination, data categories, preview, enabling sends the current consent version', async ({ page }) => {
  const s: CoachStub = { captured: {} };
  await stubCoach(page, s);
  await page.goto('/running/coach');
  const card = page.getByTestId('consent-card');
  await expect(card).toContainText('api.anthropic.com');
  await expect(page.getByTestId('sent-categories')).toContainText('per-kilometre splits');
  await expect(page.getByTestId('never-sent')).toContainText('GPS coordinates');
  await expect(page.getByTestId('ai-state')).toHaveText('AI off');
  await page.getByRole('button', { name: 'Show what would be sent' }).click();
  await expect(page.getByTestId('payload-preview')).toContainText('"payload_version": 1');
  await page.getByRole('button', { name: 'Enable AI analysis' }).click();
  await expect.poll(() => s.captured.patch).toEqual({ ai_enabled: true, consent_version: 3 });
});

test('[UI] consent toggle is disabled with an explanation when no key is configured', async ({ page }) => {
  await stubCoach(page, { captured: {}, settings: settings({ key_configured: false }) });
  await page.goto('/running/coach');
  await expect(page.getByRole('button', { name: 'Enable AI analysis' })).toBeDisabled();
  await expect(page.getByTestId('not-configured')).toBeVisible();
});

test('[UI] accept sends no overrides; disregard sends the status', async ({ page }) => {
  const s: CoachStub = { captured: {}, plan: [planRow()] };
  await stubCoach(page, s);
  await page.goto('/running/coach');
  await expect(page.getByTestId('plan-title')).toHaveText('Easy 40');
  await page.getByRole('button', { name: 'Accept', exact: true }).click();
  await expect.poll(() => s.captured.plan).toEqual({ status: 'accepted' });
  await page.getByRole('button', { name: 'Disregard' }).click();
  await expect.poll(() => s.captured.plan).toEqual({ status: 'disregarded' });
});

test('[UI] modify sends the cadence object, null for cleared fields and omits untouched fields', async ({ page }) => {
  const s: CoachStub = { captured: {}, plan: [planRow()] };
  await stubCoach(page, s);
  await page.goto('/running/coach');
  await page.getByRole('button', { name: 'Modify' }).click();
  await page.getByLabel('Cadence min').fill('170');
  await page.getByLabel('Cadence max').fill('180');
  await page.getByLabel('Pace fast (s/km)').fill('');
  await page.getByLabel('Pace slow (s/km)').fill('');
  await page.getByRole('button', { name: 'Accept with changes' }).click();
  await expect.poll(() => s.captured.plan).toEqual({ status: 'accepted', overrides: { cadence: { min: 170, max: 180 }, pace: null } });
});

test('[UI] no recommended session shows the empty state', async ({ page }) => {
  await stubCoach(page, { captured: {}, plan: [] });
  await page.goto('/running/coach');
  await expect(page.getByTestId('no-session')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Accept', exact: true })).toHaveCount(0);
});

test('[UI] profile lists measured before inferred with confidence; plan history shows status and outcome', async ({ page }) => {
  await stubCoach(page, {
    captured: {}, plan: [],
    plans: [planRow({ id: 'p2', status: 'completed', title: 'Done plan', outcome_summary: 'completed, 40/40 min, HR in range 82%' })],
    profile: [
      { id: 'natural_cadence_spm', label: 'Natural cadence', basis: 'measured', value_text: '170 spm', confidence: null, n_runs: 4 },
      { id: 'aerobic_endurance', label: 'Aerobic endurance', basis: 'inferred', value_text: 'Building', confidence: 0.5, n_runs: 4 },
    ],
  });
  await page.goto('/running/coach');
  const rows = page.getByTestId('profile').locator('tbody tr');
  await expect(rows.nth(0)).toContainText('measured');
  await expect(rows.nth(0)).toContainText('–');
  await expect(rows.nth(1)).toContainText('inferred');
  await expect(rows.nth(1)).toContainText('50%');
  await expect(page.getByTestId('plan-history')).toContainText('completed, 40/40 min, HR in range 82%');
});
