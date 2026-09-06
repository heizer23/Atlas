# CLAUDE.md

This file contains app-local guidance only.
Global architecture and development rules are defined in the repository root CLAUDE.md.

## App
EssayCards pairs long-form essay reading with spaced-repetition flashcards. A flashcard
always links back to the essay passage that taught it; the reader lets the user jump
into review at the end of each section, and a global "Due for review" queue surfaces
cards from every section as they come due over time.

## Sprint scope
- Sprint 1: One-shot markdown ingestion CLI, essay/section/flashcard data model, due-queue
  review loop with floor/doubling SRS scheduling, minimal React reader + review session UI.
- Sprint 2: `POST /api/essaycards/essays/ingest` JSON ingestion endpoint plus an in-app
  "Add / Update Essay" paste-JSON UI, sharing one upsert core with the markdown CLI path.
- Sprint 5: two-category ordering for `GET /flashcards/due` (see `## Due-queue ordering`).

## Content ingestion
Essays can be ingested two ways — both upsert by the same stable author-assigned keys
(slug / (essay_id, anchor_slug) / (essay_id, card_key)) and both call the single shared
`backend.ingest.upsert_document(conn, doc)` core, so re-ingestion via either path never
resets a flashcard's review state.

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
`GET /api/essaycards/flashcards/due` — eligibility is unchanged (`next_due_at <=
now()`), but eligible cards are returned in two categories, **RECENT entirely
before BACKLOG** (Sprint05):

- **RECENT** — `last_reviewed_at >= now() - interval '24 hours'` (a rolling
  window off Postgres `now()`, *not* a calendar day / "reviewed today"; a
  never-reviewed card is never RECENT). Sorted by `next_due_at` **DESC** —
  closest-to-now first — so a card the user just pushed a few minutes out
  re-enters near the front once that delay elapses. Serves relearning.
- **BACKLOG** — everything else eligible. Sorted by the interval the card is
  currently scheduled across, `next_due_at - last_reviewed_at`, **DESC**
  (longest first). Overdue duration is deliberately ignored. A never-reviewed
  card has interval 0 (`last_reviewed_at IS NULL`, seeded by `ingest.py`) and
  sorts behind every reviewed backlog card — no separate new-card queue.
- Tie-breakers: `next_due_at ASC`, then `f.id ASC`.

`last_reviewed_at` (on `flashcard_review_state`, written by `POST .../review`
from a single `select now()`) is the sole source of truth — EssayCards has no
per-review history table. All ordering logic is one SQL `ORDER BY` in
`list_due_flashcards`; the review UI renders `rows` in server order.

## Queue stats
`GET /api/essaycards/flashcards/stats` — review-queue forecast. Returns a Dataset of
exactly six zero-filled rows partitioning every flashcard that has a review-state row
into non-overlapping horizon bands by `next_due_at` vs Postgres `now()`: `due_now`,
`within_10_min`, `within_1_day`, `within_7_days`, `within_30_days`, `beyond_30_days`
(bands open on the lower edge, closed on the upper; the six counts sum to the total
scheduled cards in scope). Same `essay_id` / `section_id` scoping rules as
`GET /flashcards/due` (`section_id` without `essay_id` → `VALIDATION_ERROR`). Rendered
as the "Queue forecast" strip at the top of the review screen (`QueueForecastPanel` in
`src/ShellEntry.tsx`), which re-fetches after each graded card.

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

## Port
EssayCards backend runs on host port 8024 (container port 8000).

## Schema
essaycards schema in the shared Atlas Postgres instance.
Tables: essaycards.essays, essaycards.essay_sections, essaycards.flashcards,
essaycards.flashcard_review_state, essaycards.section_examinations (append-only).
Schema initialized idempotently at startup from schema.sql.
