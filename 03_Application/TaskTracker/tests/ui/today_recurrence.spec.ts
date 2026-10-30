/**
 * UI tests — TaskTracker — Sprint11_TodayAndRecurrence
 *
 * Covers the [UI] scenarios in 10_test_spec.md. Runs against http://atlas-shell via
 * the shared atlas-playwright container, using the live database: every test creates
 * its own tasks (titles prefixed "ui11-") through the API and deletes them afterwards.
 * Assertions on sections/totals are computed from the live agenda response so other
 * real tasks do not break them.
 */

import { test, expect, type Page } from '@playwright/test';

const PREFIX = 'ui11-';

function isoDate(offsetDays: number): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${m}-${day}`;
}

function formatEffort(h: number): string {
  if (h === 0) return '0 h';
  return Number.isInteger(h) ? `${h} h` : `${h.toFixed(1)} h`;
}

async function createTask(page: Page, body: Record<string, unknown>): Promise<string> {
  const res = await page.request.post('/api/tasks', { data: { priority: 'medium', ...body } });
  expect(res.ok(), `create ${JSON.stringify(body)}`).toBeTruthy();
  return (await res.json()).rows[0].id as string;
}

// Row container = parent of the title span inside TaskCard
const card = (page: Page, title: string) => page.getByText(title, { exact: true }).locator('xpath=..');

test.afterEach(async ({ page }) => {
  // Delete every ui11- task, successors included
  const res = await page.request.get('/api/tasks?page_size=500');
  if (!res.ok()) return;
  const rows = (await res.json()).rows as { id: string; title: string }[];
  for (const r of rows.filter(r => r.title.startsWith(PREFIX))) {
    await page.request.delete(`/api/tasks/${r.id}`);
  }
});

test('Today is the default landing tab', async ({ page }) => {
  await page.goto('/tasks');
  const todayNav = page.locator('[aria-current="page"]').filter({ hasText: 'Today' });
  await expect.poll(async () => await todayNav.count()).toBeGreaterThan(0);
  // Agenda renders: either the empty state or at least one section
  await expect(page.locator('[data-testid="today-empty"], [data-testid^="today-section-"]').first()).toBeVisible({ timeout: 10000 });

  await page.goto('/tasks/active');
  const activeNav = page.locator('[aria-current="page"]').filter({ hasText: 'Active' });
  await expect.poll(async () => await activeNav.count()).toBeGreaterThan(0);
});

test('Today sections and effort totals', async ({ page }) => {
  await createTask(page, { title: `${PREFIX}overdue`, due_date: isoDate(-1), effort_hours: 1 });
  await createTask(page, { title: `${PREFIX}today-a`, due_date: isoDate(0), effort_hours: 1 });
  await createTask(page, { title: `${PREFIX}today-b`, due_date: isoDate(0) });
  await createTask(page, { title: `${PREFIX}tomorrow`, due_date: isoDate(1), effort_hours: 2 });
  await createTask(page, { title: `${PREFIX}plus3`, due_date: isoDate(3), effort_hours: 0.5 });

  await page.goto('/tasks');
  await expect(card(page, `${PREFIX}overdue`)).toBeVisible({ timeout: 10000 });

  // Sections appear in order Overdue, Today, Next 7 days
  const ids = await page.locator('[data-testid^="today-section-"]').evaluateAll(
    els => els.map(e => e.getAttribute('data-testid')),
  );
  expect(ids).toEqual(['today-section-overdue', 'today-section-today', 'today-section-upcoming']);

  // Expected totals computed from the live agenda
  const agenda = (await (await page.request.get('/api/tasks/agenda')).json()).rows as
    { agenda_bucket: string; agenda_date: string; effort_hours: number | null }[];
  const sum = (rows: typeof agenda) => rows.reduce((a, r) => a + (r.effort_hours ?? 0), 0);
  await expect(page.getByTestId('today-effort')).toHaveText(formatEffort(sum(agenda.filter(r => r.agenda_bucket === 'today'))));

  const tomorrowRows = agenda.filter(r => r.agenda_date === isoDate(1));
  const plus3Rows = agenda.filter(r => r.agenda_date === isoDate(3));
  const dayEfforts = await page.getByTestId('today-day-effort').allTextContents();
  expect(dayEfforts).toContain(formatEffort(sum(tomorrowRows)));
  expect(dayEfforts).toContain(formatEffort(sum(plus3Rows)));

  // Overdue row displays its date
  await expect(card(page, `${PREFIX}overdue`).getByTestId('date-hint')).toBeVisible();
});

test('Today empty state', async ({ page }) => {
  await page.route('**/api/tasks/agenda', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      meta: { object_type: 'task', label: 'Agenda', total: 0, page: 1, page_size: 1, row_actions: [] },
      schema: [],
      rows: [],
    }),
  }));
  await page.goto('/tasks');
  await expect(page.getByTestId('today-empty')).toBeVisible({ timeout: 10000 });
  await expect(page.locator('[data-testid^="today-section-"]')).toHaveCount(0);
});

test('Completing a task updates the list in place', async ({ page }) => {
  await createTask(page, { title: `${PREFIX}done-me`, due_date: isoDate(0) });
  await createTask(page, { title: `${PREFIX}stay`, due_date: isoDate(0) });
  await page.goto('/tasks');
  await expect(card(page, `${PREFIX}done-me`)).toBeVisible({ timeout: 10000 });

  await card(page, `${PREFIX}done-me`).getByRole('button', { name: '✓' }).click();
  await expect(page.getByText(`${PREFIX}done-me`, { exact: true })).toHaveCount(0);
  await expect(page.locator('.skeleton')).toHaveCount(0);
  await expect(card(page, `${PREFIX}stay`)).toBeVisible();
});

test('Label filter applies to Today', async ({ page }) => {
  const a = await createTask(page, { title: `${PREFIX}lbl-a`, due_date: isoDate(0), effort_hours: 1.5 });
  const b = await createTask(page, { title: `${PREFIX}lbl-b`, due_date: isoDate(0), effort_hours: 4 });
  await page.request.put(`/api/tasks/${a}/labels`, { data: { labels: ['ui11-a'] } });
  await page.request.put(`/api/tasks/${b}/labels`, { data: { labels: ['ui11-b'] } });

  await page.goto('/tasks');
  const selectAll = page.getByTitle('Select all labels');
  if (await selectAll.count()) await selectAll.click();
  await page.getByTitle('Deselect all labels').click();          // none selected
  await page.getByRole('button', { name: 'ui11-a', exact: true }).click();

  await expect(card(page, `${PREFIX}lbl-a`)).toBeVisible();
  await expect(page.getByText(`${PREFIX}lbl-b`, { exact: true })).toHaveCount(0);
  await expect(page.getByTestId('today-effort')).toHaveText('1.5 h');

  await page.getByTitle('Select all labels').click();            // restore: all labels selected
});

test('Repeat control on create', async ({ page }) => {
  await page.goto('/tasks');
  await page.getByRole('button', { name: 'New task' }).click();
  await page.getByPlaceholder('Task title').fill(`${PREFIX}created-repeat`);
  await page.getByTestId('repeat-freq').selectOption('weekly');
  await page.getByTestId('repeat-interval').fill('2');
  await page.getByTestId('repeat-from-completion').check();
  await page.getByRole('button', { name: 'Create', exact: true }).click();

  await page.goto('/tasks/active');
  const icon = card(page, `${PREFIX}created-repeat`).getByTestId('repeat-icon');
  await expect(icon).toBeVisible({ timeout: 10000 });
  await expect(icon).toHaveAttribute('title', 'Every 2 weeks, after completion');
});

test('Repeat control hides interval when none', async ({ page }) => {
  await page.goto('/tasks');
  await page.getByRole('button', { name: 'New task' }).click();
  await expect(page.getByTestId('repeat-freq')).toHaveValue('');
  await expect(page.getByTestId('repeat-interval')).toHaveCount(0);
  await expect(page.getByTestId('repeat-from-completion')).toHaveCount(0);
});

test('Repeat control edit and clear', async ({ page }) => {
  await createTask(page, {
    title: `${PREFIX}edit-repeat`, recurrence_freq: 'weekly', recurrence_interval: 2,
    recurrence_mode: 'after_completion',
  });
  await page.goto('/tasks/active');
  await card(page, `${PREFIX}edit-repeat`).click();

  await expect(page.getByTestId('repeat-freq')).toHaveValue('weekly');
  await expect(page.getByTestId('repeat-interval')).toHaveValue('2');
  await expect(page.getByTestId('repeat-from-completion')).toBeChecked();

  await page.getByTestId('repeat-freq').selectOption('');
  await page.getByRole('button', { name: 'Save' }).click();

  await expect(card(page, `${PREFIX}edit-repeat`)).toBeVisible({ timeout: 10000 });
  await expect(card(page, `${PREFIX}edit-repeat`).getByTestId('repeat-icon')).toHaveCount(0);
});

test('Next-date toast on completing a recurring task', async ({ page }) => {
  await createTask(page, {
    title: `${PREFIX}toast-rec`, recurrence_freq: 'daily', recurrence_mode: 'after_completion',
  });
  await createTask(page, { title: `${PREFIX}toast-plain` });
  await page.goto('/tasks/active');

  await card(page, `${PREFIX}toast-rec`).getByRole('button', { name: '✓' }).click();
  const toast = page.getByTestId('next-toast');
  await expect(toast).toBeVisible({ timeout: 10000 });
  await expect(toast).toContainText('Next:');
  await expect(toast).toHaveCount(0, { timeout: 8000 });     // dismisses on its own

  await card(page, `${PREFIX}toast-plain`).getByRole('button', { name: '✓' }).click();
  await page.waitForTimeout(1000);
  await expect(page.getByTestId('next-toast')).toHaveCount(0);
});

test('Recurring task row shows repeat indicator', async ({ page }) => {
  await createTask(page, {
    title: `${PREFIX}ind-rec`, due_date: isoDate(2), recurrence_freq: 'monthly',
  });
  await createTask(page, { title: `${PREFIX}ind-plain` });
  await page.goto('/tasks/active');

  await expect(card(page, `${PREFIX}ind-rec`).getByTestId('repeat-icon')).toBeVisible({ timeout: 10000 });
  await expect(card(page, `${PREFIX}ind-plain`).getByTestId('repeat-icon')).toHaveCount(0);

  await card(page, `${PREFIX}ind-rec`).click();
  await expect(page.getByTestId('repeat-label')).toHaveText('Monthly');
});
