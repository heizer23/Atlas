-- Sprint10_DualSchedulerAB — additive schema changes only. No existing table
-- is recreated; flashcard identity, review state (next_due_at/review_interval
-- /last_reviewed_at), discussion/revision history, and examination history
-- are never reset or deleted by anything in this file. Follows the existing
-- `create table if not exists` / `alter table ... add column if not exists` /
-- guarded-constraint / guarded-backfill idiom already used throughout
-- 03_Application/EssayCards/schema.sql (see Sprint09_Nuggets/10_schema.sql
-- for the most recent precedent).
--
-- This file is a design copy. The implementer folds it into the canonical
-- runtime schema at 03_Application/EssayCards/schema.sql (loaded idempotently
-- at startup by backend/database.py::init_schema() and by tests/conftest.py)
-- — see 10_scaffolding.json.

begin;

-- ── essaycards.flashcard_review_state — scheduler assignment columns ────────
--
-- Assignment is permanent, decided exactly once per card (backend/scheduling.py
-- ::decide_scheduler_assignment), at the existing `if was_inserted:` gate
-- already present at all three flashcard-creation call sites
-- (backend/ingest.py, backend/routers/flashcards.py, backend/exploration.py),
-- or by the one-time migration backfill below for cards that already existed
-- before this sprint. No endpoint accepts a scheduler field in any request
-- body — this is exclusively a server-side side effect.
alter table essaycards.flashcard_review_state
    add column if not exists scheduler text not null default 'classic';

do $$ begin
    if not exists (select 1 from pg_constraint where conname = 'ck_review_state_scheduler') then
        alter table essaycards.flashcard_review_state
            add constraint ck_review_state_scheduler check (scheduler in ('classic', 'fsrs'));
    end if;
end $$;

-- Null only transiently, for a pre-sprint row between the ADD COLUMN above and
-- the guarded backfill below running later in this same transaction. Every
-- row that has ever been read by the application has a non-null value here.
alter table essaycards.flashcard_review_state
    add column if not exists scheduler_assigned_at timestamptz;

-- Closed, fixed vocabulary (R-CON-AL-01/03) — exactly these four values:
--   new_card_random               — a genuinely new card, kill switch enabled
--   migrated_never_reviewed_random — a pre-existing but never-reviewed card,
--                                    assigned at the one-time migration below
--                                    via the same balanced mechanism as a new card
--   legacy_retained_classic        — a pre-existing card with real review
--                                    history; py-fsrs has no way to reliably
--                                    initialize FSRS state without a full
--                                    per-review rating history, which this app
--                                    has never persisted, so every such card
--                                    stays on Classic (mission §4 fallback)
--   assignment_disabled_classic    — the kill switch was disabled at creation time
alter table essaycards.flashcard_review_state
    add column if not exists scheduler_assignment_reason text;

do $$ begin
    if not exists (select 1 from pg_constraint where conname = 'ck_review_state_assignment_reason') then
        alter table essaycards.flashcard_review_state
            add constraint ck_review_state_assignment_reason check (
                scheduler_assignment_reason is null or scheduler_assignment_reason in (
                    'new_card_random', 'migrated_never_reviewed_random',
                    'legacy_retained_classic', 'assignment_disabled_classic'
                )
            );
    end if;
end $$;

-- Coarse cohort/version tag identifying when and under which experiment
-- iteration a card was assigned (mission §4). A single literal this sprint;
-- a later sprint that changes assignment mechanics would introduce a new
-- value, never rewrite this one for already-assigned cards.
-- Canonical definition: backend.scheduling.EXPERIMENT_VERSION ('sprint10_v1')
-- — this DEFAULT and both migration UPDATEs below must stay in sync with it;
-- a future version bump should update all three occurrences together.
alter table essaycards.flashcard_review_state
    add column if not exists experiment_version text not null default 'sprint10_v1';

-- Supports the experiment dashboard's GROUP BY scheduler aggregates and any
-- future per-scheduler filtering of the due queue.
create index if not exists ix_review_state_scheduler
    on essaycards.flashcard_review_state(scheduler);

-- ── essaycards.fsrs_card_state ───────────────────────────────────────────────
--
-- FSRS's own per-card memory state — a SEPARATE concept from
-- flashcard_review_state.review_interval (EssayCards' own materialised
-- interval cache). Only rows for scheduler='fsrs' cards exist here; absence
-- of a row is never used as the signal for "this card is classic" — the
-- scheduler column on flashcard_review_state is the single source of truth
-- for that, kept explicit rather than inferred from presence/absence here.
--
-- raw_state (the library's own Card.to_dict() output) is the SOLE source of
-- truth for reconstructing a live fsrs.Card on the next review
-- (Card.from_dict(raw_state)). The discrete columns below exist only for
-- dashboard queryability/audit and must always be written from the exact
-- same to_dict() call that produced raw_state — never derived independently.
--
-- fsrs_state uses the library's own IntEnum values (1=Learning, 2=Review,
-- 3=Relearning — confirmed against py-fsrs 6.3.2's State enum; there is no
-- separate "new" library state, a brand-new card simply starts in Learning).
-- Named fsrs_state, not state, to avoid any confusion with EssayCards' own
-- new/learning/established classification (CLAUDE.md glossary), which
-- remains governed exclusively by flashcard_review_state.review_interval and
-- is never replaced or shadowed by this column (mission §3 "do not replace
-- the 24-hour threshold with FSRS-native learning states").
create table if not exists essaycards.fsrs_card_state (
    flashcard_id    uuid             primary key references essaycards.flashcards(id) on delete cascade,
    stability       double precision not null,
    difficulty      double precision not null,
    fsrs_state      smallint         not null,
    step            integer,                      -- null once the card has graduated out of Learning/Relearning
    last_review_at  timestamptz      not null,
    raw_state       jsonb            not null,     -- authoritative: fsrs.Card.to_dict()
    updated_at      timestamptz      not null default now(),
    constraint ck_fsrs_card_state_fsrs_state check (fsrs_state in (1, 2, 3))
);

-- ── essaycards.review_events ─────────────────────────────────────────────────
--
-- Append-only, new durable state (R-CON-BP-03): owned entirely by
-- POST /flashcards/{id}/review, one row inserted per review, for BOTH
-- schedulers (not fsrs-only) — this is what backs the experiment dashboard,
-- since flashcard_review_state only ever holds the latest snapshot and
-- EssayCards has no other per-review history table. Never backfilled: no
-- historical per-review data exists anywhere in the schema to backfill from
-- (confirmed absent by investigation), so this table only ever reflects
-- reviews that happened from this sprint's activation forward.
--
-- was_due records whether the due-queue's own base eligibility condition
-- (the card's next_due_at BEFORE this review <= the review's timestamp)
-- held for this review — an audit/diagnostic fact only. It does NOT by
-- itself distinguish an ordinary due-queue review from an immediate
-- relearning re-review: GET /flashcards/due's base eligibility already
-- requires next_due_at <= now() for every session type, so was_due is true
-- for virtually every review the application can produce, rapid retries
-- included (11_design_review.md Major finding #1). The dashboard's
-- recall-rate sample (mission §7: do not count multiple rapid retries as
-- independent evidence of long-term retention) is instead restricted to
-- rows where prior_review_interval >= interval '24 hours' — i.e. the card
-- had already graduated to established BEFORE this review, mirroring the
-- app's existing learning/established threshold (CLAUDE.md). A rapid retry
-- always follows a short (learning-phase) prior_review_interval and is
-- excluded by that filter regardless of was_due.
create table if not exists essaycards.review_events (
    id                        uuid        primary key default gen_random_uuid(),
    flashcard_id              uuid        not null references essaycards.flashcards(id) on delete cascade,
    scheduler                 text        not null,
    grade                     text        not null,
    reviewed_at               timestamptz not null,
    was_due                   boolean     not null,
    prior_review_interval     interval    not null,  -- review_interval value immediately before this review
    resulting_review_interval interval    not null,  -- review_interval value this review produced
    constraint ck_review_events_scheduler check (scheduler in ('classic', 'fsrs')),
    constraint ck_review_events_grade check (grade in ('again', 'hard', 'good', 'easy'))
);

create index if not exists ix_review_events_flashcard
    on essaycards.review_events(flashcard_id, reviewed_at desc);

-- Supports the experiment dashboard's GROUP BY scheduler ... FILTER (WHERE was_due) aggregates.
create index if not exists ix_review_events_scheduler_was_due
    on essaycards.review_events(scheduler, was_due);

-- ── One-time migration backfill for cards that existed before this sprint ───
--
-- Both UPDATEs are guarded on scheduler_assigned_at IS NULL, so a rerun of
-- this file (schema.sql runs idempotently on every startup) touches zero rows
-- the second time — the same sentinel-guarded-backfill idiom already used for
-- flashcard_review_state.review_interval's own historical backfill above in
-- schema.sql. Neither UPDATE's SET list includes next_due_at, review_interval,
-- or last_reviewed_at — a pre-existing card's schedule is never altered by
-- this migration (mission §5 "preserve existing next due dates during
-- migration").
--
-- 1. Cards already reviewed under Classic pre-sprint (real review history
--    exists) -> forced to classic, permanently. py-fsrs's only history-based
--    initialization path (Scheduler.reschedule_card) requires a complete
--    ordered per-review rating history, which this schema has never
--    persisted (only the latest-state snapshot survives) — so reliable FSRS
--    initialization is impossible for any such card, and the mission's
--    documented fallback ("retain it in Classic") applies uniformly, not to
--    a subset.
-- 'sprint10_v1' here mirrors backend.scheduling.EXPERIMENT_VERSION (canonical source).
update essaycards.flashcard_review_state
   set scheduler = 'classic',
       scheduler_assigned_at = now(),
       scheduler_assignment_reason = 'legacy_retained_classic',
       experiment_version = 'sprint10_v1'
 where scheduler_assigned_at is null
   and last_reviewed_at is not null;

-- 2. Cards that existed before this sprint but were never reviewed -> eligible
--    for the identical balanced random assignment as a brand-new card, because
--    a fresh fsrs.Card() IS the correct FSRS initialization for a
--    never-reviewed card (zero replay needed — it is exactly the state a
--    genuinely new FSRS-cohort card would start from). Uses Postgres-native
--    hashtext() rather than the Python sha256-based helper used for
--    in-application new-card assignment — a deliberate, safe divergence: this
--    cohort (existing never-reviewed rows, assigned once at migration time)
--    and the application's new-card cohort (assigned at INSERT time, from
--    this sprint forward) are disjoint and never need cross-language hash
--    parity with each other.
-- 'sprint10_v1' here mirrors backend.scheduling.EXPERIMENT_VERSION (canonical source).
update essaycards.flashcard_review_state
   set scheduler = case when hashtext(flashcard_id::text) % 2 = 0 then 'classic' else 'fsrs' end,
       scheduler_assigned_at = now(),
       scheduler_assignment_reason = 'migrated_never_reviewed_random',
       experiment_version = 'sprint10_v1'
 where scheduler_assigned_at is null
   and last_reviewed_at is null;

commit;
