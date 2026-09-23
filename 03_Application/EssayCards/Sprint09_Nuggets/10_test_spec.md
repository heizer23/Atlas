# Test Spec — EssayCards — Sprint09_Nuggets

## Scope
Covers the new nuggets router and data model (`essaycards.nuggets`, `essaycards.section_nuggets`), the
unified `[[nugget:key]]` reference validation and resync inside `backend.ingest.upsert_document` (both
ingestion paths), `essays.main_spine_markdown`, `flashcards.nugget_id` (tri-state upsert, due/export
rows), the nugget-sourced flashcard-exploration context branch, and the examination `nugget_versions`
echo-through plus the standalone `nugget_freshness_flags` helper. Out of scope: the existing
markdown/JSON ingestion happy paths, due-queue scheduling/ordering, oral-examination scoring, and image
import (all unchanged this sprint and covered by their existing tests). The "wherever ultimately
surfaced" freshness UI/endpoint is explicitly not built this sprint (see `10_architecture.json`
non_goals) and has no scenario below beyond the pure `nugget_freshness_flags` helper.

Correction round (`11_design_review.md`) additionally covers: `extract_nugget_keys`'s character-class fix
for mixed-case `nugget_key`s (Minimal Change Set item 1), `main_spine_nuggets` resolving a nugget
referenced only in `main_spine_markdown` (Minimal Change Set item 2), and `nugget_id` on
`GET /essays/{essay_id}/questions` rows plus QuestionOverviewView's edit-form nugget assignment control
(Minimal Change Set item 3).

Scenarios reference fixture objects by name where relevant (e.g. the fixture nugget `fix-nugget-cogito`).

## Scenarios

### List nuggets returns a Dataset ordered by title
- **Given:** the fixture nuggets `fix-nugget-cogito` ("Cogito") and `fix-nugget-wax` ("Wax and the Intellect").
- **When:** `GET /api/essaycards/nuggets` is called.
- **Then:** the response is a `Dataset` with `meta.object_type` `"nugget"`; rows are ordered by `title`
  ascending; each row carries `id`, `nugget_key`, `title`, `created_at`, `updated_at` and does NOT carry
  `body_markdown`.

### List nuggets is valid when empty
- **Given:** no `essaycards.nuggets` rows.
- **When:** `GET /api/essaycards/nuggets` is called.
- **Then:** the response is a `Dataset` with `rows: []` and `meta.total: 0` — not an error.

### Nugget detail includes body_markdown
- **Given:** the fixture nugget `fix-nugget-cogito`.
- **When:** `GET /api/essaycards/nuggets/{id}` is called for its id.
- **Then:** the response is a `Dataset` single row carrying `nugget_key`, `title`, and `body_markdown`.

### Nugget detail with an unknown id returns 404
- **Given:** no `essaycards.nuggets` row for a given id.
- **When:** `GET /api/essaycards/nuggets/{id}` is called with that id.
- **Then:** the response is a `404` `ApiError` with `error.code` `NOT_FOUND`.

### Nugget upsert creates, then updates by key without changing the id or key
- **Given:** no nugget exists with `nugget_key` `"new-concept"`.
- **When:** `POST /api/essaycards/nuggets/upsert` is called with `{nugget_key: "new-concept", title: "Draft Title", body_markdown: "..."}`, then called again with the same `nugget_key` and a different `title`/`body_markdown`.
- **Then:** the first call creates a row (`created: true`) with a new `id`; the second call returns the SAME `id` and `nugget_key`, `created: false`, and the row's `title`/`body_markdown` reflect the second call's values.

### Nugget upsert rejects a missing or blank required field
- **Given:** a request body missing `nugget_key`, or with `title` as an empty string.
- **When:** `POST /api/essaycards/nuggets/upsert` is called.
- **Then:** the response is a `400` `ApiError` with `error.code` `VALIDATION_ERROR`; no row is written.

### Nugget upsert rejects a key violating the slug pattern
- **Given:** a request body with `nugget_key: "not a valid key!"`.
- **When:** `POST /api/essaycards/nuggets/upsert` is called.
- **Then:** the response is a `400` `ApiError` with `error.code` `VALIDATION_ERROR`; no row is written.

### Nugget flashcards lists linked cards with no scheduling fields
- **Given:** the fixture nugget `fix-nugget-cogito` with one fixture flashcard whose `nugget_id` points to it.
- **When:** `GET /api/essaycards/nuggets/{id}/flashcards` is called for that nugget's id.
- **Then:** the response is a `Dataset` whose rows include that flashcard's `id`, `card_key`, `question`, `answer`, `level`, `essay_id`, `section_id`, and do NOT include `next_due_at`, `is_new`, `is_recent`, or `scheduled_interval_seconds`.

### Nugget flashcards for an unknown nugget id returns 404
- **Given:** no `essaycards.nuggets` row for a given id.
- **When:** `GET /api/essaycards/nuggets/{id}/flashcards` is called with that id.
- **Then:** the response is a `404` `ApiError` with `error.code` `NOT_FOUND`.

### Nugget sections lists every section referencing a shared nugget
- **Given:** the fixture nugget `fix-nugget-cogito` referenced by two fixture sections belonging to two different fixture essays.
- **When:** `GET /api/essaycards/nuggets/{id}/sections` is called for that nugget's id.
- **Then:** the response is a `Dataset` with exactly two rows, each carrying `section_id`, `anchor_slug`, `heading`, `essay_id`, `essay_title`, `essay_slug`, ordered by essay title then section order_index.

### Nugget sections for an unknown nugget id returns 404
- **Given:** no `essaycards.nuggets` row for a given id.
- **When:** `GET /api/essaycards/nuggets/{id}/sections` is called with that id.
- **Then:** the response is a `404` `ApiError` with `error.code` `NOT_FOUND`.

### Authoring package for an existing nugget includes its connected nuggets
- **Given:** the fixture nugget `fix-nugget-wax`, whose `body_markdown` itself references `fix-nugget-cogito`, in the context of a fixture essay/section.
- **When:** `GET /api/essaycards/nuggets/authoring-package?essay_id=<essay>&section_id=<section>&nugget_id=<fix-nugget-wax id>` is called.
- **Then:** the response is `200` with `nugget` carrying `fix-nugget-wax`'s `nugget_key`/`title`/`body_markdown`, and `connected_nuggets` including `{nugget_key: "fix-nugget-cogito", title: "Cogito"}`; `essay.main_spine_markdown` and `section.body_markdown` are present as read-only context.

### Authoring package with nugget_id omitted describes a new nugget
- **Given:** a valid fixture essay/section context, no `nugget_id` supplied.
- **When:** `GET /api/essaycards/nuggets/authoring-package?essay_id=<essay>&section_id=<section>` is called.
- **Then:** the response is `200` with `nugget: null` and `connected_nuggets: []`.

### Authoring package with an unresolvable context returns 404
- **Given:** an `essay_id` that does not exist, or a `section_id` that does not belong to the given `essay_id`, or a `nugget_id` that does not exist.
- **When:** `GET /api/essaycards/nuggets/authoring-package` is called with each of these in turn.
- **Then:** each response is a `404` `ApiError` with `error.code` `NOT_FOUND`.

### Generate-flashcards package includes the nugget's existing flashcards
- **Given:** the fixture nugget `fix-nugget-cogito` with one linked fixture flashcard, in the context of a fixture essay/section.
- **When:** `GET /api/essaycards/nuggets/{id}/generate-flashcards-package?essay_id=<essay>&section_id=<section>` is called for that nugget's id.
- **Then:** the response is `200` with `nugget: {nugget_key, title, body_markdown}`, `existing_flashcards` including the linked fixture card, and `context: {essay_slug, section_id}` matching the given essay/section.

### Generate-flashcards package with an unresolvable nugget or context returns 404
- **Given:** an unknown nugget id, or a valid nugget id with an unknown `essay_id`/`section_id`.
- **When:** `GET /api/essaycards/nuggets/{id}/generate-flashcards-package` is called with each of these in turn.
- **Then:** each response is a `404` `ApiError` with `error.code` `NOT_FOUND`.

### Markdown ingest resolves an existing nugget reference and resyncs section_nuggets
- **Given:** the fixture nugget `fix-nugget-cogito` and a markdown fixture file whose section body contains `[[nugget:fix-nugget-cogito]]`.
- **When:** the file is ingested via `backend.ingest.ingest()`.
- **Then:** ingestion succeeds; a `section_nuggets` row now associates the new section with `fix-nugget-cogito`.

### Markdown ingest with an unresolved nugget reference writes nothing
- **Given:** a markdown fixture file whose section body contains `[[nugget:does-not-exist]]` and `[[nugget:also-missing]]`.
- **When:** the file is ingested via `backend.ingest.ingest()`.
- **Then:** an `IngestionError` is raised naming BOTH missing keys; no essay, section, card, or `section_nuggets` row is written.

### Markdown reference resolves a mixed-case nugget_key
- **Given:** a fixture nugget whose `nugget_key` contains an uppercase letter (e.g. `fix-nugget-MixedCase`) and a markdown fixture section body containing `[[nugget:fix-nugget-MixedCase]]` written with matching case.
- **When:** the file is ingested via `backend.ingest.ingest()`.
- **Then:** ingestion succeeds; a `section_nuggets` row associates the new section with `fix-nugget-MixedCase` — demonstrating that `extract_nugget_keys`'s character class now matches `SLUG_LIKE_RE`, so a mixed-case key is referenceable (11_design_review.md Confirmed Problem 1 / Minimal Change Set item 1).

### JSON ingest with an unresolved nugget reference returns VALIDATION_ERROR
- **Given:** a `POST /api/essaycards/essays/ingest` payload whose section `body_markdown` contains `[[nugget:does-not-exist]]`.
- **When:** the request is made.
- **Then:** the response is a `400` `ApiError` with `error.code` `VALIDATION_ERROR` naming the missing key; no essay, section, or card row is written — demonstrating the same validation outcome as the markdown-path scenario above (unified check).

### Re-ingesting a section that drops a nugget reference removes only the association
- **Given:** a fixture section currently associated (via `section_nuggets`) with `fix-nugget-cogito`, whose `body_markdown` no longer contains `[[nugget:fix-nugget-cogito]]` in a new ingest payload for the same section.
- **When:** the section is re-ingested (either path).
- **Then:** the `section_nuggets` row for that `(section_id, fix-nugget-cogito)` pair is gone; the `essaycards.nuggets` row for `fix-nugget-cogito` still exists; no `flashcards` row is affected.

### Ingest round-trips main_spine_markdown
- **Given:** a `POST /api/essaycards/essays/ingest` payload with a non-empty top-level `main_spine_markdown`.
- **When:** the essay is ingested, then `GET /api/essaycards/essays/{essay_id}` is called.
- **Then:** the detail response's `main_spine_markdown` equals what was submitted.

### Essay detail sections carry their referenced nuggets
- **Given:** a fixture essay whose fixture section references `fix-nugget-cogito`.
- **When:** `GET /api/essaycards/essays/{essay_id}` is called.
- **Then:** the matching entry in `sections[].nuggets` includes `{nugget_key: "fix-nugget-cogito", title: "Cogito"}`.

### Question overview rows carry their section's referenced nuggets
- **Given:** the same fixture essay/section as above, with at least one flashcard in that section.
- **When:** `GET /api/essaycards/essays/{essay_id}/questions` is called.
- **Then:** every row belonging to that section carries `section_nuggets` including `{nugget_key: "fix-nugget-cogito", title: "Cogito"}`.

### Question overview rows carry each card's current nugget_id
- **Given:** one fixture flashcard linked to `fix-nugget-cogito` and one fixture flashcard with no nugget assignment, both in the same fixture essay.
- **When:** `GET /api/essaycards/essays/{essay_id}/questions` is called.
- **Then:** the linked card's row has `nugget_id` equal to `fix-nugget-cogito`'s id; the unlinked card's row has `nugget_id: null` (11_design_review.md Hard Rule Violation 2 / Minimal Change Set item 3).

### Section export includes the main spine and focus-section nugget context
- **Given:** a fixture essay with a non-empty `main_spine_markdown` and a focus section referencing `fix-nugget-cogito`.
- **When:** `GET /api/essaycards/essays/{essay_id}/sections/{section_id}/export` is called for the focus section.
- **Then:** the response's top level carries `main_spine_markdown` matching the essay's current value and `focus_section_nuggets` including `{nugget_key: "fix-nugget-cogito", title: "Cogito", body_markdown: <fix-nugget-cogito's current body>}`.

### Essay detail's main_spine_nuggets resolves a main-spine-only reference
- **Given:** a fixture essay whose `main_spine_markdown` references a fixture nugget (e.g. `fix-nugget-adequacy`) that is NOT referenced by any of that essay's fixture sections.
- **When:** `GET /api/essaycards/essays/{essay_id}` is called.
- **Then:** the response's top-level `main_spine_nuggets` includes `{nugget_key: "fix-nugget-adequacy", title: <its title>}`, even though no entry in `sections[].nuggets` contains it — demonstrating that a main-spine-only reference resolves to a title (11_design_review.md Hard Rule Violation 1 / Minimal Change Set item 2).

### Essay export and section export carry main_spine_nuggets
- **Given:** the same fixture essay as above.
- **When:** `GET /api/essaycards/essays/{essay_id}/export` and `GET /api/essaycards/essays/{essay_id}/sections/{section_id}/export` are each called.
- **Then:** both responses' top-level `main_spine_nuggets` include `{nugget_key: "fix-nugget-adequacy", title: <its title>}`.

### Due rows carry nugget_id
- **Given:** one due fixture flashcard with `nugget_id` set and one due fixture flashcard with `nugget_id` null.
- **When:** `GET /api/essaycards/flashcards/due` is called.
- **Then:** the linked card's row has `nugget_id` equal to the fixture nugget's id; the legacy card's row has `nugget_id: null`.

### Flashcard upsert with nugget_id omitted leaves an existing assignment untouched
- **Given:** an existing fixture flashcard already linked to `fix-nugget-cogito`.
- **When:** `POST /api/essaycards/flashcards/upsert` is called for that card with a body whose `card` object has no `nugget_id` key at all (only `id`, `level`, `q`, `a`).
- **Then:** the response is `200`; the card's `nugget_id` is still `fix-nugget-cogito`'s id.

### Flashcard upsert with nugget_id explicit null clears an existing assignment
- **Given:** the same linked fixture flashcard.
- **When:** `POST /api/essaycards/flashcards/upsert` is called with `card.nugget_id: null`.
- **Then:** the response is `200`; the card's `nugget_id` is now `null`.

### Flashcard upsert with a valid nugget_id sets the assignment
- **Given:** a fixture flashcard with `nugget_id` currently null and an existing fixture nugget `fix-nugget-wax`.
- **When:** `POST /api/essaycards/flashcards/upsert` is called with `card.nugget_id` set to `fix-nugget-wax`'s id.
- **Then:** the response is `200`; the card's `nugget_id` equals `fix-nugget-wax`'s id.

### Flashcard upsert with an unresolvable nugget_id is rejected without side effects
- **Given:** a fixture flashcard whose current `nugget_id` is `fix-nugget-cogito`'s id.
- **When:** `POST /api/essaycards/flashcards/upsert` is called with `card.nugget_id` set to a well-formed but non-existent uuid.
- **Then:** the response is a `400` `ApiError` with `error.code` `VALIDATION_ERROR`; the card's `nugget_id` is still `fix-nugget-cogito`'s id (unchanged).

### Single-question export includes nugget_id
- **Given:** the fixture flashcard linked to `fix-nugget-cogito`.
- **When:** `GET /api/essaycards/flashcards/{flashcard_id}/export` is called for that card.
- **Then:** the response's `card` object includes `nugget_id` equal to `fix-nugget-cogito`'s id.

### Exploration package for a nugget-linked card uses nugget context
- **Given:** the fixture flashcard linked to `fix-nugget-cogito`.
- **When:** `GET /api/essaycards/flashcards/{flashcard_id}/exploration-package` is called for that card.
- **Then:** the response's `context` is `{nugget_body_markdown: <fix-nugget-cogito's current body>, nugget_key: "fix-nugget-cogito", nugget_title: "Cogito"}` and does NOT contain a `section_body_markdown` key.

### Exploration package for a legacy card is unchanged
- **Given:** a fixture flashcard whose `nugget_id` is null.
- **When:** `GET /api/essaycards/flashcards/{flashcard_id}/exploration-package` is called for that card.
- **Then:** the response's `context` is `{section_body_markdown: <the card's section body>}`, exactly as before this sprint.

### Examination package includes nugget_versions per section
- **Given:** a fixture section referencing `fix-nugget-cogito`.
- **When:** `GET /api/essaycards/essays/{essay_id}/examination-package` is called.
- **Then:** that section's entry carries `nugget_versions: {"fix-nugget-cogito": <fix-nugget-cogito's current updated_at, ISO-8601>}`.

### Examination import stores nugget_versions verbatim
- **Given:** a valid `POST /api/essaycards/examinations/import` result entry whose `nugget_versions` is `{"fix-nugget-cogito": "2026-01-01T00:00:00Z"}` (an arbitrary, not-recomputed value).
- **When:** the import is submitted.
- **Then:** the inserted `section_examinations` row's `nugget_versions_at` equals exactly `{"fix-nugget-cogito": "2026-01-01T00:00:00Z"}` — not the nugget's actual current `updated_at`.

### Examination import without nugget_versions stores null
- **Given:** a valid import result entry with no `nugget_versions` key at all.
- **When:** the import is submitted.
- **Then:** the inserted row's `nugget_versions_at` is `null`.

### nugget_freshness_flags with no recorded versions skips the check
- **Given:** `recorded = None` and any non-empty `current` mapping.
- **When:** `nugget_freshness_flags(recorded, current)` is called directly.
- **Then:** the return value is `[]`.

### nugget_freshness_flags flags changed and missing keys, not matching ones
- **Given:** `recorded = {"a": "t1", "b": "t2"}` and `current = {"a": "t1", "b": "t2-changed", "c": "t3"}`.
- **When:** `nugget_freshness_flags(recorded, current)` is called directly.
- **Then:** the return value contains exactly `"b"` and `"c"` (changed and missing-from-recorded), and does NOT contain `"a"` (matching).

### [UI] Clicking a nugget reference opens the nugget without leaving the reader
- **Given:** the reader open on a fixture essay whose section body renders a resolved `[[nugget:fix-nugget-cogito]]` reference as a clickable "Cogito" link, with the reader scrolled partway down the section.
- **When:** the user clicks "Cogito".
- **Then:** an overlay/panel opens showing the nugget's title and body — the underlying reader page does not navigate away or reload, and closing the overlay returns the reader at the same scroll position it was at before the click.

### [UI — manual] Flashcard review source navigation opens the nugget without ending the session
- **Given:** an active review session on a due card whose `nugget_id` is set, with the answer revealed.
- **When:** the user clicks the "Flashcard → Nugget" control.
- **Then:** the nugget's content opens in an overlay/panel; the review session underneath is still active and unchanged (same card, same flip state) once the overlay is closed. (Verified manually this sprint — no automated UI test harness change beyond the existing Sprint03_Images precedent is introduced for this scenario.)

### [UI — manual] Editing a question can assign or unlink its nugget
- **Given:** the question overview open on a fixture card currently unlinked from any nugget.
- **When:** the user opens Edit, selects a nugget from the new nugget dropdown, and saves; then reopens Edit, selects "No nugget", and saves again.
- **Then:** after the first save the card's nugget assignment is set to the chosen nugget (visible on reload); after the second save the assignment is cleared back to no nugget — demonstrating that Save always sends `card.nugget_id` explicitly (an id, then `null`), never omitted (11_design_review.md Hard Rule Violation 2 / Minimal Change Set item 3). (Verified manually this sprint — no automated UI test harness change beyond the existing Sprint03_Images precedent is introduced for this scenario.)
