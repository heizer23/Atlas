# Sprint Draft — EssayCards: JSON Ingestion Endpoint + Upload UI

## Goal

Add a second ingestion path — an HTTP JSON endpoint plus an in-app upload form — for
creating new essays and adding/updating flashcards, so content no longer requires
hand-authoring a markdown file and running the CLI inside the container. This coexists
with the Sprint01 markdown/CLI path; both share the same underlying upsert logic so
they behave identically for equivalent content.

## Layer

03_Application

## Component

EssayCards (Sprint02, building on Sprint01_Core)

## Scope

- `POST /api/essaycards/essays/ingest` — accepts one JSON payload describing an essay,
  its sections, and their flashcards. Creates the essay if its `slug` is new; upserts
  sections/flashcards onto an existing essay if the `slug` already exists.
- Shares the **same upsert core** the Sprint01 markdown CLI (`backend/ingest.py`) already
  uses — refactor so both the CLI path (markdown → parsed structure → upsert) and the
  new API path (JSON → parsed structure → upsert) call one shared function. Do not
  duplicate the upsert logic.
- In-app "Add / Update Essay" UI: a page with a JSON textarea and a submit button,
  showing either a success summary (sections/cards created vs. updated) or validation
  errors inline.
- Minimal essay picker: since this endpoint can create essays beyond the single one
  Sprint01 seeded, add a simple list view (`GET /api/essaycards/essays`, already built)
  so the user can navigate to any ingested essay — not just the first. This is required
  for the feature to be usable at all once more than one essay can exist; it is not the
  "multi-essay library" experience Sprint01 explicitly deferred, just a plain list with
  links into the reader.

## Out of Scope

- Uploading/editing markdown files through the UI (the CLI path is unchanged and stays
  file-based)
- Deleting essays, sections, or flashcards via this endpoint or the UI
- Any reconciliation of sections/cards that exist in the DB but are omitted from a
  given JSON payload (see Partial Update Semantics below — same accepted gap as
  Sprint01's markdown path, not being solved here either)
- Authentication on the new endpoint — Atlas has no per-app auth layer anywhere in the
  repo (every component binds to `127.0.0.1` behind the shell/internal docker network,
  confirmed by checking TaskTracker/Calendar). This endpoint follows that same existing
  convention. Flagging per R-OPS-BP-02: this does turn a previously CLI/`docker exec`
  -gated write operation into an HTTP-reachable one, which is a real increase in
  reachable surface even though it's still bound to `127.0.0.1`. If that tradeoff is
  wrong, say so now — it's an explicit decision, not an oversight.
- Full multi-essay reader experience (topic switcher, essay metadata editing, etc.)

## Partial Update Semantics (R-CON-AL-04 / R-CON-AL-05)

For an existing essay (`slug` already in the DB):
- Sections present in the payload are upserted (matched by `anchor_slug`): new ones
  created, existing ones have `heading`/`body_markdown` updated.
- Sections that exist in the DB for this essay but are **not present** in the payload
  are left untouched — not deleted, not modified. Same rule for flashcards within a
  submitted section (matched by `id`): cards omitted from the payload are left as-is.
- A flashcard's `q`/`a` text updates in place when resubmitted with the same `id`; its
  `FlashcardReviewState` (`last_reviewed_at`, `next_due_at`) is never touched by ingestion
  — identical rule to Sprint01's markdown path.
- There is no "replace this essay's sections wholesale" mode in this sprint — every
  ingest call is additive/updating only, never subtractive.

## API

### `POST /api/essaycards/essays/ingest`

Request body:

```json
{
  "title": "string, required, non-empty",
  "slug": "string, required, non-empty, matches ^[a-zA-Z0-9_-]+$",
  "sections": [
    {
      "heading": "string, required, non-empty",
      "anchor_slug": "string, required, matches ^[a-zA-Z0-9_-]+$, unique within this payload",
      "body_markdown": "string, required (may be empty string)",
      "cards": [
        { "id": "string, required, matches ^[a-zA-Z0-9_-]+$, unique within this essay (across all sections, existing + incoming)",
          "q": "string, required, non-empty",
          "a": "string, required, non-empty" }
      ]
    }
  ]
}
```

Rules:
- `sections` must contain at least one entry.
- `order_index` for each section is derived from its position in the `sections` array
  (0-based) — no explicit `order_index` field in the payload. Re-ingesting with a
  different array order for existing sections updates their `order_index`.
- `cards` may be an empty array (a section can have zero flashcards).
- **Validation is all-or-nothing (R-CON-AL-02/03):** the entire payload is structurally
  and semantically validated (required fields, format, in-payload uniqueness of
  `anchor_slug` and `id`) before any database write. If any part fails, nothing is
  written — same transactional guarantee as the existing markdown `ingest()` function.
- **This endpoint must not use a Pydantic request-body model for validation.** Sprint01's
  design review (`11_design_review.md`, round 1) found that FastAPI's default handling
  of Pydantic body validation errors bypasses the `ApiError` envelope required by
  R-CON-BP-04, because Atlas's shared exception handler
  (`platform_errorhandling` — see `02_Platform/03_ErrorHandling/`) only catches generic
  `Exception`, not `RequestValidationError`. Sprint01 fixed this for `POST .../review`
  by validating the raw JSON body manually. This endpoint has a much larger/nested body,
  so the same requirement applies with more force — manual validation returning
  `ApiError` on any failure, not a Pydantic model. (Note for the designer: Calendar's
  `POST /events` was found to still have this same unfixed gap — do not use it as a
  reference pattern.)

Success response: `200` with a typed record:
```json
{ "essay_id": "...", "slug": "...", "sections_created": 0, "sections_updated": 0,
  "cards_created": 0, "cards_updated": 0 }
```

Error response: `ApiError`, for any validation failure (missing/empty required field,
bad slug/anchor/id format, duplicate `anchor_slug` or `id` within the payload, `id`
collision with an existing card in a *different* section of the same essay).

## UI

- New "Add / Update Essay" view (reachable from a nav entry in the EssayCards app):
  a textarea for pasting the JSON payload and a submit button.
  - On success: show the summary counts from the response and a link to open the
    essay in the reader.
  - On failure: show the `ApiError` message/detail inline, do not clear the textarea
    (so the user can fix and resubmit without retyping).
- New essay list/picker view: reachable from the EssayCards app's top-level nav,
  listing all essays (`GET /api/essaycards/essays`) with a link into the reader for
  each. This is the only navigation change needed to make multiple essays usable —
  no other Sprint01 UI changes required.

## Data Model

No schema changes. Reuses `Essay`, `EssaySection`, `Flashcard`, `FlashcardReviewState`
exactly as defined in Sprint01_Core's `10_schema.sql`.

## Open Design Questions (for design review)

- Confirm the shared-upsert-core refactor doesn't change any observable behavior of the
  existing markdown CLI path — Sprint01's test suite (36 tests, all passing) should
  still pass unchanged after the refactor, and is the regression check for this.
- Confirm whether `POST .../ingest` needs its own dedicated test spec scenarios for the
  all-or-nothing rollback case (payload with one invalid section among several valid
  ones) — R-CON-AL-01 requires empty/error-result behavior to be explicit and tested,
  not just described.
