-- Sprint13_ReviewStatsSentenceFeedback — schema changes. This file is a
-- design copy; the implementer folds it into the canonical runtime schema at
-- 03_Application/EssayCards/schema.sql (loaded idempotently at startup by
-- backend/database.py::init_schema() and by tests/conftest.py), appended
-- after the existing "Sprint12_FSRSAndUXOverhaul" block — see
-- 10_scaffolding.json. Follows the same idempotent idiom already used
-- throughout schema.sql (`create table if not exists` / guarded `do $$ ... $$`
-- constraint blocks).
--
-- Scope: exactly one new table, essaycards.sentence_feedback (Sprint13 §4 —
-- essay-reader sentence-level "difficult" / "thumbs up" marks). Nothing else
-- in this sprint touches the schema — the Review-page and Stats-page changes
-- (Sprint13 §§1-3, 5-8) are all computed live from essaycards.review_events /
-- essaycards.flashcard_review_state, both pre-existing and unchanged.

begin;

-- ── essaycards.sentence_feedback (Sprint13 §4) ──────────────────────────────
--
-- One row per (section_id, sentence_index) that currently carries at least
-- one of the two independent flags. A sentence with NEITHER flag set has NO
-- row — "neither state" is represented by absence, not by an all-false row
-- (ck_sentence_feedback_any_flag enforces this at the database level; the
-- application upserts on a flag going true and DELETEs the row outright when
-- toggling a flag off leaves both false — see 10_architecture.json
-- §internal_flow step 7).
--
-- Addressing: a sentence is identified by its 0-based ordinal position
-- (sentence_index) within the ordered sentence list that
-- backend/sentences.py::split_sentences(body_markdown) produces for that
-- section's CURRENT body_markdown — NOT a user-selected character range (see
-- CLAUDE.md "Essay reader sentence feedback" / StoryReader's annotations
-- table, which addresses an arbitrary (paragraph_index, char_start, char_end)
-- span instead; EssayCards does not need that generality because the
-- addressable unit here is always exactly one algorithm-computed sentence).
--
-- sentence_text is the exact sentence substring at write time, server-
-- validated to match split_sentences(section.body_markdown)[sentence_index]
-- on every PATCH (mirrors StoryReader's selected_text equality check). It is
-- NOT re-validated against the section's current content on read — see the
-- KNOWN GAP note below.
--
-- KNOWN GAP — documented, not guarded (same house style as the nugget
-- ownership/cascade gap and the non-atomic flashcard-generation gap in
-- CLAUDE.md "Known gaps"): essaycards.essay_sections.body_markdown is
-- mutable (re-ingested via POST /essays/ingest or the markdown CLI, with no
-- versioning concept, unlike StoryReader's immutable story_versions). If a
-- section's body_markdown is edited after sentence feedback was recorded
-- against it, sentence_index positions can shift. A row whose sentence_index
-- is now OUT OF RANGE is naturally invisible (the reader only ever looks up
-- feedback for sentence_index values the live split_sentences(...) call
-- actually produced) — but a row whose sentence_index still falls in range
-- can become silently MISATTACHED to a different sentence than the one it
-- was recorded against. No re-ingest-time migration, re-indexing, or
-- deletion of stale sentence_feedback rows is added this sprint (consistent
-- with the app's general no-delete-on-re-ingest policy — see CLAUDE.md
-- "Content ingestion").
create table if not exists essaycards.sentence_feedback (
    id             uuid        primary key default gen_random_uuid(),
    section_id     uuid        not null references essaycards.essay_sections(id) on delete cascade,
    sentence_index integer     not null check (sentence_index >= 0),
    sentence_text  text        not null check (sentence_text <> ''),
    is_difficult   boolean     not null default false,
    is_thumbs_up   boolean     not null default false,
    created_at     timestamptz not null default now(),
    updated_at     timestamptz not null default now(),
    constraint uq_sentence_feedback_section_sentence unique (section_id, sentence_index),
    constraint ck_sentence_feedback_any_flag check (is_difficult or is_thumbs_up)
);

-- Serves both GET /essays/{essay_id}/sentence-feedback's per-section grouping
-- and the PATCH endpoint's (section_id, sentence_index) upsert/delete lookup
-- — the unique constraint above already provides this leading-column index
-- (same reasoning as storyreader.annotations' uq_annotations_exact_span), so
-- no separate index is added here.

commit;
