# Sprint Draft — StoryReader: Scroll-to-Deselect + Resume Position

## Goal

Two related UX fixes to the Reader:

> "Scrolling should deselect as well. Also please have the app remember were
> we are so when i restart the story (or the app) we jump to were we left
> of."

1. Any scroll clears the current tap-cycle selection/reaction bar (Sprint02
   only cleared it on tap, not on scroll — today the bar drifts out of
   alignment with the text once you scroll past it, since it's positioned
   once at tap time and never re-anchored).
2. Reading position is remembered per story version and restored: reopening
   a story you were already reading jumps back to where you left off, and
   reopening the app itself (its root route) jumps straight back into the
   most recently active story rather than always showing the Story List.

## Layer / Component

03_Application / StoryReader (Sprint03, follows Sprint01_Core, Sprint02_TapToSelect)

## Fast Path

Requested and confirmed by the human in the immediately preceding turn of
this same session, which already established fast-path as the working mode
for small StoryReader changes (Sprint02). Eligibility re-checked against
R-PRO-BP-01 §11 for this sprint's own scope:

- No new database table — two **additive columns** on existing tables only:
  `stories.last_opened_at` and `story_versions.last_read_paragraph_index`.
- `files_changed` ≤ 5 — expected 3: `schema.sql`, `backend/routers/stories.py`,
  `src/ShellEntry.tsx`.
- No new/changed shared contract surface — the one new endpoint
  (`GET /storyreader/last-read`) and one extended endpoint
  (`PUT /storyreader/stories/{id}/versions/{v}/position`) are both app-local,
  not platform contracts or cross-app Dataset shapes.
- Single component, single layer — StoryReader, Application layer, both
  backend and frontend but within this one component.

All four hold. Design done as a plan-mode conversation with the human,
saved to `05_fast_path_plan.md` before implementation starts, per §11.3.

## Scope

- Scroll (anywhere on the Reader) immediately clears any active tap-cycle
  selection and closes the reaction bar.
- Every position save (see below) also marks the story as "most recently
  active" (`stories.last_opened_at`), which is what the app-root redirect
  reads.
- Reading position is tracked per `(story_id, version)` — consistent with
  how annotations are already pinned to an exact version (Sprint01). A new
  version starts with no remembered position, same as it starts with no
  annotations; positions are never migrated across versions.
- Position is derived from which paragraph sits at the top of the viewport,
  saved via a small debounced call after scrolling stops, and once
  immediately on opening a story (so even a very short visit updates
  "most recently active," not just a long enough scroll).
- Opening a story (with no explicit `?version=`/`?highlight=` override)
  restores the saved position for whichever version loads, scrolling
  instantly (no animation) rather than smoothly, since this is a resume, not
  an intentional in-app jump.
- The app's root route (`/storyreader`) checks whether any story has ever
  been opened; if so, it redirects straight into that story (which then
  restores its own last position) instead of showing the Story List. First
  run (nothing ever opened) still shows the Story List.

## Out of Scope

- Any flush-on-close/`beforeunload`/`visibilitychange` handler to save the
  very last few seconds of reading before an abrupt tab close — accepted gap,
  same spirit as this app's other documented "known gap, not guarded"
  decisions. Worst case: position lags by up to the debounce window.
- Exact scroll-restore precision below paragraph granularity (no sub-
  paragraph/character-level scroll memory) — matches the app's existing
  paragraph-indexed addressing (the same granularity the Feedback list's
  "jump to passage" already uses).
- Any change to the annotation data model, tap-cycle mechanics, or reaction
  semantics from Sprint01/Sprint02.
