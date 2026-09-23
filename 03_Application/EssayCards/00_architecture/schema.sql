-- Sprint09_Nuggets — additive schema changes only. No existing table is
-- recreated; no flashcard identity, review state, discussion/revision
-- history, or examination history is reset or deleted. Follows the existing
-- `create table if not exists` / `alter table ... add column if not exists` /
-- guarded-constraint idiom already used in 03_Application/EssayCards/schema.sql.
--
-- This file is a design copy. The implementer folds it into the canonical
-- runtime schema at 03_Application/EssayCards/schema.sql (loaded idempotently
-- at startup and by tests/conftest.py) — see 10_scaffolding.json.

begin;

-- ── essaycards.nuggets ───────────────────────────────────────────────────────
--
-- A standalone, independently-learnable concept — NOT owned by one essay or
-- section (see CLAUDE.md "Nuggets" / Sprint09_Nuggets/00_draft.md §0). The
-- same nugget can be referenced by multiple sections/essays without
-- duplicating its content, its flashcards, or their review state.
--
-- nugget_key is the stable, author-assigned identity — same convention as
-- essays.slug / essay_sections.anchor_slug / flashcards.card_key: validated
-- against SLUG_LIKE_RE (backend/ingest.py, promoted from the essays.py-local
-- copy this sprint), no auto-slugify, no auto-lowercasing, GLOBALLY unique
-- (no per-essay scoping). Create/update is upsert-by-key
-- (`on conflict (nugget_key) do update set title = ..., body_markdown = ...`)
-- — the key is always the WHERE, never a SET column, so a title edit can
-- never change the key. No key-rename support this sprint.
create table if not exists essaycards.nuggets (
    id            uuid        primary key default gen_random_uuid(),
    nugget_key    text        not null,
    title         text        not null,
    body_markdown text        not null default '',
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now(),
    constraint uq_nuggets_nugget_key unique (nugget_key)
);

-- GET /nuggets orders by title/nugget_key (see backend/routers/nuggets.py);
-- created_at is indexed for a possible future recency view, mirroring the
-- precedent set by ix_essays_category_sort / ix_images_created_at.
create index if not exists ix_nuggets_created_at on essaycards.nuggets(created_at);

-- ── essaycards.section_nuggets ───────────────────────────────────────────────
--
-- Many-to-many association between a section and the nuggets its
-- body_markdown currently references via `[[nugget:key]]`. DERIVED, NOT
-- AUTHOR-MAINTAINED: a section's Markdown is the sole source of truth. Rows
-- are fully resynced (insert missing, delete stale) on every section upsert
-- by backend/ingest.py::upsert_document — see Sprint09_Nuggets/00_draft.md §2.
--
-- This resync is an explicit, documented exception to the app's general
-- no-delete-on-re-ingest policy (see CLAUDE.md "Content ingestion"): it only
-- ever removes an ASSOCIATION row here, never a nuggets row or a flashcards
-- row.
create table if not exists essaycards.section_nuggets (
    section_id uuid not null references essaycards.essay_sections(id) on delete cascade,
    nugget_id  uuid not null references essaycards.nuggets(id) on delete cascade,
    primary key (section_id, nugget_id)
);

-- Supports GET /nuggets/{id}/sections (the nugget view's "referenced by"
-- list) and the freshness/rendering lookups keyed by nugget_id; lookup by
-- section_id is already covered by the primary key's leading column.
create index if not exists ix_section_nuggets_nugget_id on essaycards.section_nuggets(nugget_id);

-- ── essaycards.flashcards.nugget_id ─────────────────────────────────────────
--
-- Nullable: existing flashcards remain valid with no nugget. Assignment is
-- always explicit, via POST /flashcards/upsert's optional card.nugget_id
-- (backend/routers/flashcards.py) — no ingestion path, and no other endpoint,
-- ever reads or writes it (same "set exclusively by one endpoint" pattern
-- already established for flashcards.level, Sprint08). essay_id/section_id
-- remain required and unchanged this sprint.
--
-- KNOWN GAP — documented, not guarded (Sprint09_Nuggets/00_draft.md §1;
-- Sprint09_Nuggets/10_architecture.json §risks; CLAUDE.md "Known gaps"): a
-- flashcard reachable through a shared nugget from another essay is still
-- only OWNED by its own essay_id/section_id. A cascading delete of that
-- owning section or essay (essay_id/section_id are both `on delete cascade`)
-- would remove the card even though another essay still references it via
-- the nugget. The app has no delete endpoint anywhere today (essays,
-- sections, flashcards, and images are all upsert-only), so this risk has no
-- live trigger through the app; it is latent, not exercised. No app-level
-- guard is added this sprint — an explicit decision, not an oversight.
--
-- `on delete set null` (rather than cascade or restrict) governs only the
-- hypothetical case of a nuggets row itself being removed by direct SQL
-- (the app never deletes a nugget) — a card simply loses its nugget link
-- rather than being deleted.
alter table essaycards.flashcards
    add column if not exists nugget_id uuid references essaycards.nuggets(id) on delete set null;

-- Supports GET /nuggets/{id}/flashcards. Partial: nugget_id is null for the
-- large majority of legacy cards.
create index if not exists ix_flashcards_nugget_id
    on essaycards.flashcards(nugget_id) where nugget_id is not null;

-- ── essaycards.essays.main_spine_markdown ───────────────────────────────────
--
-- The compact, memorizable "main spine" narrative of the essay — the top
-- level of the essay / section / nugget / flashcard hierarchy (see CLAUDE.md
-- "Nuggets"). References nuggets via the same `[[nugget:key]]` syntax as a
-- section's body_markdown (backend/ingest.py::extract_nugget_keys).
--
-- JSON/API-ingest-only this sprint: POST /essays/ingest gains an optional
-- top-level `main_spine_markdown` key (default '' on omission, same
-- optional-key convention as category/sort_index/status). The markdown-CLI
-- front-matter grammar (backend/ingest.py::_parse_front_matter) is UNCHANGED
-- this sprint — an essay ingested via the markdown CLI keeps
-- main_spine_markdown = '' until edited through the JSON path. This is the
-- resolution of the "main-spine authoring on the CLI path" open question
-- referenced in Sprint09_Nuggets/00_draft.md's closing Note: folded into §4's
-- essays.py-only description rather than into the CLI grammar.
alter table essaycards.essays
    add column if not exists main_spine_markdown text not null default '';

-- ── essaycards.section_examinations.nugget_versions_at ──────────────────────
--
-- Nugget-aware examination freshness (Sprint09_Nuggets/00_draft.md §9).
-- NULL means "predates this feature" — an existing row stays fully readable
-- (no backfill, no discard) and the nugget-level freshness check is skipped
-- for it. '{}'::jsonb means "this section referenced zero nuggets at exam
-- time." Populated by backend/examinations.py::build_export_package at
-- export time ({nugget_key: nuggets.updated_at} for the section's
-- then-current references) and echoed back verbatim into this column by
-- backend/examinations.py::import_results — NOT recomputed at import time,
-- the same echo-through-import handling already used for
-- section_version_at. Accepts the same known false-positive-on-byte-
-- identical-re-save limitation the section-level check already has (see the
-- section_version_at comment above) — not solved here, just not made worse.
alter table essaycards.section_examinations
    add column if not exists nugget_versions_at jsonb;

commit;
