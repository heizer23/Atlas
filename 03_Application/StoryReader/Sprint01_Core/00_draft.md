# Sprint Draft — StoryReader MVP: Mobile Passage Feedback

## Goal

A mobile-first reader for markdown stories, built to capture fast, low-friction passage
feedback while reading on a phone: select a sentence or paragraph, tap one of four
reactions, done — no confirmation, no comments. A per-story feedback list then shows
every marked passage in reading order, with enough surrounding text to remember the
reaction a day later, and jumps back to the passage on tap.

Stories are authored and published entirely outside this app, by a separate writing
assistant ("Codex") that has direct SSH access to the server. Codex drops markdown files
onto disk and, later, reads annotations back off disk/API to discuss them in its own
chat with the user. This sprint's API/file surface is designed for that consumer, not
for a human uploading/downloading anything by hand.

Component name `StoryReader` is a placeholder — rename freely during design review if a
better name comes to mind.

## Layer

03_Application

## Component

StoryReader

## Scope

- Story list view: every story, title, which version is latest, marked-passage count
  for the version currently in view.
- Reader view: renders one story version's markdown, paragraph by paragraph. Selecting a
  sentence or paragraph surfaces the four reaction buttons; tapping one saves
  immediately. Marked passages show a subtle highlight. Tapping an already-reacted
  passage lets you change or remove the reaction — still no confirmation step.
- Feedback list view: one story's annotations (for the version in view), in reading
  order, each showing its reaction, selected text, and surrounding context. Tapping a
  row jumps to that passage in the Reader view, scrolled into place and briefly
  highlighted.
- Markdown story ingestion from a configurable content folder, with stable story
  identity and immutable, append-only versions (see Content Publishing).
- A documented, machine-readable annotation export for Codex (see Codex Integration).

## Out of Scope

- Any comment or free-text field on an annotation — reaction only, this version.
- In-app story authoring/editing UI — content only ever arrives via the content folder.
- Any AI analysis, summarization, or chat inside StoryReader itself — Codex does that
  elsewhere, out of band.
- Reconciling annotations across versions (e.g. re-anchoring a passage after a rewrite)
  — an annotation belongs to the exact version it was made on; a new version starts with
  zero annotations. See Content Publishing and Data Model.
- Multi-user accounts, sharing, or permissions — single-user system, matches the rest of
  Atlas.
- Notifications, reading progress tracking, statistics/analytics on reactions.
- Deleting a story or a version through the UI (ingestion is append-only; out of scope
  here, same as EssayCards' essay/section ingestion).
- Overlap reconciliation — two annotations may cover overlapping spans in this sprint;
  nothing merges or blocks them.

## Content Publishing

Stories are plain markdown files with YAML front matter, same shape as EssayCards'
offline ingestion convention:

- Front matter: `title`, `slug` (stable story identity — never changes once assigned).
- Body: the story text, in ordinary markdown, split into paragraphs the same way the
  reader renders them (see Annotation Location below — the split algorithm is one
  canonical function, shared by ingestion and the reader payload; design phase to
  finalize exact rules for what counts as a paragraph boundary, e.g. blank-line-
  separated blocks, whether a blockquote or list counts as one paragraph or several).

**Publishing a version.** Codex writes/overwrites `<content_dir>/<slug>.md` over its
existing SSH session, then runs a one-shot ingestion command (mirrors EssayCards'
`python -m backend.ingest`, not an HTTP endpoint — no upload path is needed since Codex
already has a shell on the server):

```
docker exec atlas-storyreader python -m backend.ingest content/<slug>.md
```

- First ingestion of a `slug` creates the story (`version = 1`).
- Re-ingestion compares the file's content against the story's current latest version
  by hash (same idempotency pattern as EssayCards image import's `source_sha256`):
  - Unchanged content → no-op, no new version row. Running ingestion twice by mistake
    must never create a duplicate version.
  - Changed content → inserts a new version (`version = latest + 1`). Versions are
    immutable once written — ingestion never updates an existing version row's content,
    only appends a new one.
- `title` may change on re-ingestion (updates the story row); `slug` is fixed at
  creation and any change is rejected as an ingestion error (same rationale as
  EssayCards' stable `slug`/`card_key` conventions — identity fields are never silently
  renamed).

**Version pinning invariant (drives Data Model + API):** an annotation always carries
the exact `(story_id, version)` it was made against. Publishing a new version:
- never touches any existing annotation row,
- never re-attaches, migrates, or re-anchors an annotation onto the new version's text,
- leaves the new version's annotation list empty until the user marks it themselves.

Viewing an old version must remain possible (its annotations are otherwise orphaned and
unreadable) — the Reader/Feedback list are explicitly version-scoped, defaulting to the
story's latest version, with a way to switch to an older one.

**Content folder path.** Following the existing Atlas `${DATA_ROOT}/<app>/content`
convention (see EssayCards `compose.yml`) is the default, but the user has said the
final location will be specified after the app is built and may live outside
`DATA_ROOT` entirely (e.g. inside a separate writing-project directory Codex already
works in). Design phase: read the mount path from its own env var (e.g.
`STORYREADER_CONTENT_DIR`) rather than hardcoding the `DATA_ROOT` convention, so the
bind-mount source can be repointed in `compose.yml` without a code change.

## Data Model

### Story
- id
- slug (unique, stable, author-assigned)
- title
- latest_version (denormalized convenience; the row also derivable as
  `max(version)` from StoryVersion)
- created_at, updated_at

### StoryVersion
- id
- story_id (FK → Story)
- version (integer, starts at 1, monotonic per story)
- body_markdown (full text, immutable once inserted — no diffing/patching)
- content_sha256 (idempotency key for re-ingestion)
- created_at
- Unique on (story_id, version). Never updated after insert.

### Annotation
- id
- story_id (FK → Story, denormalized for direct per-story queries)
- version (paired with story_id — NOT a FK to StoryVersion's surrogate id, to make the
  version-pinning invariant textually obvious in every query: `where story_id = $1 and
  version = $2`)
- paragraph_index (0-based, within that exact version's paragraph split)
- char_start, char_end (offsets into that paragraph's rendered plain text — see
  Annotation Location)
- selected_text (verbatim substring at [char_start, char_end) — stored redundantly so
  the export in Codex Integration is self-contained without re-rendering the version)
- context_before, context_after (surrounding text captured at creation time, from the
  immutable version content — see Annotation Location)
- reaction: exactly one of `positive` | `negative` | `neutral` | `unclear`
- created_at, updated_at
- Unique on (story_id, version, paragraph_index, char_start, char_end) — one reaction
  per exact span; a second tap at the same span updates or deletes the existing row (see
  Reaction Semantics), it never inserts a duplicate.

## Annotation Location

Location is always relative to one immutable version's **rendered plain text**, not raw
markdown source — i.e. what `window.getSelection()` sees on the phone screen, not
markdown syntax characters. Because the version is immutable, `paragraph_index` +
character offsets computed at read time will always match what was stored at creation
time; no re-mapping is ever needed within a version (only across versions, which is
explicitly out of scope — see Content Publishing).

- The reader payload (`GET .../versions/{version}`, see API) returns paragraphs as an
  ordered array so the frontend never has to re-derive `paragraph_index` from raw
  markdown itself — ingestion and the read endpoint use the same paragraph-split
  function.
- `context_before` / `context_after`: the remainder of the same paragraph's text before
  and after the selection (design phase to pick an exact bound, e.g. capped at ~200
  characters, spilling into the adjacent paragraph only if the selection sits at a
  paragraph edge and the capped window would otherwise be empty).

## Reaction Semantics

Four reactions, exactly these, fixed set (not open-ended like EssayCards' `category`):
👍 `positive`, 👎 `negative`, 😐 `neutral`, ❓ `unclear`.

- Selecting text with no existing annotation at that exact span, then tapping a
  reaction: creates the annotation. Saves on tap — no confirmation step anywhere in this
  flow.
- Tapping a *different* reaction on an already-annotated span: updates `reaction` and
  `updated_at` in place. Same row, same `created_at`.
- Tapping the *same, currently-active* reaction again: deletes the annotation (the
  "easy to remove" requirement). The frontend already knows the active annotation's id
  from the version's annotation list, so this is a plain delete by id, not a
  toggle-detecting upsert.
- No annotation is ever created or left with a null/empty reaction — the four values
  above are the only persisted states; "no reaction" is the absence of a row.

## API

All under `/api/storyreader`. Bound to `127.0.0.1` only on the host, same as every other
Atlas app (least exposure default) — Codex reaches it either via `curl` to the
loopback-bound port over its own SSH session, or by reading exported files directly (see
Codex Integration); neither needs the public shell/nginx route.

```
GET    /api/storyreader/stories
GET    /api/storyreader/stories/{story_id}
GET    /api/storyreader/stories/{story_id}/versions/{version}
GET    /api/storyreader/stories/{story_id}/versions/{version}/annotations
POST   /api/storyreader/annotations
DELETE /api/storyreader/annotations/{annotation_id}
GET    /api/storyreader/stories/{story_id}/versions/{version}/annotations/export
```

### `GET /api/storyreader/stories`
- No parameters. Returns Dataset: `{ id, slug, title, latest_version, created_at,
  updated_at }`.
- Ordering: `updated_at desc` (most recently published first).
- Empty result is valid — no stories ingested yet; UI shows an empty state.

### `GET /api/storyreader/stories/{story_id}`
- Returns Dataset (single row): story fields plus the full list of existing version
  numbers (for the version switcher).
- 404 → `ApiError` if `story_id` does not exist.

### `GET /api/storyreader/stories/{story_id}/versions/{version}`
- Param `version`: optional, default = that story's `latest_version`.
- Returns Dataset (single row): `{ story_id, version, title, paragraphs: [{
  paragraph_index, text }, ...] }`.
- 404 → `ApiError` if `story_id` or that specific `version` does not exist.

### `GET /api/storyreader/stories/{story_id}/versions/{version}/annotations`
- Param `version`: required, no default (the Reader always knows which version it's
  currently showing and asks for exactly that one — no implicit "latest" fallback here,
  unlike the version-content endpoint above).
- Returns Dataset: annotation rows as in Data Model.
- Ordering: `paragraph_index asc, char_start asc` (reading order).
- Empty result is valid — nothing marked yet on this version.

### `POST /api/storyreader/annotations`
- Mutation endpoint (R-CON-BP-04 exempt).
- Body: `{ story_id, version, paragraph_index, char_start, char_end, selected_text,
  context_before, context_after, reaction }`. All fields required — this endpoint only
  ever creates or overwrites-in-place at an exact span (see Reaction Semantics); it
  never partially updates a subset of fields.
- On success: `200`/`201` with the typed annotation record (so the frontend learns the
  row's `id` immediately, needed for the toggle-off delete).
- On error (`story_id`/`version` doesn't exist, `reaction` outside the fixed set,
  `char_start >= char_end`): `ApiError` `VALIDATION_ERROR` or `NOT_FOUND`.

### `DELETE /api/storyreader/annotations/{annotation_id}`
- Mutation endpoint. On success: `204`. On error (unknown id): `ApiError NOT_FOUND`.

### `GET .../versions/{version}/annotations/export`
See Codex Integration — bespoke JSON, R-CON-BP-04 exempt (same rationale as EssayCards'
`exploration-package`/`examination-package`: built for an external LLM round trip, not
for a Dataset-consuming UI component).

## UI

Registered in Atlas Shell (`src/shellConfig.ts`) with `mobilePrimaryNav` as the primary
target — this app is designed to be used one-handed, on a phone, while reading.

- **Story list** (`/storyreader`): title, latest version, marked-passage count for the
  version in view. Taps into the Reader at the latest version.
- **Reader** (`/storyreader/stories/:id`, optional `?version=`): clean typography,
  minimal chrome — the story text is the whole screen. Selecting a sentence or paragraph
  surfaces the four reaction buttons near the selection; tapping one saves immediately
  and shows a subtle highlight (a single quiet highlight treatment across all four
  reactions, distinguished by a small inline reaction icon rather than four clashing
  highlight colors, to protect "clean typography, minimal interruptions"). Tapping an
  already-highlighted passage re-opens the same four buttons, with the active one
  visually marked, to change or remove it. A version switcher is visible only when the
  story has more than one version.
- **Feedback list** (`/storyreader/stories/:id/feedback`): every annotation for the
  version in view, reading order, each row showing its reaction icon, the selected text,
  and its stored surrounding context. Tapping a row navigates to the Reader, scrolled
  and briefly highlighted at that passage.

## Codex Integration

Documented here so both the human and Codex have one authoritative reference; restate
this section (or link to it) in the component's `CLAUDE.md` once implemented, EssayCards
-style.

**Adding or publishing a story** — see Content Publishing above:
1. Write/overwrite `<content_dir>/<slug>.md` (front matter `title` + `slug`, markdown
   body) over SSH.
2. `docker exec atlas-storyreader python -m backend.ingest content/<slug>.md`.
3. Unchanged content is a no-op; changed content creates a new immutable version.

**Retrieving annotations for discussion:**

```
curl http://127.0.0.1:<port>/api/storyreader/stories/{story_id}/versions/{version}/annotations/export
```

- Returns JSON: story `slug`/`title`, the exact `version`, and every annotation for that
  version — `selected_text`, `context_before`, `context_after`, `reaction`
  (`positive`/`negative`/`neutral`/`unclear`, verbatim — never translated into a guessed
  "reason"), `created_at`, `updated_at` — in reading order.
- No upload/download step: same server, same filesystem/loopback network Codex is
  already inside over its SSH session.
- `story_id`/`slug` lookup: design phase to decide whether this endpoint also accepts
  `slug` instead of `story_id` for convenience, since Codex knows the slug it just
  published but may not know the surrogate id — either resolve slug→id via
  `GET /stories` first, or accept both; pick one and document it, don't leave it
  ambiguous.

## Time Authority

`created_at`/`updated_at` on every table are server time, taken when the write happens
— no client-supplied timestamps anywhere in this app (R-CON-AL-06).

## Open Design Questions (for design review)

- Exact paragraph-split algorithm (blank-line blocks vs. treating lists/blockquotes as
  one paragraph each) is not fully specified here — design phase must finalize and
  document it, shared verbatim between ingestion and the version-content endpoint.
- Exact `context_before`/`context_after` window size/bound.
- Whether the export endpoint (and/or the annotations list endpoint) should accept
  `slug` as an alternative to `story_id` for Codex's convenience.
- Final content-folder mount path — deferred by the user until after the app is built;
  design phase should make it a dedicated env var (not hardcoded to the `DATA_ROOT`
  convention) so it can be repointed without a code change.
