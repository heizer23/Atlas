# EssayCards — Single-section export / insert

Split out of `CLAUDE.md` (reference detail; load when working on this area).

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

## Improve section (Sprint15)
Third reader action, alongside Export / Insert: **Improve section** revises a section using
its oral-exam history. It calls the same section export with `?include_examinations=true`.
- `include_examinations` is an optional bool, default `false`; with the default the package
  is byte-identical to the plain export. `POST /essays/ingest` ignores the field.
- When true the package adds `focus_section_examinations`: every `exam_type='guided'` row of
  the focus section, ordered `examined_at` ascending, each
  `{examined_at, score, passed, question, answer_transcript, feedback}` verbatim; `[]` if none.
  Unguided exams are never included. Read-only.
- The button copies `SECTION_IMPROVE_PROMPT_INTRO` (`src/ShellEntry.tsx`) + the package, then
  becomes **Import improved section →** (navigates to `IngestView`). Same nugget-drop-detection
  sessionStorage stash as Export section. The reply is an ordinary ingest payload (edit in place
  by card id; the examinations field is omitted) — no new import path.
- Invalid `include_examinations` values return a 422 `VALIDATION_ERROR` ApiError; a malformed
  essay/section id returns 404 `NOT_FOUND` (app-level check in `backend/main.py`).
