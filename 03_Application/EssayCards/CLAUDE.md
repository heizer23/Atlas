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
essaycards.flashcard_review_state.
Schema initialized idempotently at startup from schema.sql.
