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
  (intended sections, narrative, scope notes). (Sprint14 removed the planned/complete PILL
  from the essay overview; `status` itself and the oral-exam gating on `complete` remain.)
- **complete** — content is finished enough to learn from.
- **card** — a single flashcard (`essaycards.flashcards`), with one
  `flashcard_review_state` row.
- **level** — a card's integer structural depth (`flashcards.level`, `>= 1`, default
  `2`). Current convention: `1` = foundational/spine, `2` = building/explanatory
  structure, `3` = decorating/examples/terminology/anecdotes/supporting detail.
  Open-ended upward, not an enum — set exclusively by `POST /flashcards/upsert`; no
  other endpoint (including essay/section ingest) reads or writes it. See
  `## Question levels and overview`.

### Nuggets (Sprint09)
- **nugget** — a standalone, independently-learnable concept (`essaycards.nuggets`),
  NOT owned by one essay or section — a new layer between section and flashcard.
  `essay (main spine) -> section (sub-spine) -> nugget -> flashcard`. The same nugget
  can be referenced by any number of sections/essays without duplicating its content,
  its flashcards, or their review state.
- **`nugget_key`** — the nugget's stable, author-assigned identity, same convention as
  `slug` / `anchor_slug` / `card_key`: validated against `SLUG_LIKE_RE`
  (`^[a-zA-Z0-9_-]+$`, case-sensitive, no auto-slugify/lowercase), globally unique.
  Create/update is always upsert-by-key — the key is never a `SET` column, so a
  title/body edit can never rename it. No key-rename path.
- **`[[nugget:key]]`** — the Markdown reference syntax, usable in
  `essays.main_spine_markdown` and `essay_sections.body_markdown`. Resolved through
  the stable `nugget_key`; the rendered title always comes live from `nuggets.title`,
  never duplicated as a separate copy in the referencing Markdown. An unresolved
  reference is always an ingest-time validation error — no placeholder nugget is ever
  auto-created.
- **`section_nuggets`** — the many-to-many association between a section and the
  nuggets it currently references. DERIVED, NOT AUTHOR-MAINTAINED: a section's
  Markdown is the sole source of truth, and the association rows are fully resynced
  (insert missing, delete stale) on every section upsert by
  `backend/ingest.py::upsert_document`. This is the one explicit exception to the
  app's general no-delete-on-re-ingest policy — it only ever removes an association
  row, never a `nuggets` row or a `flashcards` row.
- **`flashcards.nugget_id`** — a card's optional link to the one nugget it tests.
  Nullable; set exclusively via `POST /flashcards/upsert`'s `nugget_id` field
  (omit/null/value tri-state — an omitted key never disturbs an existing assignment).
  No ingestion path ever reads or writes it. When set, a card's exploration context
  (`GET /flashcards/{id}/exploration-package`) becomes the nugget's own
  `body_markdown` instead of the containing section's.

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
- **learned** (Sprint14) — interval `>= 30 days`. A stricter level ABOVE established
  (learned is a subset of established). Thresholds live once in `backend/progress.py`
  (`ESTABLISHED_INTERVAL_SQL`, `LEARNED_INTERVAL_SQL`).
- **locked** (Sprint14) — a card whose section has not passed its guided section oral
  exam. Derived, never stored: unlocked iff `section_oral_state.guided_passed`. A locked
  card stays stored and counted in `progress_total`, but is excluded from every review
  queue, from `GET /flashcards/stats` and from `open_count`, and cannot be reviewed.
- Every UNLOCKED scheduled card is exactly one of **new** / **learning** / **established** /
  **learned** (learned is also established; the question overview shows the highest).
  A locked card shows as **locked** instead.
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
- **revalidation** (Sprint14) — a third, dedicated mode: re-checking every card flagged
  `needs_revalidation` after a failed unguided essay oral, regardless of due date. See
  `## Section progression (Sprint14)`.

### Oral exams
- **exam** — a historical oral-examination result for one section, stored as a
  `section_examinations` row (append-only, one row per section per occasion). "Current
  understanding" of a section is always the latest such row (highest `examined_at`).
- **section score** — one `section_examinations` row's raw grade, `0–6`.
- **pass rule** (Sprint14) — an oral attempt PASSES iff `score / 6 * 100 >= 70`, i.e. score
  `>= 5` on the 0–6 scale (4 = 66.7% fails). One rule for all four oral kinds; defined once
  in `backend/oral_state.py`; the verdict is computed at import time and stored in
  `passed`. Supersedes Sprint12's `score >= 3`.
- **scope** (Sprint14, oral exams) — an oral attempt is `section` scope (one section) or
  `essay` scope (the whole essay as an integrated whole). Section attempts are stored in
  `section_examinations`, essay attempts in `essay_examinations`.
- **exam_type** (Sprint12) — `guided` | `unguided`, required on every
  `section_examinations` row, never silently defaulted by the application going
  forward. `guided` = calibration-aware (the examiner is shown the section's prior
  `guided`-type history to tune starting difficulty). `unguided` = genuinely cold —
  no prior history/calibration context is ever passed, regardless of what history
  exists. (Sprint14: guided/unguided now also feed the section/essay traffic lights — see
  `## Section progression (Sprint14)`.)
- Sprint12 removed the single blended per-essay **oral score** / **exam date**
  percentage that previously lived on the essay overview (`oral_score`/`oral_date`);
  Sprint14 then replaced Sprint12's four-milestone `learning_level` with the traffic
  lights below.

### Overview indicators
- **progress** — for an essay or topic: **established** cards / total cards in scope —
  the `22 / 34` line. Established cards that are also *open* still count. Not a maturity
  score.
- **open count** — for an essay or topic: how many cards in scope are **open** right
  now AND unlocked AND not awaiting revalidation (Sprint14) — what a focus session would
  surface. The `12 open` line.
- **section traffic light** (Sprint14) — derived per-section state `grey` (not started) /
  `yellow` (guided oral passed, cards unlocked) / `green` (every card established) /
  `blue` (unguided oral passed). Shown as one small dot per section.
- **essay traffic light** (Sprint14) — derived per-essay state `grey` / `yellow` (guided
  ESSAY oral passed) / `green` (every card learned) / `blue` (every section unguided
  passed) / `violet` (unguided ESSAY oral passed). Shown as one large dot. Highest
  satisfied state wins. See `## Section progression (Sprint14)`. This replaces the removed
  Sprint12 `learning_level`.

## Sprint scope
- Sprint 1: One-shot markdown ingestion CLI, essay/section/flashcard data model, due-queue
  review loop with floor/doubling SRS scheduling, minimal React reader + review session UI.
- Sprint 2: `POST /api/essaycards/essays/ingest` JSON ingestion endpoint plus an in-app
  "Add / Update Essay" paste-JSON UI, sharing one upsert core with the markdown CLI path.
- Sprint 5: two-category ordering for `GET /flashcards/due` (see `## Due-queue ordering`).
- Sprint 7: essay roadmap (`status`), focus vs review sessions, materialised `review_interval`,
  roadmap knowledge indicators on `GET /essays` (see `## Roadmap, focus and review`).
- Sprint 8: card `level`, question-overview screen, single-question maintenance
  (edit/add/export/import) decoupled from essay ingest, single-essay export (see
  `## Question levels and overview`).
- Sprint 9: nuggets (`essaycards.nuggets`, `section_nuggets`), `essays.main_spine_markdown`,
  unified `[[nugget:key]]` reference validation across both ingestion paths, `flashcards.nugget_id`,
  nugget-aware flashcard exploration context, examination `nugget_versions` echo-through, and
  in-app nugget rendering/navigation (see `## Glossary` "Nuggets" and `## Nuggets` below).
- Sprint 10: FSRS as a second, persistently 50/50 A/B-assigned scheduling algorithm alongside
  Classic, a scheduler badge on the review card, and a first-version experiment dashboard.
  Retired in full by Sprint 12 (see below) — kept here only as a historical note.
- Sprint 11: `GET /review-stats/summary` — day/week/month observed recall dashboard.
- Sprint 12: FSRS becomes the SOLE scheduler (Classic + the Sprint10 A/B experiment and its
  dashboard removed entirely), a derived 0-4 essay `learning_level` with a new guided/unguided
  `exam_type` split on oral exams, consolidated essay/section action menus (`ActionMenu`) with a
  persisted category collapse control, and a reworked stats page (`GET /review-stats/activity`,
  `GET /review-stats/intervals`) plus regrouped main nav (see `## FSRS scheduling (Sprint12)` and
  `## Learning progress` (retired by Sprint 14, see `## Section progression (Sprint14)`)).
- Sprint 13: Review page shows a day-based five-metric row (Recalls / Unique / First from
  `GET /review-stats/today`, UTC calendar day; Due / New derived client-side from the due queue) and a
  single unlabeled interval row (the Current/Upcoming/Session UI of `## Review screen` below is
  superseded); Stats page Study Activity is a day-based stacked Repeat/Unique/First chart
  (`GET /review-stats/activity` now returns `recalls`/`unique_cards_seen`/`first_cards_seen`/`recall_rate`)
  and Observed Recall is a day/week/month selector (`/review-stats/summary` gains `new_count`);
  essay reader sentence feedback (`backend/sentences.py::split_sentences`,
  `backend/routers/sentence_feedback.py`, `essaycards.sentence_feedback` — two independent boolean
  flags per sentence, addressed by sentence_index; known gap: feedback can misattach if a section's
  body_markdown is edited after marking).
- Sprint 14: section-level learning progression — derived section/essay traffic lights replace the
  overview's planned/complete pill, card counts and 0–4 level; flashcards locked until a passed guided
  SECTION oral; 70% pass rule on all oral kinds; section- and essay-scope orals; Learned (>= 30d) card
  state; failure-triggered Revalidation that preserves FSRS state unless the card is forgotten
  (see `## Section progression (Sprint14)`). Retires Sprint12's `learning_level` and its nine fields.

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
`GET /api/essaycards/flashcards/due` — base eligibility is `next_due_at <= now()`, AND
(Sprint14) the card's section is unlocked AND the card is not `needs_revalidation` (flagged
cards are served only by `GET /flashcards/revalidation`). The ORDER BY below is unchanged.
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
`backend.scheduling.FSRSScheduler` (the sole scheduler since Sprint12 — see
`## FSRS scheduling (Sprint12)`) must recompute it. Card classification:
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
Every row carries, beyond `id/title/slug/category/sort_index/status`, three
category-level indicators (against Postgres `now()` at query time; `list_essays`
docstring is authoritative):
- `progress_total` (int) — every flashcard in the essay (not gated on a
  review-state row existing; locked cards included).
- `progress_established` (int) — those with `review_interval >= interval '24 hours'`
  (a `LEFT JOIN`, so a card with no review-state row counts in total, not here).
- `open_count` (int) — those with `next_due_at <= now()` AND in an unlocked section
  AND not `needs_revalidation` (Sprint14: exactly what a focus session would surface;
  not gated on established).

plus the Sprint14 derived essay traffic light (`essay_state`, `essay_next_step`,
`essay_guided_passed`, `essay_unguided_passed`, the two latest scores and passed dates,
`cards_learned_count`, `sections_total`, `sections_unguided_passed_count`,
`revalidation_pending_count`) — see `## Section progression (Sprint14)`. The nine
Sprint12 learning-progress fields and `learning_level` are removed.

Topic-level progress / open count are **not** returned — the frontend sums the
per-essay counts of a topic's rows. `GET /essays/{id}` (detail) carries the same
essay-progress fields as the list endpoint, computed by the identical shared SQL
(`backend/progress.py::essay_progress_lateral_sql`).

## Queue stats
`GET /api/essaycards/flashcards/stats` — review-queue forecast. Returns a Dataset of
exactly **seven** zero-filled rows partitioning every flashcard that has a review-state
row into non-overlapping horizon bands by `next_due_at` vs Postgres `now()`: `due_now`,
`within_10_min`, `within_1_day`, `within_7_days`, `within_30_days`, `within_90_days`,
`beyond_90_days` (bands open on the lower edge, closed on the upper; the seven counts
sum to the total UNLOCKED scheduled cards in scope — Sprint14 excludes locked cards;
cards flagged `needs_revalidation` stay counted in their FSRS due-date bands, so `due_now`
can exceed the focus queue and `open_count` by the number of flagged due cards). The 30-/90-day split feeds the review
screen's UPCOMING `≤3 mo` / `>3 mo` forecast columns. Same `topic` / `essay_id` /
`section_id` scoping rules as `GET /flashcards/due` (`section_id` without `essay_id`,
or `topic` with `essay_id`/`section_id` → `VALIDATION_ERROR`) — but **no** interval
filter: it always counts every unlocked scheduled card in scope, so the forecast
approximates the focus session it accompanies (`ReviewStatsPanel` passes the session's
scope through). Review-stats endpoints (`/review-stats/*`) are unchanged: they read
`review_events`, which a 'preserved' revalidation check never writes.

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

## Question levels and overview
Sprint 8. Decouples question/card maintenance from the essay import/export flow —
before this sprint, adding or editing one card required resending essay/section-shaped
JSON (`POST /essays/ingest` or the single-section export). The underlying schema needed
no redesign for this: `essaycards.flashcards` was already its own table with a stable
`id` and a `section_id` foreign key, never embedded in `essay_sections.body_markdown` or
any section JSON blob — the coupling was purely an API-layer gap. What was missing was a
narrow, card-only read/write pair.

**`level`** (see `## Glossary`) lives on `flashcards.level`, `not null default 2`,
`check (level >= 1)`, backfilled via the standard idempotent `alter table ... add column
if not exists` pattern already used for `essays.status` and
`flashcard_review_state.review_interval` — every pre-existing card got `2`
("building/explanatory"), a neutral guess absent any signal for which cards are
foundational vs. decorative. It is set **exclusively** by `POST /flashcards/upsert`
below; `backend/ingest.py`'s shared upsert core (used by both the markdown CLI and
`POST /essays/ingest`) has no `level` column in its INSERT or its `ON CONFLICT DO
UPDATE SET` list at all, so re-ingesting an essay or a section (`## Single-section
export / insert` below) can never read, write, or reset it — this is the actual
mechanism guaranteeing "essay edits don't touch level" and "level edits don't touch
essay content", not a runtime check.

**`GET /essays/{essay_id}/questions`** (`backend/routers/essays.py::list_essay_questions`)
— every flashcard in the essay, flat, each row carrying its `card_key`, `level`, and its
section's identity/order (`section_id`/`section_anchor_slug`/`section_heading`/
`section_order_index`). A Dataset, ordered `(section order_index asc, level asc,
created_at asc)`. Client-side grouping into section -> level, same pattern as
`EssayListView` already grouping essays by `category` from a flat row list — Datasets
are flat by contract (R-CON-BP-04); there is no nested JSON shape.

**Question overview** (`src/ShellEntry.tsx` → `QuestionOverviewView`,
`/essaycards/essays/:id/questions`, reached via a **Question overview** button in
`ReaderView`) — editorial, not review. For each section (essay order), each of Level 1 /
2 / 3 (always rendered, even empty, as "No questions at this level yet." — a gap is
something you *see*, not something you infer from an absent heading) **and any level
above 3 present in the data** (open-ended upward, ascending), lists its questions. A
question's border color (`levelBorderColor`) reads Level 1 as bold/primary, Level 2 as
medium/outline, Level 3+ as faint/outline-variant — existing Material 3 tokens, not a
new palette. Per question: **Edit** (inline textareas for q/a + a level number input,
`POST /flashcards/upsert`) and **Export** (below). Per level, **+ Add question** opens
an inline form (`AddQuestionForm`) that also posts to `POST /flashcards/upsert` with
`card.id` omitted, so the backend auto-generates a fresh id (`q-<8hex>`, mirroring but
not sharing code with `backend/exploration.py`'s `disc-<8hex>` generator).

**`POST /flashcards/upsert`** (`backend/routers/flashcards.py`) — the question-level
counterpart to `POST /essays/ingest`, sharing no code or validation with it. Body:
`{essay_slug, section_id, card: {id?, level, q, a}}`. Resolves the essay by slug,
requires `section_id` to already belong to it, then upserts by `(essay_id, card_key)`:
`card.id` matching an existing key updates that card in place (question/answer/level
change; id, section, essay all stable); `card.id` present but unmatched creates a card
with that id; `card.id` omitted creates one with an auto-generated id. `level` is
**required on every call, never defaulted** — an omitted level must never silently
reset an existing Level 1/3 card back to some default, so the caller (always pre-filled
from the card's current level) must state it explicitly every time. Rejects a `card.id`
that already exists under a *different* section (mirrors
`essays.py::_check_card_section_collisions`) — `section_id` is not in the update's `SET`
clause at all, so this endpoint cannot move a card between sections even by accident.
Never touches `essaycards.essays` or `essaycards.essay_sections`.

**Single-question AI export/import** — "Export" on a question (`QuestionItem` in
`QuestionOverviewView`) fetches `GET /flashcards/{flashcard_id}/export` and copies it,
plus `QUESTION_EXPORT_PROMPT_INTRO` (`src/ShellEntry.tsx`), to the clipboard, then
toggles to **Import →** (same pattern as `## Single-section export / insert`) routing to
`QuestionImportView` (`/essaycards/questions/import`). The export carries
`essay_slug`/`essay_title`/`section_id`/`section_anchor_slug`/`section_heading`/
`section_body_markdown` as **read-only context** (grounding for the AI conversation)
alongside `card: {id, level, q, a}` — the only part that is ever saved. This is enforced
structurally, not by convention: `POST /flashcards/upsert`'s body schema has no field for
section prose, heading, or essay title at all, so pasting the *entire unedited export*
back (context included) changes nothing but the card, because there is nothing on the
receiving end for that context to write to.

**`GET /essays/{essay_id}/export`** (`backend/routers/essays.py::export_essay`) — the
single-essay counterpart, sibling to the per-section export below (shares
`_ordered_sections_with_cards`): every current section, in order, with its cards, no
`focus_section_id`. Reimports through the existing `POST /essays/ingest` via "Add /
Update Essay" (**Export essay** button in `ReaderView`, same copy-then-toggle-to-Import
pattern). There was no bulk multi-essay export/import to restrict to one essay — ingest
has always taken exactly one `slug` per call: this fills the previously-missing
capability to export an *existing* essay's current content (as opposed to `STUB_PROMPT`,
which is a blank fill-in template for a brand new essay).

## Nuggets (Sprint09)
See `## Glossary` "Nuggets (Sprint09)" for the core vocabulary. This section is the
implementation contract.

**Schema.** `essaycards.nuggets` (`id`, `nugget_key` unique, `title`, `body_markdown`,
`created_at`/`updated_at`) and `essaycards.section_nuggets` (many-to-many,
`(section_id, nugget_id)` composite PK, both FKs `on delete cascade`) are new tables.
`flashcards.nugget_id` (nullable, `on delete set null`) and
`essays.main_spine_markdown` (`not null default ''`) are additive columns. All
additive/idempotent, per the existing `create table if not exists` /
`alter table ... add column if not exists` pattern.

**Reference resolution and resync.** `backend/ingest.py::extract_nugget_keys` strips
fenced code blocks and inline code spans, then matches `\[\[nugget:([a-zA-Z0-9_-]+)\]\]`
— the character class matches `SLUG_LIKE_RE` exactly, so any valid `nugget_key` (mixed
case included) is referenceable. `upsert_document`'s first step (before any write)
resolves the union of every referenced key across `main_spine_markdown` and every
section's `body_markdown` against `essaycards.nuggets`, raising `IngestionError` naming
every unresolved key at once if any is missing — identical on both the markdown CLI and
`POST /essays/ingest` JSON paths, because both share this one core. No placeholder
nugget is ever auto-created. Once a section's id is known, `section_nuggets` is fully
resynced to that section's current references (insert missing, delete stale) — the one
explicit exception to the app's general no-delete-on-re-ingest policy; it only ever
removes an association row, never a `nuggets` or `flashcards` row.

**`SLUG_LIKE_RE`** (`^[a-zA-Z0-9_-]+$`) lives in `backend/ingest.py`, promoted from what
was previously a private copy in `essays.py` — the one canonical definition
(`essays.py`, `nuggets.py` both import it; `flashcards.py`'s separate `_CARD_ID_RE`,
same pattern, is untouched).

**`essays.main_spine_markdown`** is settable via `POST /essays/ingest` only (optional
top-level key, default `''` on omission, same convention as `category`/`sort_index`/
`status`). The markdown-CLI front-matter grammar is unchanged — an essay ingested via
the CLI keeps `main_spine_markdown = ''` until edited through the JSON path.

**API** (`backend/routers/nuggets.py`, mounted at `/api/essaycards/nuggets`):
`GET ''` (list, no `body_markdown`), `GET '/{id}'` (detail), `POST '/upsert'`
(upsert-by-`nugget_key`), `GET '/{id}/flashcards'` (flat, no scheduling fields —
reviewing a nugget-linked card for real spaced repetition still goes through the
existing essay/section-scoped focus session; no nugget-scoped `/due` or `/stats` this
sprint), `GET '/{id}/sections'` ("referenced by"), `GET '/authoring-package'` and
`GET '/{id}/generate-flashcards-package'` (bespoke JSON, Dataset-exempt — ChatGPT round
trips, see below). Existing endpoints extended: essay detail/export/section-export gain
`main_spine_markdown`/`main_spine_nuggets`/per-section `nuggets`; question-overview rows
gain `section_nuggets`/`nugget_id`; `POST /flashcards/upsert` gains `nugget_id`
(omit/null/value tri-state, R-CON-AL-04); `GET /flashcards/due` and single-question
export gain `nugget_id`.

**Frontend rendering.** `remarkNuggetRefs` (a remark plugin, `src/ShellEntry.tsx`)
visits mdast `text` nodes and turns a resolved `[[nugget:key]]` into an in-app link
(`NuggetLink`, `href="nugget:<key>"`) or a non-clickable broken-link span for an
unresolved one (`href="nugget-missing:<key>"`) — fenced/inline code is already a
separate node type by the time remark hands off, so no hand-written stripping is
needed on the frontend (unlike the backend's regex-based `extract_nugget_keys`).
Clicking a resolved link opens `NuggetPanel`, an in-page overlay with its own
click-through id-stack — never a route navigation, so `ReaderView`/`ReviewSessionView`
never unmount and reading position / review-session state survive opening and closing
it. `ReviewSessionView`'s revealed-answer area shows "Flashcard → Nugget" (opens the
same overlay) when the current card's `nugget_id` is set, else the unchanged "Jump to
passage" route navigation.

**ChatGPT round trips**, same export → copy → discuss → paste → apply pattern as every
other round trip in this app: nugget authoring (`GET /nuggets/authoring-package` →
`POST /nuggets/upsert`, reachable via "+ New nugget" in `ReaderView` / "Edit nugget" in
`NuggetPanel`) and flashcard generation from a nugget (`GET
/nuggets/{id}/generate-flashcards-package` → one `POST /flashcards/upsert` per
AI-returned card, sequential, each pre-set with `nugget_id` — not atomic across the
batch, see Known gap below). The section spine-revision package
(`GET .../sections/{id}/export`) additionally carries `main_spine_markdown`,
`main_spine_nuggets`, and `focus_section_nuggets` (full body, focus section only); on
reimport, `IngestView` compares the returned focus section's current nugget keys
against a set stashed in `sessionStorage` at export time and shows a non-blocking
warning banner naming any accidentally-dropped reference (submission is never blocked).

**Known gap — ownership/cascade (documented, not guarded).** A flashcard reachable
through a shared nugget from another essay is still only *owned* by its own
`essay_id`/`section_id` (`flashcards.nugget_id` does not change this — see schema.sql's
comment on the column). Deleting the owning section or essay would remove the card even
though another essay still references it via the nugget. The app has no delete endpoint
anywhere today (essays/sections/flashcards/images are all upsert-only), so this risk has
no live trigger through the app; it is latent, not exercised. No app-level guard is
added — an explicit decision, same pattern as the Sprint02 card/section-move asymmetry.

**Known gap — non-atomic flashcard generation.** "Generate flashcards from a nugget"
issues one `POST /flashcards/upsert` per AI-generated card, not a single atomic batch —
if card *N* of *M* fails, cards `1..N-1` are already saved while `N..M` are not. The
import view reports per-card success/failure so a failed card can be retried
individually.

## Single-section export / insert
Revise one section, or insert a new one, with ChatGPT — without a dedicated import
endpoint. Deliberately reuses the whole-essay JSON round trip (`## Content ingestion`):
`GET /api/essaycards/essays/{essay_id}/sections/{section_id}/export`
(`backend/routers/essays.py::export_section`) returns a bespoke JSON blob (R-CON-BP-04
exemption, same rationale as `examination-package`/`exploration-package`) that IS already
a valid `POST /essays/ingest` payload — `title`/`slug`/`category`/`sort_index`/`status`
plus **every** current section (each with `section_id`/`heading`/`anchor_slug`/
`body_markdown`/`cards`), in order, plus `focus_section_id` naming which section the
request was for.

**Why the full array, not just the one section.** `POST /essays/ingest` assigns each
submitted section's `order_index` from its position in the payload's `sections` array
(`_validate_ingest_body`'s `"order_index": s_idx` / `_upsert_section`'s `on conflict do
update set order_index = excluded.order_index`) — never from a value carried in the
payload. A payload holding only the target section therefore always lands it at
`order_index` 0 on reimport, silently promoting any non-first section to the front of the
essay. Carrying the whole array at its current order means an unedited reply reproduces
every section's existing `order_index`; the export/insert prompts instruct the model to
return every entry but the one it was asked to change exactly as given, in place. (This
was a real bug in the original single-section-payload version of this feature, fixed
before it saw use beyond the one session that introduced it — see `git log` on
`backend/routers/essays.py::export_section` and the `preserves_order_for_non_first_section`
regression test in `tests/test_essays.py`.)

Two buttons at the end of each section in `ReaderView`, both toggling to **Import →**
(navigating to the existing `IngestView`, `/essaycards/ingest`) once something is copied —
same mechanism, different prompt:
- **Export section** — copies the package + `SECTION_EXPORT_PROMPT_INTRO`
  (`src/ShellEntry.tsx`) unmodified; the model is told to revise only the section named by
  `focus_section_id` and return every other entry byte-for-byte identical.
- **Insert section after** — `buildSectionInsertClipboardText` splices a blank
  instructional placeholder section (its field *values* are the fill-in instructions, same
  convention as `PLACEHOLDER_JSON`/`STUB_PROMPT`) into the array immediately after
  `focus_section_id`, client-side, before copying it with `SECTION_INSERT_PROMPT_INTRO`;
  the model fills in the placeholder and returns the whole array, everything else
  untouched. On reimport this is an ordinary `POST /essays/ingest` with one new
  `anchor_slug` — `upsert_document` inserts it and assigns its `order_index` from where it
  sits in the returned array, i.e. exactly where it was spliced in.

Because `upsert_document` still never touches a section or card absent from the payload
(`## Content ingestion`), and both flows always resubmit every section, nothing is ever
silently dropped — PROVIDED the essay-level fields round-trip unedited (the export
intentionally echoes the essay's current `category`/`sort_index`/`status` for this reason —
see `_validate_ingest_body` defaults). Same accepted gap as ingest generally: a card
removed from `cards` on reimport is left unchanged, not deleted.

## Oral examinations
(Sprint14 added scope, the 70% pass rule and state transitions on top of the round trip below
— see `## Section progression (Sprint14)`; `section_examinations` gained `passed`.)
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

**Nugget freshness (Sprint09, infrastructure only — not surfaced).** The export
package's `build_export_package` also attaches per-section `nugget_versions:
{nugget_key: live nuggets.updated_at}` for that section's currently-referenced
nuggets, mirroring the existing `section_version` field. Import accepts an optional
per-result `nugget_versions` and stores it **verbatim** (never recomputed) into the
new `section_examinations.nugget_versions_at` column — `null` means "predates this
feature" and skips the nugget-level check; absent on import stores `null` too. A pure
helper, `backend/examinations.py::nugget_freshness_flags(recorded, current)`, compares
a stored value against a freshly computed one and returns the changed/missing keys —
it exists and is tested, but is **not called by any endpoint or UI this sprint**; where
it is eventually surfaced is explicitly deferred.

## Flashcard exploration (Sprint06)
Explore a *single* flashcard with ChatGPT — deliberately action-neutral at export
time (the user does not pre-decide whether the problem is their own
misunderstanding, a bad question, a wrong answer, or a missing distinction; that
emerges from the conversation).

- **Export.** `GET /api/essaycards/flashcards/{flashcard_id}/exploration-package`
  returns a bespoke JSON blob (`export_version: 1`) — the card (identified by its
  **uuid** `card_id`, with `card_key` echoed for readability), its essay/section
  metadata, and a `context` object. EssayCards has **no card→paragraph linkage**;
  the finest context available is either the whole containing section
  (`context.section_body_markdown`, a legacy card whose `nugget_id` is null) or, for
  a nugget-linked card (Sprint09), the nugget's own independent explanation
  INSTEAD OF the section (`context.nugget_body_markdown` +
  `context.nugget_key`/`context.nugget_title` — a replacement, not an addition; see
  `## Nuggets`). Same R-CON-BP-04 exemption rationale as `examination-package`. The
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

## FSRS scheduling (Sprint12)
FSRS (`fsrs` PyPI package, FSRS-6) is the SOLE scheduler. Sprint10's
dual-scheduler A/B experiment (Classic vs FSRS, persistent 50/50 assignment,
the scheduler badge, the experiment dashboard) is retired in full: its
schema columns dropped, its router/UI deleted. The due-queue selection/
ordering mechanism (`## Due-queue ordering`, `## Queue stats`, Focus/Review
eligibility, the 24-hour learning/established threshold) remains completely
untouched by this — only the mechanism that computes `next_due_at` changed.

**`backend/scheduling.py`.** `VALID_GRADES` is unchanged. `ClassicScheduler`,
`compute_next_due_at`, and `decide_scheduler_assignment` are REMOVED (verified
safe to remove only after the migration and FSRS review dispatch were
confirmed correct by the test suite). `FSRSScheduler` is unchanged from
Sprint10: loads or creates an `fsrs.Card`, drives a module-level
`fsrs.Scheduler(desired_retention=DESIRED_RETENTION)`, library-default
parameters/learning_steps/relearning_steps. `DESIRED_RETENTION` (new) — a
module constant, `float(os.environ.get('ESSAYCARDS_FSRS_DESIRED_RETENTION',
'0.9'))`, read once at import time; no UI exposure this sprint (env-var-only
server setting). FSRS's own memory state (stability, difficulty, its internal
Learning/Review/Relearning state, step) remains a SEPARATE, additional
persisted concept (`essaycards.fsrs_card_state`) — never confused with or
substituted for `review_interval`. Rating mapping unchanged: direct 1:1 name
match (`again`/`hard`/`good`/`easy` -> `fsrs.Rating.Again`/`Hard`/`Good`/`Easy`);
every datetime handed to the library is normalized to exactly
`.astimezone(timezone.utc)` first.

**Review transaction.** `POST /flashcards/{id}/review` now ALWAYS dispatches
to `FSRSScheduler` — no scheduler column to read, no branch. Inside the same
transaction as the `flashcard_review_state` `UPDATE`, it always upserts
`essaycards.fsrs_card_state` and always inserts one `essaycards.review_events`
row (append-only; the `scheduler` column on this table is also dropped). New
card creation (`backend/ingest.py`, `backend/routers/flashcards.py::
_upsert_question`, `backend/exploration.py::execute_plan`'s `create_card`
branch) seeds a bare `flashcard_review_state` row with no scheduler metadata
at all.

**Legacy FSRS-state migration (documented approximation — R-OPS-BP-01).**
`backend/migrate_fsrs_state.py::migrate_legacy_fsrs_state`, invoked once at
every startup immediately after `init_schema()`: for every
`flashcard_review_state` row with `last_reviewed_at IS NOT NULL` and no
existing `fsrs_card_state` row, synthesizes initial FSRS state via
`backend.scheduling.estimate_initial_fsrs_state(review_interval,
last_reviewed_at, desired_retention)` — a pure, independently unit-testable
function. This is an APPROXIMATION, not a reconstruction of real review
history: no complete per-review rating history exists anywhere in this schema
to replay. Stability is inverted from FSRS-6's own
interval-from-stability-and-retention formula, reading `FACTOR`/`DECAY`
directly off the live `fsrs.Scheduler` instance (never hardcoded literals —
they are themselves trainable-parameter-derived and would silently drift from
whatever parameter vector the scheduler actually uses). Difficulty is
obtained by running one `review_card()` call on a fresh `fsrs.Card()` with a
neutral `Rating.Good`, timestamped at the card's own `last_reviewed_at` — not
hand-derived, so it stays correct across a library version bump. Each row is
backfilled in its own small transaction (one bad row logs and is skipped, not
a startup failure); a skipped row falls back to a fresh `fsrs.Card()` on its
next real review, same as a never-reviewed card. Never writes
`next_due_at`/`review_interval`/`last_reviewed_at` — those are read-only
inputs to the synthesis, never its targets.

**Schema migration.** `essaycards.pre_fsrs_migration_backup_sprint12` — a new,
retained-indefinitely audit table (no pruning policy yet), created and
populated from the Sprint10 scheduler-assignment columns BEFORE they are
dropped, guarded by both the backup table's own absence and the source
`scheduler` column still existing (so it is correctly a no-op on a fresh
database that never had those columns, not just on a rerun). `schema.sql`
then drops `flashcard_review_state.scheduler` /
`scheduler_assigned_at` / `scheduler_assignment_reason` / `experiment_version`
and `review_events.scheduler`. The old Sprint10 `ADD COLUMN`/`CREATE INDEX`/
backfill-`UPDATE` statements for these columns are NOT reproduced in
`schema.sql` — keeping an add-then-drop pair for a permanently retired column
in the same idempotently-rerun file would churn forever (add — drop — add —
drop — ...) rather than converging; see the file's own "Sprint10_DualSchedulerAB
(retired by Sprint12)" comment block.

## Section progression (Sprint14)
Replaces Sprint12's `## Learning progress` (the four-milestone `learning_level` and its nine
fields are gone). Everything below is DERIVED at query time from stored oral state plus
`flashcard_review_state.review_interval` — no traffic-light color is ever stored. All state
SQL lives in `backend/progress.py`; the pass rule and oral-state transitions live in
`backend/oral_state.py`; revalidation primitives in `backend/revalidation.py`.

**Pass rule.** See the Glossary: passed iff score >= 5 of 6 (70%). Computed once at import,
stored in `section_examinations.passed` / `essay_examinations.passed`; nothing re-derives it.
The package's `scoring` block echoes the rule so prompts and verdicts cannot drift.

**Section state** (highest satisfied wins): `blue` iff section unguided passed; else `green`
iff guided passed AND >= 1 card AND every card seen with `review_interval >= 24h`; else
`yellow` iff guided passed; else `grey`. A guided-passed section with zero cards is yellow,
never green. Blue needs only the unguided pass (an unguided pass on a never-guided section is
blue). `GET /progress/sections` returns one row per section (flat; client groups by
`essay_id`) with `state`, `next_step`, scores, passed dates, `cards_total`/`cards_established`,
`is_locked`.

**Essay state** (highest satisfied wins): `violet` iff essay unguided passed; else `blue` iff
>= 1 section and every section unguided passed; else `green` iff >= 1 card and every card
`review_interval >= 30 days` (learned); else `yellow` iff guided ESSAY oral passed (section
guided orals never count); else `grey`. Zero-card / zero-section essays are never vacuously
green/blue.

**Unlock.** A card is eligible for review only if its section's `section_oral_state` row has
`guided_passed`. Cards stay stored and counted; a card added later to an already-passed
section is unlocked automatically. `POST /flashcards/{id}/review` on a locked card is
`VALIDATION_ERROR` (no write). `GET /essays/{id}/questions` rows carry `is_locked`,
`card_state` (`locked|new|learning|established|learned`) and `needs_revalidation`.
Existing sections were grandfathered once at migration (`guided_pass_source =
'grandfathered'`: any reviewed card, or a guided exam scored >= 3).

**Oral import.** `POST /examinations/import` results carry a required `scope`
(`section` | `essay`). `section` needs `section_anchor_slug` + `section_version`; `essay`
must omit or null `section_anchor_slug` (omitted == null) and ignores `section_version` /
`nugget_versions`. All-or-nothing in one transaction; transitions apply in server import
order. Guided pass is sticky (a later failing guided attempt only updates the latest score).
A failing unguided SECTION attempt only records history. The response adds per result
`scope`, `passed`, `score_percent`, `effects`, and a top-level `revalidation` list.
`GET /essays/{id}/examination-package` now requires `exam_type` AND `scope`
(`section` also requires `section_id`; `essay` forbids it); `GET /essays/{id}/examinations`
lists whole-essay attempts.

**Failure cascade.** A failing unguided ESSAY attempt made while the essay was Violet, in the
same transaction: clears essay unguided pass (`unguided_invalidated_at = now()`), clears every
section's unguided pass, and flags every card of the essay that has been reviewed at least once
(`needs_revalidation = true`). Untouched: guided state, all attempt history, FSRS state, due
dates, intervals. A failing unguided essay attempt while NOT Violet is history-only.

**Revalidation.** Flagged cards are served by `GET /flashcards/revalidation` (any due date) and
excluded from `GET /flashcards/due`. The review endpoint derives the mode from the flag:
grade `again` = incorrect, any other grade = correct. Correct: flag cleared, an audit row in
`revalidation_events` (`preserved`), and NOTHING else changes (no FSRS call, no `review_events`
row). Incorrect: flag cleared and the normal FSRS failure path runs, plus a `failed` audit row.
The review UI in `?revalidate=1` mode shows exactly two buttons: Correct (sends `good`) and
Incorrect (sends `again`). Revalidation of an essay is complete when its pending count is 0.

**UI.** Overview: one large `EssayProgressDot` + one small dot per section (`SectionProgressDots`);
dots are native buttons with title + aria-label, their click stops propagation so they never also
open the essay row; a collapsed `ProgressLegend`; a `Revalidate (N)` control when pending > 0.
Reader: locked sections show a lock hint and a disabled "Review this section"; section menus
offer section-scope orals, the essay menu whole-essay orals.

**Known gaps (documented, not guarded).** State transitions follow server import order, not
`examined_at` order; editing a section after its oral pass does not invalidate the pass;
re-importing an identical failing result double-applies at most once (a second failing result is
history-only because the claim is already false).

## Button and nav consolidation (Sprint12)
Essay/section button rows are replaced by a reusable `ActionMenu` component
(`src/ShellEntry.tsx`) — a primary button plus an accessible dropdown
(`role=menu`/`menuitem`, Escape + click-outside to close, keyboard-operable).
Used at two sites:
- **Essay header** (`ReaderView`) — primary = Study (focus session on the
  whole essay, when it has cards) or Question overview (fallback, when it has
  none); secondary dropdown = Question overview (when not primary), Guided
  oral exam, Unguided oral exam (both gated on `status === 'complete'`),
  Export essay / Import, + New nugget (gated on `sections.length > 0`). The
  `← All essays` back button stays standalone, never folded into the menu.
- **Section end** (`ReaderView`) — primary = Review this section; secondary
  dropdown = Export section / Import, Insert section after / Import.
  `SectionExaminationHistory` is unaffected, sitting below the menu as before.

Every pre-existing action is preserved somewhere post-consolidation — none
silently dropped (see `Sprint12_FSRSAndUXOverhaul/10_architecture.json
§button_nav_inventory` for the complete pre -> post mapping).

**Category collapse** (`EssayListView`). Each category heading gets a
collapse/expand toggle (▸/▾ chevron, same glyph convention as
`SectionExaminationHistory`), persisted via `localStorage` key
`essaycards:categoryCollapsed:<category>` (`UNCATEGORIZED` for the
null-category group), defaulting expanded when no stored value exists. The
heading row (title, established/total, open count, the per-category Study
button) always stays visible; only the essay rows beneath it collapse/hide.

**Nav regrouping** (`src/shellConfig.ts`). `mobilePrimaryNav` trimmed to
Essays / Due for review / Stats (the everyday-learning + stats items).
Add / Update Essay moves to the new `secondaryMenu` (the Shell's existing
mobile "More" overlay). `desktopNav` keeps all four items (no group concept
in the Shell's current `AppConfig`/`NavItem` contract — R-CON-BP-06; desktop
"grouping" is order-only). The Experiment nav entry is removed entirely.

## Port
EssayCards backend runs on host port 8024 (container port 8000).

## Schema
essaycards schema in the shared Atlas Postgres instance.
Tables: essaycards.essays, essaycards.essay_sections, essaycards.flashcards,
essaycards.flashcard_review_state, essaycards.section_examinations (append-only,
gains `exam_type` in Sprint12), essaycards.flashcard_discussions,
essaycards.flashcard_revisions (Sprint06 — flashcard exploration; the app
never updates/deletes rows in either), essaycards.fsrs_card_state,
essaycards.review_events (append-only; its Sprint10-only `scheduler` column
was dropped in Sprint12), essaycards.pre_fsrs_migration_backup_sprint12
(Sprint12 — one-time audit snapshot of the retired Sprint10 scheduler-
assignment data, retained indefinitely, never read by live code — see
`## FSRS scheduling (Sprint12)`), and (Sprint14) essaycards.essay_examinations
(append-only), essaycards.section_oral_state, essaycards.essay_oral_state,
essaycards.revalidation_events (append-only), plus `section_examinations.passed` and
`flashcard_review_state.needs_revalidation`.
Schema initialized idempotently at startup from schema.sql.

`00_architecture/schema.sql` is a design copy that `make essaycards-schema` feeds
to psql; it is already one sprint stale (missing `essaycards.images`). The
canonical runtime schema is `03_Application/EssayCards/schema.sql` (per
architecture.json), applied by `init_schema()` at startup and by conftest.

## Test convention: no system-wide literal counts

Tests must not assert exact system-wide aggregate counts that depend on the whole
fixture world (e.g. `total == 47`, per-band totals across all essays). Assert
deltas (count before/after the action under test) or counts scoped to the fixture
rows the test itself created. Rationale: every sprint that gated or added fixture
data (Sprint10, Sprint12, Sprint14) broke unrelated global-count tests; see
`00_Blueprint/Quality/Rule_Audit_2026-10-11.md` T9. Adopted 2026-10-11; existing
literal-count tests are migrated opportunistically, not in a sweep.
