/**
 * UI tests — WorkoutTracker — Session tab (chooser → active workout → exercise logging → finish).
 *
 * Runs against http://atlas-shell via the shared atlas-playwright container, on the live
 * database. The test starts ONE new session, and deletes exactly that session (by id) when it
 * ends, pass or fail. It skips itself if a workout is already active, so it never touches
 * real in-progress work. Existing sessions are only read.
 *
 * Screenshots (mobile 390x844) are written to /tmp/wt-shots inside the container.
 */

import { test, expect, type Page } from '@playwright/test';

test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

const SHOTS = '/tmp/wt-shots';

async function activeSessionId(page: Page): Promise<string | null> {
  const res = await page.request.get('/api/workout/sessions/active');
  const body = await res.json();
  return body.rows[0]?.id ?? null;
}

test('session tab: chooser, start, log an exercise, resume after reload, finish', async ({ page }) => {
  if (await activeSessionId(page)) test.skip(true, 'a workout is already active; not touching it');

  let createdId: string | null = null;
  try {
    // 1. No active workout → archetype chooser
    await page.goto('/workout');
    await expect(page.getByRole('heading', { name: 'Start workout' })).toBeVisible();
    const types = page.getByRole('list', { name: 'Workout types' }).getByRole('button');
    await expect(types.first()).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/01_chooser.png` });

    // 2. Start → overview with planned exercises (neutral em dash, no deltas)
    await types.first().click();
    await expect(page.getByRole('button', { name: /not completed yet/ }).first()).toBeVisible();
    createdId = await activeSessionId(page);
    expect(createdId).not.toBeNull();
    await expect(page.getByRole('button', { name: 'Finish Workout' })).toBeVisible();
    await expect(page.getByRole('button', { name: '+ Add Exercise' })).toBeVisible();
    await page.waitForTimeout(600); // let mini charts load
    await page.screenshot({ path: `${SHOTS}/02_overview_planned.png` });

    // 3. Open first exercise → touch targets, log sets, comment, save
    const first = page.getByRole('button', { name: /not completed yet/ }).first();
    await first.click();
    await expect(page.getByRole('button', { name: 'Done' })).toBeVisible();
    for (const label of ['Decrease weight', 'Increase weight', 'Set 1: more reps', 'Set 1: fewer reps']) {
      const box = await page.getByRole('button', { name: label }).boundingBox();
      expect(box!.width, label).toBeGreaterThanOrEqual(44);
      expect(box!.height, label).toBeGreaterThanOrEqual(44);
    }
    expect((await page.getByRole('button', { name: 'Done' }).boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await page.waitForTimeout(600);
    await page.screenshot({ path: `${SHOTS}/03_exercise_empty.png` });

    // Tap a set to start it, enter reps, checkmark to confirm (reps + server-side timing are saved)
    for (const [n, reps] of [[1, '9'], [2, '8'], [3, '7']]) {
      await page.getByRole('button', { name: `Start set ${n}` }).click();
      await page.getByLabel(`Set ${n} reps`).fill(reps);
      await page.getByRole('button', { name: `Confirm set ${n}` }).click();
      await expect(page.getByRole('group', { name: `Set ${n}`, exact: true })).toHaveAttribute('data-state', 'done');
    }
    await page.getByLabel('Notes').fill('UI test note');
    await page.screenshot({ path: `${SHOTS}/04_exercise_filled.png` });

    // 4. Reload mid-exercise → same exercise screen; confirmed sets come from the server, notes from the draft
    await page.reload();
    await expect(page.getByLabel('Set 1 reps')).toHaveValue('9');
    await expect(page.getByLabel('Notes')).toHaveValue('UI test note');
    expect(await activeSessionId(page)).toBe(createdId); // no duplicate session

    // 5. Done → back to overview, exercise now completed
    await page.getByRole('button', { name: 'Done' }).click();
    await expect(page.getByRole('button', { name: /, completed/ }).first()).toBeVisible();
    await page.waitForTimeout(600);
    await page.screenshot({ path: `${SHOTS}/05_overview_one_done.png` });

    // 6. Reload on overview → still the same active session
    await page.reload();
    await expect(page.getByRole('button', { name: 'Finish Workout' })).toBeVisible();
    expect(await activeSessionId(page)).toBe(createdId);
    await page.goto('/workout/log');
    await page.goto('/workout');
    await expect(page.getByRole('button', { name: 'Finish Workout' })).toBeVisible(); // Session tab resumes

    // 7. Finish with planned exercises left → confirmation, then the session is finished
    await page.getByRole('button', { name: 'Finish Workout' }).click();
    await expect(page.getByRole('dialog', { name: 'Finish workout?' })).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/06_finish_confirm.png` });
    await page.getByRole('dialog', { name: 'Finish workout?' }).getByRole('button', { name: 'Finish' }).click();
    await expect(page).toHaveURL(/\/workout\/log/);
    expect(await activeSessionId(page)).toBeNull();
    await page.waitForTimeout(600);
    await page.screenshot({ path: `${SHOTS}/07_log_after_finish.png` });

    // 8. Back on Session tab → chooser again (nothing active)
    await page.goto('/workout');
    await expect(page.getByRole('heading', { name: 'Start workout' })).toBeVisible();
  } finally {
    if (createdId) await page.request.delete(`/api/workout/sessions/${createdId}`);
  }
});
