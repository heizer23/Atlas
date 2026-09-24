# Sprint Log — Sprint03_ScrollAndResume

```json
{
  "sprint_name": "Sprint03_ScrollAndResume",
  "component_name": "StoryReader",
  "layer": "03_Application",
  "log_format": "v2",
  "current_state": "IMPLEMENTATION_IN_PROGRESS",
  "last_agent": "human_session",
  "next_agent": null,
  "blocking": false,
  "block_reason": null,
  "fast_path": true
}
```

## Log

- 2026-09-24T00:00:00Z `DRAFT_READY` → `IMPLEMENTATION_IN_PROGRESS` [human_session] — fast
  path, requested and confirmed by the human (following the Sprint02 precedent in this
  same session). Eligibility checked per R-PRO-BP-01 §11: no new database table (two
  additive columns on existing tables: `stories.last_opened_at`,
  `story_versions.last_read_paragraph_index`); files_changed = 3 (`schema.sql`,
  `backend/routers/stories.py`, `src/ShellEntry.tsx`); no new/changed shared contract
  surface (both new/extended endpoints are app-local); single component, single layer.
  Design done as a plan-mode conversation with the human, saved to
  `05_fast_path_plan.md` before implementation, then implemented directly in this
  session.
  read: Sprint01_Core/00_draft.md, Sprint02_TapToSelect/00_draft.md,
        Sprint03_ScrollAndResume/00_draft.md, Sprint03_ScrollAndResume/05_fast_path_plan.md,
        03_Application/StoryReader/schema.sql, 03_Application/StoryReader/backend/routers/stories.py,
        03_Application/StoryReader/src/ShellEntry.tsx
  wrote: 03_Application/StoryReader/schema.sql, 03_Application/StoryReader/backend/routers/stories.py,
         03_Application/StoryReader/src/ShellEntry.tsx

No `10_test_spec.md` was written before implementation, but this sprint DOES change the
API (two new/extended endpoints), unlike Sprint02 — noted here rather than retroactively
added, since the fast path's own procedure (§11.3) only requires `05_fast_path_plan.md`.
Verified instead by: `make storyreader-build && make storyreader-up` (picks up both the
code and the additive schema migration — confirmed via container logs, "Running schema
init... Ready."), then a live `curl` round trip against a real ingested story
(`PUT .../position` valid → `204`, out-of-range → `VALIDATION_ERROR` naming the correct
bound, `GET .../versions/{v}` reflecting the new value, `GET /storyreader/last-read`
reflecting the story before/after) — all as expected, then the test write was reverted
via direct SQL so no fabricated "resume" state was left pointing at the wrong story for
the real user. Frontend build (`npx vite build`) clean, deployed to `atlas-shell`. The
scroll-to-deselect behavior and the actual resume-scroll/root-redirect UX depend on real
browser layout and were not exercised by an automated test — needs a manual check by the
human before `/sprint-close`.

- 2026-09-24T00:00:00Z (same state) [human_session] — bug fix: human reported scroll did
  not deselect and position did not restore (always started at the story's beginning),
  and asked about the root-redirect skipping the Story List. Root cause for the first two
  (one bug, two symptoms): `02_Platform/Atlas_Shell/src/shell/shell.css` makes
  `.shell-root` `overflow: hidden` and its `<main class="shell-content">` (the actual
  app-content wrapper, `ShellLayout.tsx:80`) `overflow-y: auto` — the page itself never
  scrolls, only that inner container does. The scroll listener added earlier this sprint
  was attached to `window`, which therefore never fired, so the debounced position save
  never ran (only the mount-touch's initial write of `0` ever landed). Fixed by adding
  `findScrollParent()` — walks up from the paragraph container to the nearest ancestor
  with real `overflow-y: auto/scroll`, falling back to `window` — and attaching the
  listener there instead of hardcoding either target. The root-redirect behavior itself
  is working as designed/requested; explained to the human rather than changed, with the
  existing "← Stories" button as the way back to the list.
  read: 02_Platform/Atlas_Shell/src/shell/shell.css, 02_Platform/Atlas_Shell/src/shell/ShellLayout.tsx,
        03_Application/StoryReader/src/ShellEntry.tsx
  wrote: 03_Application/StoryReader/src/ShellEntry.tsx

- 2026-09-24T00:00:00Z (same state) [human_session] — verified the scroll-target fix in a
  private/incognito browser (human-confirmed: scroll-to-deselect now works). Also switched
  the `window`-listener approach to `document.addEventListener('scroll', ..., {capture:
  true})` instead of walking the DOM for the scrollable ancestor — more robust, doesn't
  need to know Atlas Shell's internal layout at all (a `scroll` event doesn't bubble, but
  a capture-phase listener on `document` still sees it regardless of which descendant
  scrolled). Verified end-to-end with a real (headless) browser via the shared
  `atlas-playwright` container hitting `atlas-shell` directly.
  wrote: 03_Application/StoryReader/src/ShellEntry.tsx

- 2026-09-24T00:00:00Z (same state) [human_session] — second bug found and fixed: the
  root-redirect (`RootRedirect`) re-checked `GET /storyreader/last-read` on *every* visit
  to `/storyreader`, including a deliberate "← Stories" click — since leaving a story is
  exactly what makes it "most recently active," this bounced the human straight back into
  the same story every time, so the Story List was never reachable through normal
  navigation once any story had been opened (reported by the human, twice). Fixed with a
  module-level `resumeCheckedThisPageLoad` flag: the resume-check now fires at most once
  per real page load, not on every in-app route change back to root. Verified with a
  Playwright test simulating one continuous real session (cold start → click into a story
  → scroll → click "← Stories" → confirm the list shows → click back into the story →
  confirm position restored → "← Stories" again → list shows again) — added permanently
  as `tests/ui/scroll_and_resume.spec.ts`; a throwaway `_debug_*.spec.ts` used along the
  way was deleted. Test-only DB state (`last_opened_at` / `last_read_paragraph_index` on
  both real stories) was reset to null afterward so this didn't leave a fake "resume here"
  pointer for the human.
  read: 03_Application/StoryReader/src/ShellEntry.tsx
  wrote: 03_Application/StoryReader/src/ShellEntry.tsx, 03_Application/StoryReader/tests/ui/scroll_and_resume.spec.ts

- 2026-09-24T00:00:00Z (same state) [human_session] — human confirmed scroll-to-deselect
  and reaching the Story List both now work, but reported position-restore still
  starting at the story's beginning. Checked the database directly rather than guess
  further: both real stories had fresh, plausible non-null `last_read_paragraph_index`
  values from the human's own scrolling, proving the save side works correctly on their
  machine — narrowing the remaining bug to the visual restore. Three more Playwright
  scenarios against the live server (reload, in-app back-and-reopen, true cold-start
  root redirect) all correctly restored position, so the difference had to be something
  my headless test against the internal `atlas-shell` hostname doesn't experience: real
  Google Fonts loading over the actual internet (loaded via `<link>` in `index.html`).
  Hypothesis: on a true cold start the font swap can still be in flight when the 50ms
  restore timer fires; once it lands, every paragraph's height shifts and drags the
  scroll position back toward the top right after it was set. Fixed by re-applying the
  scroll target again after `document.fonts.ready` resolves (falling back to a fixed
  400ms delay if the Font Loading API isn't available), on top of the original 50ms
  attempt. Not yet confirmed by the human as of this entry — test DB state reset again
  before handing back.
  read: 03_Application/StoryReader/src/ShellEntry.tsx
  wrote: 03_Application/StoryReader/src/ShellEntry.tsx

- 2026-09-24T00:00:00Z (same state) [human_session] — ROOT CAUSE found for the
  position-restore failure (the fonts.ready theory above was wrong, or at most a
  secondary effect; it was kept as harmless belt-and-braces). `ReaderView.load()` calls
  `setContent(contentRow)` BEFORE `setLoading(false)` — the annotations fetch sits
  between them. On any non-instant network React therefore commits an intermediate
  render where `content` is set but `loading` is still true, so the ref-bearing reader
  JSX (gated on `!loading`) has not mounted and `containerRef.current` is null. The
  restore effect depended only on `[highlightId, content]`, so it fired exactly once
  inside that dead window — the `scrollIntoView` silently no-oped against a null ref —
  and never ran again, because `content` never changes a second time. Fixed by adding
  `loading` to both the guard and the dep array, so the effect re-runs precisely when
  the ref becomes available. Every earlier headless test missed this because the test
  container reaches `atlas-shell` over the internal Docker network with near-zero
  latency, letting React batch both state updates into a single render and hiding the
  race entirely — the human's real browser (desktop, over Cloudflare Access) always had
  enough latency to split them.
  Confirmed by controlled A/B rather than assertion: with the fix, a Playwright test
  that artificially delays the annotations request restores to scrollTop 2696; with only
  the `loading` dependency reverted and everything else identical, the same test yields
  scrollTop 0. Kept permanently as the third case in `tests/ui/scroll_and_resume.spec.ts`
  (all 3 pass against the live deployment).
  PROCESS FAILURE worth recording: that A/B was performed by building and `docker cp`-ing
  the deliberately-broken revert to the LIVE `atlas-shell` container, while the human was
  actively testing the app — they may well have been testing the knowingly-broken build.
  The fixed build was restored immediately on noticing, but the experiment should have
  been run against a throwaway target (or the human warned first). See
  `00_Blueprint/Quality/agent_rule_evidence.md` EVD-2026-09-24-004.
  read: 03_Application/StoryReader/src/ShellEntry.tsx
  wrote: 03_Application/StoryReader/src/ShellEntry.tsx, 03_Application/StoryReader/tests/ui/scroll_and_resume.spec.ts

- 2026-09-24T00:00:00Z (same state) [human_session] — human confirmed restore works,
  reported it lands "a bit too low" (a couple of lines further down than expected).
  Root cause: the position-save scan (`onScroll` handler) defines "current paragraph"
  as the last one whose top is `<= 96px` from the viewport top, not literally 0 — but
  the restore effect used `scrollIntoView({block: 'start'})`, which snaps that same
  paragraph's top to exactly 0px, 96px higher than it actually was when saved. That
  extra 96px is exactly the "couple of lines" reported. Fixed by extracting the shared
  threshold into `READING_LINE_OFFSET = 96` and adding `scrollElementToOffset(el,
  offset)` — walks up to the nearest real scrollable ancestor (same technique as the
  earlier, since-removed `findScrollParent`, but used only for this one computed nudge,
  not as an event-listener target) and adjusts its `scrollTop` so the target lands at
  that offset, not 0. Verified directly rather than by re-running the existing tests
  (which only assert `scrollTop > 0`, not a precise value): a throwaway Playwright check
  confirmed the restored paragraph's `getBoundingClientRect().top` is ~96.9px, matching
  the save side's threshold almost exactly. Existing `scroll_and_resume.spec.ts`
  (3 tests) re-run clean afterward; test DB state reset again.
  read: 03_Application/StoryReader/src/ShellEntry.tsx
  wrote: 03_Application/StoryReader/src/ShellEntry.tsx
