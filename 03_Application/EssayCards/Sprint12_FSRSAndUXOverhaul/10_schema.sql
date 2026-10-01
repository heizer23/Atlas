-- Sprint12_FSRSAndUXOverhaul — schema changes. This file is a design copy;
-- the implementer folds it into the canonical runtime schema at
-- 03_Application/EssayCards/schema.sql (loaded idempotently at startup by
-- backend/database.py::init_schema() and by tests/conftest.py) — see
-- 10_scaffolding.json. Follows the same idempotent idiom already used
-- throughout schema.sql (`create table if not exists` / `add column if not
-- exists` / guarded `do $$ ... $$` constraint blocks / guarded backfills).
--
-- Scope: (1) back up Sprint10's scheduler-assignment data before destroying
-- it, (2) drop every Sprint10-only scheduler column (flashcard_review_state's
-- four + review_events.scheduler — their CHECK constraints and any index
-- referencing only these columns are dropped automatically by Postgres along
-- with the column, per "ALTER TABLE ... DROP COLUMN ... automatically drops
-- all constraints and indexes involving the column"), and (3) add
-- section_examinations.exam_type for the new guided/unguided oral-exam
-- split. The legacy FSRS-state NUMERIC synthesis itself (stability/
-- difficulty/fsrs_state/step for a reviewed card with no native FSRS state)
-- is deliberately NOT done here in SQL — it is implemented in Python
-- (backend/migrate_fsrs_state.py + backend/scheduling.py::
-- estimate_initial_fsrs_state), run once at every startup immediately after
-- this file, so it can reuse the exact same fsrs library code/constants the
-- live scheduler uses with zero risk of a hand-duplicated SQL formula
-- drifting from it. See 10_architecture.json §contracts.invariants.

begin;

-- ── Back up Sprint10's scheduler-assignment data BEFORE dropping it ────────
--
-- New durable state (R-CON-BP-03): an audit snapshot, not a live table any
-- code path reads from. Owned by this sprint; retained indefinitely (no
-- pruning policy this sprint — see 10_architecture.json §deferred_decisions).
-- Guarded by an information_schema existence check rather than a sentinel
-- column, because the sentinel this migration would naturally use
-- (flashcard_review_state.scheduler_assigned_at) is itself being dropped
-- below in this same transaction — the table's own existence is the guard,
-- so a rerun after the first successful run is a no-op.
do $$ begin
    if not exists (
        select 1 from information_schema.tables
        where table_schema = 'essaycards' and table_name = 'pre_fsrs_migration_backup_sprint12'
    ) then
        create table essaycards.pre_fsrs_migration_backup_sprint12 as
        select
            flashcard_id,
            scheduler,
            scheduler_assigned_at,
            scheduler_assignment_reason,
            experiment_version,
            last_reviewed_at,
            next_due_at,
            review_interval,
            now() as backed_up_at
        from essaycards.flashcard_review_state;
    end if;
end $$;

-- ── Drop Sprint10's scheduler-assignment columns ────────────────────────────
--
-- Every card is FSRS-only from this sprint forward — scheduler assignment is
-- no longer a live decision anywhere in the app (00_draft.md §1 "Remove
-- experimental assignment, scheduler badges, and comparison statistics").
-- Dropping these columns automatically drops ck_review_state_scheduler,
-- ck_review_state_assignment_reason, and ix_review_state_scheduler — no
-- separate DROP CONSTRAINT / DROP INDEX statement is needed or correct to
-- add here.
alter table essaycards.flashcard_review_state drop column if exists scheduler;
alter table essaycards.flashcard_review_state drop column if exists scheduler_assigned_at;
alter table essaycards.flashcard_review_state drop column if exists scheduler_assignment_reason;
alter table essaycards.flashcard_review_state drop column if exists experiment_version;

-- Dropping this column automatically drops ck_review_events_scheduler and
-- ix_review_events_scheduler_prior_interval (a multi-column index referencing
-- this column is dropped along with it, same as a single-column index).
-- review_events itself survives unchanged otherwise — it remains the
-- general-purpose, scheduler-agnostic append-only review-history log that
-- backend/routers/review_stats.py already reads from.
alter table essaycards.review_events drop column if exists scheduler;

-- ── essaycards.section_examinations.exam_type (Sprint12) ───────────────────
--
-- Distinguishes a calibration-aware "guided" oral exam (the only mode that
-- existed before this sprint — EXAM_PROMPT_INTRO's use of a section's
-- last_examination to tune starting difficulty) from a new, genuinely cold
-- "unguided" mode that passes no prior history/calibration context to the
-- examiner. Required, never silently defaulted by the application going
-- forward (POST /examinations/import's validate_import_body rejects a
-- missing exam_type — same discipline as flashcards.level) — the column
-- DEFAULT below exists only to backfill every pre-Sprint12 row, which was
-- always examined under the one pre-existing calibration-aware flow and is
-- therefore correctly classified 'guided' in retrospect.
alter table essaycards.section_examinations
    add column if not exists exam_type text not null default 'guided';

do $$ begin
    if not exists (select 1 from pg_constraint where conname = 'ck_section_examinations_exam_type') then
        alter table essaycards.section_examinations
            add constraint ck_section_examinations_exam_type check (exam_type in ('guided', 'unguided'));
    end if;
end $$;

-- Supports the per-(section, exam_type) "latest examination" lookup that
-- backend/routers/essays.py's learning-progress query and
-- backend/examinations.py::build_export_package both need (DISTINCT ON
-- (section_id) ... WHERE exam_type = ... ORDER BY examined_at DESC).
create index if not exists ix_section_examinations_section_type_examined
    on essaycards.section_examinations(section_id, exam_type, examined_at desc);

commit;

-- ── Not performed in this file (see module comment above) ──────────────────
--
-- The legacy FSRS-state backfill (essaycards.fsrs_card_state rows for every
-- flashcard_review_state row with last_reviewed_at IS NOT NULL and no native
-- FSRS state yet) is implemented in Python:
--   backend/scheduling.py::estimate_initial_fsrs_state(review_interval,
--     last_reviewed_at, desired_retention) — pure, unit-testable synthesis.
--   backend/migrate_fsrs_state.py::migrate_legacy_fsrs_state(conn) — the
--     one-time, idempotent driver (guarded by "no existing fsrs_card_state
--     row for this flashcard_id"), invoked once at every startup from
--     backend/main.py immediately after init_schema() (this file) completes.
-- Neither ever writes next_due_at, review_interval, or last_reviewed_at for
-- an existing card — those three columns are read-only inputs to the
-- synthesis, never its targets (10_architecture.json §contracts.invariants
-- "DUE DATES PRESERVED").
