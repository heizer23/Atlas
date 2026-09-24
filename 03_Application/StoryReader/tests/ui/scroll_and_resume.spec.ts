/**
 * UI tests — StoryReader — Sprint03_ScrollAndResume
 *
 * Covers:
 *   - Any scroll clears the active tap-cycle selection / reaction bar
 *   - Reading position is saved on scroll (debounced) and restored on reload
 *   - Position restore survives the load-order race (see the third test) —
 *     this is the regression that actually shipped broken and took several
 *     rounds of real-browser testing to find, so it is worth keeping.
 *
 * Tests run against http://atlas-shell via the shared atlas-playwright container.
 * They use the live production database — no test fixtures are loaded, so they
 * target one of the real ingested stories directly by id, and each test seeds
 * or clears the saved position it depends on rather than assuming a clean slate.
 */

import { test, expect } from '@playwright/test';

const STORY_ID = 'cc78a551-ff5c-425a-bedb-2af286f30512'; // "The Losing Side" — long enough to scroll

/** Seeds the stored reading position directly, bypassing the scroll-save
 * debounce so restore-side tests are isolated from save-side timing. */
async function seedPosition(request: any, paragraphIndex: number) {
  await request.put(`/api/storyreader/stories/${STORY_ID}/versions/1/position`, {
    data: { paragraph_index: paragraphIndex },
  });
}

const scrollTop = (page: any) =>
  page.evaluate(() => document.querySelector('main')?.scrollTop ?? 0);

test('scrolling clears the tap-cycle selection and reaction bar', async ({ page, request }) => {
  // Start at the top so the tapped paragraph is where this test expects it.
  await seedPosition(request, 0);

  await page.goto(`/storyreader/stories/${STORY_ID}?version=1`);
  await page.waitForSelector('[data-paragraph-index]');
  await page.waitForTimeout(300);

  const firstParagraph = page.locator('[data-paragraph-index="1"]');
  const box = await firstParagraph.boundingBox();
  if (!box) throw new Error('no bounding box for paragraph 1');
  await page.mouse.click(box.x + 10, box.y + 10);

  await expect(page.getByTitle('Positive')).toBeVisible();

  // Leave the cursor where the click left it — over the paragraph text. Moving
  // it first risks parking it on the reaction bar, which is not scrollable, so
  // the wheel event would never reach the shell's scroll container.
  await page.mouse.wheel(0, 800);
  await page.waitForTimeout(300);

  await expect(page.getByTitle('Positive')).not.toBeVisible();
});

test('reading position is saved on scroll and restored on reload', async ({ page, request }) => {
  await seedPosition(request, 0);

  await page.goto(`/storyreader/stories/${STORY_ID}?version=1`);
  await page.waitForSelector('[data-paragraph-index]');
  await page.waitForTimeout(300);

  await page.mouse.move(200, 300);
  await page.mouse.wheel(0, 2000);
  // Debounced save fires ~600ms after the last scroll event.
  await page.waitForTimeout(1200);
  expect(await scrollTop(page)).toBeGreaterThan(0);

  await page.reload();
  await page.waitForSelector('[data-paragraph-index]');
  await page.waitForTimeout(500);

  expect(await scrollTop(page)).toBeGreaterThan(0);
});

/**
 * Regression: ReaderView's load() calls setContent() BEFORE setLoading(false).
 * On any non-instant network React commits an intermediate render where
 * `content` is set but the ref-bearing reader JSX (gated on `!loading`) has
 * not mounted — containerRef.current is null and the scroll silently no-ops.
 * If the restore effect depends only on [content] it fires exactly once, in
 * that dead window, and never runs again. Delaying the annotations request
 * (the one whose completion flips `loading`) reproduces it deterministically;
 * without `loading` in the effect's deps this test fails with scrollTop 0.
 */
test('position restore survives the content-then-loading render race', async ({ page, request }) => {
  await seedPosition(request, 40);

  await page.route('**/api/storyreader/stories/*/versions/*/annotations', async route => {
    await new Promise(r => setTimeout(r, 400));
    await route.continue();
  });

  await page.goto(`/storyreader/stories/${STORY_ID}?version=1`);
  await page.waitForSelector('[data-paragraph-index]');
  await page.waitForTimeout(800);

  expect(await scrollTop(page)).toBeGreaterThan(0);
});
