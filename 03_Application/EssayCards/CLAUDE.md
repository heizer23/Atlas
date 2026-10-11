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

## Frontend layout (`src/`)
`ShellEntry.tsx` is only the route table. `types.ts` (API row types), `styles.ts`, `format.ts`,
`prompts.ts` (all clipboard helpers + AI prompt text), `nuggets.tsx` (nugget rendering/panel),
`components/` (ActionMenu, Progress dots, ReviewStatsPanel/ForecastGrid, ExaminationHistory),
`views/` (one file per routed view). New view -> `views/<Name>View.tsx` + a `<Route>` in `ShellEntry.tsx`.

## Reference docs (`docs/`)
Detailed per-area behavior was split out of this file. Read the matching doc before changing that area.
Cross-references written as `## Heading` elsewhere in these files resolve via this map.

| Doc | Contains (headings) |
|---|---|
| `docs/sprint_history.md` | Per-sprint scope summary (historical). Headings: `Sprint scope` |
| `docs/ingestion.md` | Markdown CLI + JSON ingest paths, essay overview metadata (`category`, `sort_index`, `status`). Headings: `Content ingestion` |
| `docs/images.md` | Image import (staging + browser upload), idempotency, backup caveats. Headings: `Images` |
| `docs/scheduling.md` | Due-queue ordering, roadmap/focus/review, queue stats, FSRS scheduling. Headings: `Due-queue ordering`; `Roadmap, focus and review`; `Queue stats`; `FSRS scheduling (Sprint12)` |
| `docs/llm_protocols.md` | Table of all external-AI export → import flows (endpoints, prompts, import views). Headings: `External-AI flows` |
| `docs/review_ui.md` | `ReviewSessionView` / `ReviewStatsPanel`, button and nav consolidation. Headings: `Review screen`; `Button and nav consolidation (Sprint12)` |
| `docs/question_levels.md` | Card `level`, question-overview screen, single-question maintenance. Headings: `Question levels and overview` |
| `docs/nuggets.md` | Nugget model, `[[nugget:key]]` references, nugget endpoints/UI. Headings: `Nuggets (Sprint09)` |
| `docs/export_insert.md` | Section export/insert flow. Headings: `Single-section export / insert` |
| `docs/oral_progression.md` | Oral examinations, traffic lights, locking, revalidation. Headings: `Oral examinations`; `Section progression (Sprint14)` |
| `docs/exploration.md` | Explore-a-card-with-ChatGPT package/import flow. Headings: `Flashcard exploration (Sprint06)` |

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

`make essaycards-schema` feeds the runtime `schema.sql` (idempotent) to psql. `00_architecture/schema.sql`
is a snapshot copy of it (refresh on sprint close; the Makefile does not use it). The
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
