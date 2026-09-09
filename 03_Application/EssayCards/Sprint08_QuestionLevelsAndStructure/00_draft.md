# Sprint08 — Question levels and a per-essay question overview

## Scope

Decouple question/card maintenance from the essay import/export flow, add an
integer `level` per card, and add an editorial overview screen showing an
essay's question structure by section and level. Restrict essay-level
export/import to a single essay (it already is, per essay; see below). Oral
exams and card-to-multiple-essay relationships are explicitly out of scope.

## 1. Question levels

Each flashcard gets an integer `level` column (not an enum/string). Current
semantic convention, described in the UI but not enforced beyond `>= 1`:

- `1` = foundational / spine
- `2` = building / explanatory structure
- `3` = decorating / examples, terminology, anecdotes, supporting detail

Not upper-bounded — a finer scale can be introduced later without a schema
change. No question `sort_index` in this sprint.

## 2. Card/section decoupling — already structurally true

Inspected `schema.sql`: `essaycards.flashcards` is already its own table with
a stable `id` and a `section_id` foreign key — cards are NOT embedded in
`essay_sections.body_markdown` or any section JSON blob. The coupling problem
is entirely at the API layer: today the only way to add/edit a card is
through the essay-shaped JSON ingest endpoint (`POST /essays/ingest`) or this
session's earlier "Export section" mechanism, both of which require resending
section/essay-level fields. No schema redesign is needed for decoupling — new
narrow, card-only endpoints are.

## 3. Question overview screen

New screen for one essay: sections in essay order, each section's questions
grouped by level ascending. Purpose is editorial/narrative, not review.
Reuses the existing Dataset + client-side-grouping pattern already used by
`EssayListView` (categories) rather than inventing a nested JSON shape.

## 4/5. Single-question actions + AI export/import

New narrow endpoints, reusing the existing card row (never touching
`essay_sections`/`essays`):

- `GET /flashcards/{flashcard_id}/export` — bespoke JSON (R-CON-BP-04
  exemption, same rationale as `examination-package`/section `export`):
  essay slug/title, section id/anchor/heading/body (READ-ONLY CONTEXT), and
  `card: {id, level, q, a}`.
- `POST /flashcards/upsert` — `{essay_slug, section_id, card: {id?, level, q,
  a}}`. Resolves essay by slug, requires `section_id` to belong to it, then
  upserts by `(essay_id, card_key)`: `card.id` matching an existing card
  updates it in place; `card.id` present but new, or omitted, creates a card
  (omitted -> auto-generated id, for the overview's "Add question" form).
  Rejects moving an existing card to a different section (mirrors
  `essays.py::_check_card_section_collisions`). The payload has no field for
  section prose/heading/order — structurally incapable of touching essay
  content, so pasting the unedited export context back is always safe.

Overview actions (inspect/edit/add/export/import) all go through these two
endpoints plus the existing per-question data already loaded.

## 6. Single-essay export

New `GET /essays/{essay_id}/export` (sibling to the existing per-section
export), returning the same ingest-shaped payload (all current
sections+cards, in order) for the WHOLE essay, reimported through the
existing `POST /essays/ingest` + "Add / Update Essay". There was no bulk
multi-essay export/import to restrict — ingest has always taken exactly one
essay (one slug) per call; this fills the missing "export an existing whole
essay's current content" capability, which is single-essay by construction
like everything else here.

## 7. Migration

`alter table essaycards.flashcards add column if not exists level integer not
null default 2` + a guarded `ck_flashcards_level check (level >= 1)`,
following the exact idempotent pattern already used for
`essays.category/sort_index/status` and `flashcard_review_state.review_interval`
in `schema.sql`. Default `2` ("building/explanatory") for every pre-existing
card — a neutral guess absent any signal for which cards are foundational vs.
decorative. No IDs change, no data is deleted, `flashcard_review_state` is
untouched.

## 8. Non-goals (explicit)

Oral exams (any mode), level-based review scheduling/prioritization, general
card-to-multiple-essay/many-to-many linking, card `sort_index`, review-system
redesign, rewriting essay prose, AI-assigned levels.

## Note

Implemented directly from this draft at the user's explicit request (see
chat); the full `R-PRO-BP-01` design→review→test agent pipeline was not run
for this change, matching the precedent set by `Sprint05_ReviewQueueOrdering`.
