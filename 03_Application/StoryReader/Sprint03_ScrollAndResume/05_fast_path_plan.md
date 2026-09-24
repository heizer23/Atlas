# StoryReader — Scroll-to-Deselect + Resume Position (Sprint03, fast path)

## Context

Sprint02 gave the Reader a tap-cycle selection with a reaction bar positioned once at
tap time. Scrolling doesn't clear it, so the bar drifts out of alignment with the
underlying text as soon as you scroll — needs to close on any scroll. Separately, the
user wants the app to remember reading position: reopening a story you were already
reading should jump back to where you left off, and reopening the app itself should
land you back in whatever story was most recently active rather than always showing the
Story List.

This needs new persisted state (previously there was none beyond annotations), so it's
more than "quick," but it fits cleanly as additive columns — no new table, no new shared
contract. Confined to three files, all already read in full this session:
`03_Application/StoryReader/{schema.sql, backend/routers/stories.py, src/ShellEntry.tsx}`.

## Approach

### 1. Scroll clears the tap-cycle selection (`src/ShellEntry.tsx`, `ReaderView`)

Add one `useEffect` that attaches a passive `window` `scroll` listener for the lifetime
of `ReaderView`, calling `setPopover(p => p ? null : p)` on every event. This is the
same `popover` state Sprint02 already drives the reaction bar and the live pending-
highlight overlay from — clearing it here reuses that machinery with no other change.

### 2. Persisted position — schema (additive only)

```sql
alter table storyreader.stories        add column if not exists last_opened_at timestamptz;
alter table storyreader.story_versions add column if not exists last_read_paragraph_index integer;
```

`last_opened_at` is touched by every position save (mount included, not just scroll) —
it doubles as "most recently active story," which is what the root-redirect endpoint
reads. `last_read_paragraph_index` is pinned to one exact `(story_id, version)` row,
mirroring how annotations are already pinned per version (Sprint01) — a new version
starts with no remembered position, same as it starts with zero annotations.

### 3. Backend (`backend/routers/stories.py`)

- `VERSION_CONTENT_SCHEMA` gains a `last_read_paragraph_index` column; `get_version_content`
  selects it from `story_versions` and includes it in the row (alongside the existing
  `paragraphs` payload it already builds via `split_paragraphs`).
- New `PositionUpdate(BaseModel)`: `{ paragraph_index: int }`.
- New route `PUT /stories/{story_id}/versions/{version}/position`:
  - Resolve via the existing `_resolve_version(conn, story_id, version, allow_latest=False)`
    helper (same as `list_annotations`) — the caller always already knows the concrete
    version it's viewing.
  - Validate `paragraph_index` the same way `create_or_update_annotation` already
    validates `body.paragraph_index` against `split_paragraphs(body_markdown)` (reuse,
    don't reinvent): `>= 0` and `< len(paragraphs)`.
  - One connection, two updates, one commit: `update storyreader.story_versions set
    last_read_paragraph_index = %s where story_id = %s and version = %s`, then `update
    storyreader.stories set last_opened_at = now() where id = %s`.
  - Return `204` (mutation endpoint, R-CON-BP-04 exempt, no body needed).
- New route `GET /storyreader/last-read` (registered as its own literal path — `/last-read`,
  not nested under `/stories/{story_id}`, so there's no route-ordering ambiguity with the
  existing `/stories/{story_id}` catch-all):
  - `select id from storyreader.stories where last_opened_at is not null order by
    last_opened_at desc limit 1`.
  - Bespoke JSON (R-CON-BP-04 exempt — same rationale as `export_annotations`: a tiny
    control signal for client-side routing, not a rendered Dataset): `{"story_id": "<uuid>"}`
    or `{"story_id": null}` when nothing has ever been opened. Always `200` — "nothing yet"
    is a valid empty state (R-CON-AL-01), not an error.

### 4. Frontend (`src/ShellEntry.tsx`)

- `VersionContentRow` interface: add `last_read_paragraph_index: number | null`.
- Small helper `savePosition(storyId, version, paragraphIndex)` wrapping the new `PUT`
  call (fire-and-forget, same `apiFetch` used everywhere else in this file).
- In `ReaderView`:
  - A `useEffect` keyed on `[content]` that calls `savePosition` once, immediately, with
    `content.last_read_paragraph_index ?? 0` — the "mount touch" that updates
    `last_opened_at` even on a short visit, not just after a long-enough scroll.
  - A position-restore `useEffect`, same shape as the existing `highlightId` scroll-into-
    view effect (:496-510 in the current file) but lower priority: only runs when there's
    no `highlightId` and `content.last_read_paragraph_index != null`, using
    `behavior: 'auto'` (instant) rather than `'smooth'` — this is a resume, not an
    intentional in-app jump.
  - Extend the new scroll listener from step 1: alongside the immediate `setPopover(null)`,
    debounce (~600ms after the last scroll event) a scan over
    `containerRef.current.querySelectorAll('[data-paragraph-index]')` for the topmost
    element whose `getBoundingClientRect().top <= 96` (a small fixed offset so the
    "current" paragraph is the one at/just above the reading line, not literally at
    `top: 0`), and call `savePosition` with its index.
- Root route: today `<Route path="/" element={<StoryListView />} />`. Add a small
  `RootRedirect` component that on mount calls `GET /storyreader/last-read`; if
  `story_id` is non-null, `navigate(`/storyreader/stories/${story_id}`, { replace: true })`;
  otherwise renders `<StoryListView />` (first run / nothing ever opened). Show the
  existing `<Skeleton />` while the check is in flight so there's no flash of the list
  before redirecting. Swap it in for `StoryListView` on the `"/"` route only — the
  `/stories/:id` and `/stories/:id/feedback` routes are unchanged.

## Files touched

`03_Application/StoryReader/{schema.sql, backend/routers/stories.py, src/ShellEntry.tsx}`
— 3 files. No new table, no shared/platform contract change (fast-path eligibility
confirmed in `Sprint03_ScrollAndResume/00_draft.md`).

## Accepted gap (documented, not guarded)

No `beforeunload`/`visibilitychange` flush — position is only saved on the debounced
scroll-stop and on mount. An abrupt tab close mid-debounce can lose up to ~600ms of
scroll progress. Same spirit as this app's other documented "known gap" decisions
(EssayCards' non-atomic flashcard generation, StoryReader's own no-delete-on-reingest).

## Verification

1. `npx vite build` (Atlas Shell) + `docker cp dist/. atlas-shell:/usr/share/nginx/html/`.
2. Apply the schema change: the backend re-runs `schema.sql` idempotently at startup
   (`alter table ... add column if not exists`), so `docker restart atlas-storyreader`
   (and `atlas-storyreader-test`) picks it up — same pattern as every prior additive
   migration in this repo.
3. `curl` round trip against one of the two real stories already in the system: `PUT
   .../position` with a valid and an out-of-range `paragraph_index` (expect `204` then
   `VALIDATION_ERROR`), then `GET .../versions/{v}` and confirm
   `last_read_paragraph_index` comes back; `GET /storyreader/last-read` before and after,
   confirming it returns that story's id.
4. Manual browser check (can't be scripted from here): scroll while a tap-selection is
   active → bar disappears; scroll to a specific paragraph, reload the page → jumps back
   there instantly; open `/storyreader` root fresh → redirects into that story instead of
   the list.
5. Record the plan as `Sprint03_ScrollAndResume/05_fast_path_plan.md` before implementing.
