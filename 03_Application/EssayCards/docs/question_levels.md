# EssayCards — Question levels and overview

Split out of `CLAUDE.md` (reference detail; load when working on this area).

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
