# CLAUDE.md

This file contains app-local guidance only.
Global architecture and development rules are defined in the repository root CLAUDE.md.

## App
EssayCards pairs long-form essay reading with spaced-repetition flashcards. A flashcard
always links back to the essay passage that taught it; the reader lets the user jump
into review at the end of each section, and a global "Due for review" queue surfaces
cards from every section as they come due over time.

## Glossary
Canonical domain vocabulary. Use these words with exactly these meanings in code,
comments, endpoint params, UI labels, and sprint drafts — do not coin near-synonyms.

Some terms below (essay `status`, the `review_interval` column, the `focus` / `review`
session split) are being introduced by the "Essay Roadmap / Directed Learning" sprint
and may not all be in the code yet; the definitions are still authoritative for how
they must be built.

### Structure
- **topic** — a named collection of essays. Stored as the free-text `essays.category`
  value; an essay belongs to at most one topic, or to none.
- **essay** — one learning unit: an `essaycards.essays` row plus its ordered sections
  and their flashcards.
- **status** — an essay's lifecycle position. One of **planned** or **complete**
  (more values may be added later).
- **planned** — the essay exists as a stub; its body text *is* the planning document
  (intended sections, narrative, scope notes).
- **complete** — content is finished enough to learn from.
- **card** — a single flashcard (`essaycards.flashcards`), with one
  `flashcard_review_state` row.

### Card scheduling
- **open** — the scheduler currently considers the card showable:
  `next_due_at <= now()`. Also called *due*. Not changed by the Roadmap sprint.
- **interval** — the span a card is currently scheduled across:
  `next_due_at − last_reviewed_at`, fixed at its last review. Materialised as
  `flashcard_review_state.review_interval` (Postgres `interval` type,
  `NOT NULL DEFAULT '0'`), written in the same statement as `next_due_at`. `'0'` for a
  *new* card. The timestamp difference stays the definition of record; the column is a
  write-time cache of it (single writer: the review endpoint; seeded `'0'` by
  `ingest.py`). Column is `review_interval`, not `interval`, because `interval` is a
  reserved word.
- **new** — a card never reviewed: `last_reviewed_at IS NULL` (interval `'0'`).
- **learning** — reviewed at least once, interval still `< 24h`.
- **established** — interval `>= 24h`.
- Every scheduled card is exactly one of **new** / **learning** / **established**.
- **graduate** / **graduation** — a card's interval first reaching 24h, moving it from
  *learning* to *established*. Not stored; detectable only by the threshold crossing.

### Sessions
- **scope** — the restriction on a focus session: exactly one topic, or exactly one
  essay.
- **focus** — a study session restricted to a scope, surfacing every **open** card in
  that scope regardless of state (new / learning / established). Started from the essay
  overview. This is the *learning* mode.
- **review** — the global study session, no scope, surfacing cards that are **open AND
  established**. This is the *maintenance* mode.

### Oral exams
- **exam** — the current oral-exam standing of an essay, derived (not stored) from
  `section_examinations` (append-only, one row per section per occasion). Method: for
  each section take its most recent row (latest `examined_at`) — that row is the current
  assessment of that section. The essay-level **score** / **exam date** exist only when
  **every** section has at least one such row; if any section has never been examined,
  both are null (an essay is not "currently examined" until all of it has been).
- **section score** — one `section_examinations` row's raw grade, `0–6`.
- **score** — the essay's overall exam result, present only when every section has been
  examined: `round(avg(latest section_score across all sections) / 6 * 100)`. Rendered
  as a percentage.
- **exam date** — the **oldest** `examined_at` among those per-section most-recent rows
  (the least-recently-tested section sets it); present under the same all-sections
  condition as **score**. Re-examining one stale section moves the date forward to
  whichever section is stalest next.
- Sections only ever grow (re-ingest never deletes them), so a section added in a later
  ingest drops the essay back to no **score** / **exam date** until it too is examined.

### Overview indicators
- **progress** — for an essay or topic: **established** cards / total cards in scope —
  the `22 / 34` line. Established cards that are also *open* still count. Not a maturity
  score.
- **open count** — for an essay or topic: how many cards in scope are **open** right
  now — what a focus session would surface. The `12 open` line.

## Sprint scope
- Sprint 1: One-shot markdown ingestion CLI, essay/section/flashcard data model, due-queue
  review loop with floor/doubling SRS scheduling, minimal React reader + review session UI.
- Sprint 2: `POST /api/essaycards/essays/ingest` JSON ingestion endpoint plus an in-app
  "Add / Update Essay" paste-JSON UI, sharing one upsert core with the markdown CLI path.
- Sprint 5: two-category ordering for `GET /flashcards/due` (see `## Due-queue ordering`).
- Sprint 7: essay roadmap (`status`), focus vs review sessions, materialised `review_interval`,
  roadmap knowledge indicators on `GET /essays` (see `## Roadmap, focus and review`).

## Content ingestion
Essays can be ingested two ways — both upsert by the same stable author-assigned keys
(slug / (essay_id, anchor_slug) / (essay_id, card_key)) and both call the single shared
`backend.ingest.upsert_document(conn, doc)` core, so re-ingestion via either path never
resets a flashcard's review state.

### Essay overview metadata (`category`, `sort_index`, `status`)
Both ingestion paths accept three optional essay-level fields — front-matter keys for the
markdown CLI, top-level JSON keys for the API:
- `category` — free text, no fixed set, no lookup table (an essay has at most one). It is
  the group the essay appears under on the overview page. The known groups (`Art`,
  `History`, `Philosophy`) and their display order live only in the frontend
  (`CATEGORY_ORDER` in `src/ShellEntry.tsx`); any other value renders in its own group
  after those, and `null` renders last under "Uncategorized". Adding a category is a
  content change, not a schema change.
- `sort_index` — integer, default `0`, the essay's position **within its category**,
  ascending (ties break on `created_at`). This is where a sequence number goes — it is
  never written into `title`. Distinct from `essay_sections.order_index`, which is
  auto-derived from payload array order; `sort_index` is set explicitly by the author.
- `status` — `planned` | `complete`, default `complete` (`ck_essays_status`). `planned`
  is a stub whose body text is a planning document; a normal ingest is `complete`, so a
  stub must set `status: planned` explicitly. `VALID_ESSAY_STATUSES` / `DEFAULT_ESSAY_STATUS`
  in `backend/ingest.py` are the single source for both ingest paths.

All three are `on conflict do update`d on re-ingest, so a later payload with the same slug
re-files, re-orders or re-statuses the essay. `GET /essays` orders rows
`(category asc nulls last, sort_index asc, created_at asc)` and carries all three fields
on every row; `EssayListView` groups on them. Blank `category`, non-integer `sort_index`
or a `status` outside the set is `VALIDATION_ERROR` (JSON path) / `IngestionError`
(markdown path).

**Markdown CLI** (offline authoring — YAML front matter, `## Heading {#anchor}` sections,
one fenced ```flashcards YAML block per section):

    docker exec atlas-essaycards python -m backend.ingest /app/content/<file>.md

**JSON API / in-app UI** (Sprint 2): `POST /api/essaycards/essays/ingest`, or the
"Add / Update Essay" nav entry in the app, which pastes the same JSON shape into a
textarea. See `Sprint02_JsonIngestion/00_draft.md` for the payload schema.

One deliberate asymmetry: a card `id` that already exists in the DB under a *different*
section is silently moved by the markdown CLI path (`ON CONFLICT ... DO UPDATE SET
section_id = excluded.section_id`), but rejected as `VALIDATION_ERROR` by the JSON
endpoint's pre-write validation layer. The shared upsert core's SQL is identical for
both paths — only the JSON endpoint's validation is stricter. See
`Sprint02_JsonIngestion/10_architecture.json` §risks.

Deleting a section or flashcard from the source (markdown file or JSON payload) does NOT
delete its row on re-ingestion via either path — this is an explicit Sprint 1 gap,
extended unchanged to the JSON path in Sprint 2 (see `Sprint01_Core/10_architecture.json`
§risks), not a bug.

To use an image in essay or card text, import it first (see `## Images` below), then
reference its slug as ordinary Markdown — `![](/api/essaycards/images/<slug>)` — inside
`body_markdown` / `q` / `a`. Neither ingestion path parses or validates image references;
a reference to a slug that was never imported just renders as a broken image.

The JSON-ingestion helper prompt (`STUB_PROMPT` in `src/ShellEntry.tsx`, shown in the
"Add / Update Essay" view) has an **Images rule** plus an **"Available images"** list the
author fills in by hand from the imported slugs. The generating model only emits
`![](...)` references for slugs on that list; if the list is left empty it emits none.
The endpoint still does no validation — the list is a prompt-side convention, not a
backend check.

## Images
Images enter two ways — a **server-side staging folder** and **in-browser upload**
(paste / drop / pick, Images view only). Both run the identical processing core
(`backend.import_images.process_image_bytes`): decode → `exif_transpose` → Lanczos
downscale to a 2000 px longest edge → metadata-stripped re-encode → slug →
`source_sha256` idempotency → per-file transaction (write `/app/images/<slug>.<ext>`,
INSERT the `essaycards.images` row, commit). Accepted: `.jpg` `.jpeg` `.png` `.gif`
`.webp` — SVG is rejected (stored-XSS vector). Per-file problems (not an image, format
mismatch, oversized GIF, still-too-large after re-encode) are reported as `skipped` /
`400` and never abort a batch.

Idempotency spans both paths: `source_sha256` (SHA-256 of the original bytes) is the
key, so uploading bytes already imported via staging — or vice versa — returns
`unchanged` with no second row and no rewrite.

**Staging path**
1. Drop files into `${DATA_ROOT}/essaycards/staging` (mounted read-only at
   `/app/staging`) — scp, a file share, Syncthing, etc.
2. Import: CLI `docker exec atlas-essaycards python -m backend.import_images`, or the
   **Images** view → **Scan staging folder**.

**Browser upload path** (`POST /api/essaycards/images/upload`)
- On the Images view: paste (Ctrl/Cmd-V), drop onto the drop zone, or pick a file.
- Hard 12 MiB request-body cap, enforced while reading.
- The **raw uploaded bytes** are archived to `${DATA_ROOT}/essaycards/images/originals/`
  (`/app/images/originals/<source_sha256>.<ext>`, created by the code) *before* the
  import — this is the upload path's equivalent of a retained staging original. There
  is no reprocess-from-`originals/` tool yet; to rebuild an uploaded image today, copy
  its original into staging and rescan.

Use **Copy Markdown** in the Images view to copy `![](/api/essaycards/images/<slug>)`
into essay or card text.

The slug is derived from the original filename (lowercased, non-alphanumeric runs
collapsed to `-`; an unnamed clipboard paste becomes `pasted-image`), with a `-<6 hex>`
suffix appended only on a collision with a different image.

**You must retain your own copies — nothing under `/app/images` is backed up
automatically.** The daily `pg_dump` covers the `essaycards.images` rows only, never the
files. `/app/images/<slug>.<ext>` (processed, web-served) and `/app/images/originals/`
(raw upload archive) are both outside it and nothing else backs them up. After a database
restore the rows are back but `GET /images/{slug}` returns 404 until the bytes are
restored:
- **Staged images:** re-run the scan against the retained staging folder.
- **Uploaded images:** the raw bytes live in `originals/<source_sha256>.<ext>`; today,
  recovery is manual (copy an original into staging and rescan).

If you lose `/app/images` *and* both your staging originals and the `originals/` archive,
the affected images are unrecoverable.

## Pattern references
Follow the same patterns as StorageTracker / Calendar (03_Application):
- FastAPI backend, psycopg2 connection pool, RealDictCursor
- platform_contracts for Dataset responses on GET endpoints
- platform_errorhandling for api_error and middleware
- Atlas Shell registration via src/shellConfig.ts

One deliberate deviation from the StorageTracker/Calendar router pattern:
`POST /flashcards/{id}/review` does NOT use a Pydantic request body model. It reads
the raw Starlette `Request` and validates `grade` manually so that every invalid
shape (missing key, wrong type, out-of-set value, unparsable JSON) returns
ApiError VALIDATION_ERROR (400) instead of FastAPI's default 422 shape. See
`Sprint01_Core/10_architecture.json` §contracts.invariants.

## Due-queue ordering
`GET /api/essaycards/flashcards/due` — base eligibility is `next_due_at <= now()`.
**Sprint07** splits the endpoint into two session types, inferred from whether a
scope param is present (there is no `mode` param — see `## Roadmap, focus and
review`):

- **review** (no scope) additionally requires `review_interval >= interval '24
  hours'` — only `established` cards that are also due.
- **focus** (`?topic=` | `?essay_id=` | `?essay_id=&section_id=`) applies no
  interval filter — every open card in scope (new, learning, established).

Within either session, eligible cards are returned in two categories, **RECENT
entirely before BACKLOG** (Sprint05):

- **RECENT** — `last_reviewed_at >= now() - interval '24 hours'` (a rolling
  window off Postgres `now()`, *not* a calendar day / "reviewed today"; a
  never-reviewed card is never RECENT). Sorted by `next_due_at` **DESC** —
  closest-to-now first — so a card the user just pushed a few minutes out
  re-enters near the front once that delay elapses. Serves relearning.
- **BACKLOG** — everything else eligible. Sorted by `flashcard_review_state.review_interval`
  (`== next_due_at - last_reviewed_at`), **DESC** (longest first). Overdue
  duration is deliberately ignored. A never-reviewed card has `review_interval`
  `'0'` (seeded by `ingest.py`) and sorts behind every reviewed backlog card —
  no separate new-card queue.
- Tie-breakers: `next_due_at ASC`, then `f.id ASC`.

`last_reviewed_at` / `next_due_at` / `review_interval` (on `flashcard_review_state`,
all written by `POST .../review` from a single `select now()`) are the source of
truth — EssayCards has no per-review history table. All ordering logic is one SQL
`ORDER BY` in `list_due_flashcards`; the review UI renders `rows` in server order.

Each `/due` row also carries three additive fields (R-CON-BP-04; none affects
eligibility or ordering): `is_new` (bool) = `last_reviewed_at IS NULL`;
`is_recent` (bool) = `last_reviewed_at >= now() - interval '24 hours'` (the
RECENT-vs-BACKLOG category flag, false when `is_new`); and
`scheduled_interval_seconds` (int) = epoch seconds of `review_interval`, the
interval the card is currently scheduled across (the BACKLOG sort key; `0` when
`is_new`). All three feed the review screen.

## Roadmap, focus and review
Sprint07. Terms are defined in `## Glossary`; this section is the implementation
contract.

### `review_interval` (materialised interval)
`flashcard_review_state.review_interval` (`interval`, `NOT NULL DEFAULT '0'`,
`ck_review_state_interval >= 0`) is a **write-time cache** of
`next_due_at - last_reviewed_at`. The timestamp difference stays the definition
of record. Single writer: `POST /flashcards/{id}/review` sets it in the same
`UPDATE` as `next_due_at`, to `next_due_at - now` (`now` also being
`last_reviewed_at`), so the cache always equals the difference. `ingest.py`
seeds `'0'`. Any future code path that reschedules a card without going through
`compute_next_due_at` must recompute it. Card classification:
`new` = `last_reviewed_at IS NULL` (interval `'0'`); `learning` =
`review_interval < interval '24 hours'` and not new; `established` =
`review_interval >= interval '24 hours'`.

### focus vs review (`GET /flashcards/due`)
No `mode` param — the session type is inferred from scope presence:
`{}` → review (`+ review_interval >= '24 hours'`); `{topic}` / `{essay_id}` /
`{essay_id, section_id}` → focus (no interval filter). Rejected with
`VALIDATION_ERROR`: `section_id` without `essay_id`; `topic` together with
`essay_id` or `section_id`. `topic` filters on `essays.category`. The reader's
end-of-section jump is already scoped, so it is a focus session with no code
change. `GET /flashcards/stats` is unchanged.

### `GET /essays` roadmap indicators
Every row carries, beyond `id/title/slug/category/sort_index/status`, five
derived fields (all against Postgres `now()` at query time; `list_essays`
docstring is authoritative):
- `progress_total` (int) — every flashcard in the essay (not gated on a
  review-state row existing).
- `progress_established` (int) — those with `review_interval >= interval '24 hours'`
  (a `LEFT JOIN`, so a card with no review-state row counts in total, not here).
- `open_count` (int) — those with `next_due_at <= now()` (the plain `open`
  definition; **not** gated on established — exactly what a focus session would
  surface).
- `oral_score` (int | null) — `round(avg(latest section_score) / 6 * 100)` over
  the most recent `section_examinations` row per section. `null` unless **every**
  section has ≥ 1 examination.
- `oral_date` (ISO str | null) — the **oldest** `examined_at` among those
  most-recent-per-section rows; same all-sections gate as `oral_score`.

Topic-level progress / open count are **not** returned — the frontend sums the
per-essay counts of a topic's rows. `GET /essays/{id}` (detail) carries `status`
only, not the derived indicators.

## Queue stats
`GET /api/essaycards/flashcards/stats` — review-queue forecast. Returns a Dataset of
exactly **seven** zero-filled rows partitioning every flashcard that has a review-state
row into non-overlapping horizon bands by `next_due_at` vs Postgres `now()`: `due_now`,
`within_10_min`, `within_1_day`, `within_7_days`, `within_30_days`, `within_90_days`,
`beyond_90_days` (bands open on the lower edge, closed on the upper; the seven counts
sum to the total scheduled cards in scope). The 30-/90-day split feeds the review
screen's UPCOMING `≤3 mo` / `>3 mo` forecast columns. Same `essay_id` / `section_id`
scoping rules as `GET /flashcards/due` (`section_id` without `essay_id` →
`VALIDATION_ERROR`).

## Review screen (`src/ShellEntry.tsx` → `ReviewSessionView` / `ReviewStatsPanel`)
Material 3 layout, no page header: one flat `surface-variant` stats card, the
question card (`surface` + `elevation-1`, the dominant element), a full-width
primary **Flip** button (grade buttons replace it after flip), then a small
diagnostics frame. The stats card has two sections, their names (`CURRENT` /
`UPCOMING`) rotated vertically in a left gutter, no divider between them:
- **CURRENT** — three metric blocks: `Session` (reviews done this session,
  including a card that came back around), `Backlog` (cards due in the most
  recent `/due` refetch), `New` (`is_new` cards in that same queue).
- **UPCOMING** — a two-row × six-column forecast (`≤10m <1d <7d <30d <3mo ≥3mo`),
  horizontally scrollable on narrow widths. `All` = live `GET /stats` (the six
  forward bands, `due_now` omitted). `Session` = client-side tally: each review
  response gives `next_due_at − last_reviewed_at`, bucketed by the same band
  edges and counted per session (reset when the session starts, not on the
  per-grade refetch). No backend state; `FORECAST_COLUMNS` in `ShellEntry.tsx`
  mirrors the `/stats` band edges.

**Recency-selected bold frame.** The question card gets a **2 px primary
border** whenever the current card's `is_recent` is true — i.e. it was placed
ahead of the backlog because it was reviewed within the last 24 h (RECENT
category, sorted by `next_due_at`), not because of its interval. The
diagnostics frame under the buttons then shows either "↩ Failed earlier this
session — shown again" (the card's `flashcard_id` is in the session's
`againIds` set) or "◆ Selected by recency…", plus the current card's
`scheduled_interval_seconds` ("last interval" — the BACKLOG sort key) and the
new interval the previously-graded card landed on. `againIds` is a
diagnostics-only label; it has no effect on which card is shown.

**Refetch-on-grade (supersedes the Sprint05c relearning sub-queue).** The
session re-fetches `GET /flashcards/due` on mount, after **every** grade, and
from the completion screen's **Check again** button — never on a timer.
`ReviewSessionView` holds no `index` or client-side relearning queue; it always
renders `queue[0]` from the latest response. The card just graded is scheduled
at least 5 s (`again`) / 1 min (floored `hard`) into the future, so it is
absent from the immediate refetch and reappears only on a **later** refetch,
once it actually comes due, in the server's RECENT-first order. The session
ends when a refetch returns nothing due. One accepted gap: the very last card
graded `again` or floored `hard`, with nothing else to grade while its
interval elapses — **Check again** on the completion screen re-runs the fetch
for exactly that case.

## Oral examinations
Sections already have a stable author-assigned id (`anchor_slug`, unique per essay) —
that id is reused as-is for examination history; no separate section-id scheme was
introduced. "Version" of a section is `essay_sections.updated_at`, snapshotted into
`section_examinations.section_version_at` at export time — not a separate counter.
"Current understanding" of a section is never stored; it is always the latest row in
`essaycards.section_examinations` for that section_id.

Round trip: `GET /api/essaycards/essays/{id}/examination-package` builds a
self-contained JSON package (essay + sections + flashcards + each section's derived
last examination) for pasting into ChatGPT — copied to the clipboard by the "Export
for examination" button in ReaderView, together with the scoring-rubric prompt in
`EXAM_PROMPT_INTRO` (src/ShellEntry.tsx). ChatGPT's JSON reply is pasted into
`ImportExaminationsView` (`/essaycards/examinations/import`) and posted to
`POST /api/essaycards/examinations/import`, which resolves each result's
`essay_slug`/`section_anchor_slug` and inserts a new row — never updates or deletes
an existing one. Same validate-everything-before-any-write pattern as
`/essays/ingest`; `NOT_FOUND` if a slug pair doesn't resolve, `VALIDATION_ERROR` for
any structural problem, all-or-nothing across the whole batch.

The export endpoint is a GET that returns a bespoke JSON body rather than a Dataset —
a deliberate R-CON-BP-04 exemption (see backend/routers/examinations.py module
docstring): it's copied to the clipboard for an external LLM, not rendered by a
Dataset-consuming UI component. `GET /sections/{id}/examinations` (the plain history
list shown under each section in ReaderView) IS real UI-visible tabular data and
returns a proper Dataset.

## Flashcard exploration (Sprint06)
Explore a *single* flashcard with ChatGPT — deliberately action-neutral at export
time (the user does not pre-decide whether the problem is their own
misunderstanding, a bad question, a wrong answer, or a missing distinction; that
emerges from the conversation).

- **Export.** `GET /api/essaycards/flashcards/{flashcard_id}/exploration-package`
  returns a bespoke JSON blob (`export_version: 1`) — the card (identified by its
  **uuid** `card_id`, with `card_key` echoed for readability), its essay/section
  metadata, and `context.section_body_markdown`. EssayCards has **no
  card→paragraph linkage**; the whole containing section is the finest context
  available. Same R-CON-BP-04 exemption rationale as `examination-package`. The
  **Explore** button on the revealed answer in `ReviewSessionView` fetches it and
  copies it + `EXPLORE_PROMPT_INTRO` (src/ShellEntry.tsx) to the clipboard
  ("Copied for ChatGPT"). Read-only — never touches review/scheduling state. It
  sits next to the existing "Jump to passage" control, same `jumpBtnStyle` weight,
  and after a successful copy becomes an **Import result →** button routing to
  `ExploreImportView` (reset on the next card).
- **Import.** `POST /api/essaycards/flashcards/exploration/import` — raw
  `request.json()`, `{"actions": [...]}` (a bare single action object is also
  accepted). `?dry_run=true` validates + resolves + returns the plan **without
  writing**; the `ExploreImportView` (`/essaycards/explore/import`, reachable from
  the essay list) previews that, then re-POSTs without the flag to apply.
- **Actions.** Exactly one `save_discussion` (required); 0..1 `update_card` per
  card_id; 0..n `create_card`. `update_card.changes` is whitelisted to
  `question` / `answer`; `reason` is mandatory and persisted. `create_card` needs
  `section_id` (+ optional `section_anchor_slug`, validated against it), gets an
  auto-generated `card_key` (`disc-<8hex>`) and a fresh `flashcard_review_state`
  row like ingest.
- **Atomicity & errors.** The whole import is one transaction — any failure rolls
  back every action, including the discussion. A rejected import returns a
  complete, copy-pasteable `error.message` ("EssayCards could not import … Nothing
  was saved. Fix the JSON and send the complete … package again."); the import
  view has a **Copy error for ChatGPT** button.
- **Persistence.** `flashcard_discussions` (one row per exploration;
  `question_at_time` / `answer_at_time` / `section_id_at_time` snapshotted from the
  live card *before* any `update_card` from the same import; `knowledge_gap`
  nullable) and `flashcard_revisions` (one row per Q/A edit; both old+new of both
  fields always stored; mandatory `reason`; `source_discussion_id` links the edit
  to its discussion). Historical question/answer text lives **only** in
  `flashcard_revisions` — `flashcards` always holds just the current version, so an
  edited-away question never reappears in `GET /flashcards/due`. The returned JSON
  is transport only; it is decomposed into these rows and never stored verbatim.
- Backend: `backend/exploration.py` (build/validate/plan/execute) +
  `backend/routers/exploration.py` (registered after `flashcards.router`).

## Port
EssayCards backend runs on host port 8024 (container port 8000).

## Schema
essaycards schema in the shared Atlas Postgres instance.
Tables: essaycards.essays, essaycards.essay_sections, essaycards.flashcards,
essaycards.flashcard_review_state, essaycards.section_examinations (append-only),
essaycards.flashcard_discussions, essaycards.flashcard_revisions (Sprint06 —
flashcard exploration; the app never updates/deletes rows in either).
Schema initialized idempotently at startup from schema.sql.

`00_architecture/schema.sql` is a design copy that `make essaycards-schema` feeds
to psql; it is already one sprint stale (missing `essaycards.images`). The
canonical runtime schema is `03_Application/EssayCards/schema.sql` (per
architecture.json), applied by `init_schema()` at startup and by conftest.
