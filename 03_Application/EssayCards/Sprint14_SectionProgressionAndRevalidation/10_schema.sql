-- Sprint14_SectionProgressionAndRevalidation — schema changes. Design copy; the
-- implementer folds it into the canonical runtime schema at
-- 03_Application/EssayCards/schema.sql (loaded idempotently at startup by
-- backend/database.py::init_schema() and by tests/conftest.py), after the
-- Sprint13 block. Same idempotent idiom as the rest of schema.sql.
--
-- Scope:
--   1. section_examinations.passed   (pass/fail recorded at write time)
--   2. essay_examinations            (NEW, append-only: full-essay oral attempts)
--   3. section_oral_state            (NEW: current oral pass state per section)
--   4. essay_oral_state              (NEW: current oral pass state per essay)
--   5. flashcard_review_state.needs_revalidation  (NEW column)
--   6. revalidation_events           (NEW, append-only: audit of revalidation checks)
--
-- Everything here is PRIVATE EssayCards state (R-CON-BP-03): not a shared
-- contract, no shared view. Traffic-light colors are NEVER stored — they are
-- derived at query time (backend/progress.py) from these tables plus
-- flashcard_review_state.review_interval.
--
-- The pass THRESHOLD (70% of score_max 6) is NOT encoded in any constraint —
-- it lives only in backend/oral_state.py so it can become configurable later.
-- The one-time backfill (section 1) re-grades historical section_examinations
-- rows under the 70% rule (literal 420, i.e. score >= 5), NOT the Sprint12
-- score >= 3 bar; rows written from this sprint on carry the verdict computed
-- at write time under the threshold in force then. Section 4 grandfathers
-- unlocks separately (guided score >= 3), so a historical guided 3 can show
-- passed = false next to an unlocked section.
--
-- This file carries no begin/commit: it is folded into schema.sql, which
-- already wraps everything in a single transaction.
--
-- LOCK/UNLOCK of flashcards has no column: a card is unlocked iff its
-- section's section_oral_state.guided_passed is true (derived; a card added
-- later to an already-passed section is therefore unlocked automatically).
--
-- TIME AUTHORITY (R-CON-AL-06): *_passed_at = the attempt's examined_at
-- (external/ChatGPT-supplied, offset-required, existing import discipline);
-- unguided_invalidated_at and revalidation_events.checked_at = server now().

-- ── 1. section_examinations.passed ─────────────────────────────────────────
-- Nullable add -> one-time backfill under the 70% rule frozen at migration
-- time (score * 100 >= 70 * 6 = 420, i.e. score >= 5) -> NOT NULL. The
-- literal 420 is a historical migration constant, not the live threshold.
-- Every row written by the app from this sprint on sets passed explicitly
-- (no column default by design: existing fixture/test INSERTs must supply it).
alter table essaycards.section_examinations add column if not exists passed boolean;
update essaycards.section_examinations set passed = (score * 100 >= 420) where passed is null;
alter table essaycards.section_examinations alter column passed set not null;

-- ── 2. essaycards.essay_examinations ───────────────────────────────────────
-- Append-only attempts at a FULL-ESSAY oral (scope='essay'), guided or
-- unguided. The app never updates or deletes a row. Section-scope attempts
-- stay in section_examinations.
create table if not exists essaycards.essay_examinations (
    id                uuid        primary key default gen_random_uuid(),
    essay_id          uuid        not null references essaycards.essays(id) on delete cascade,
    exam_type         text        not null,
    examined_at       timestamptz not null,
    question          text        not null,
    answer_transcript text        not null,
    score             smallint    not null,
    passed            boolean     not null,
    feedback          text,
    created_at        timestamptz not null default now(),
    constraint ck_essay_examinations_score check (score between 0 and 6),
    constraint ck_essay_examinations_exam_type check (exam_type in ('guided', 'unguided'))
);

create index if not exists ix_essay_examinations_essay_type_examined
    on essaycards.essay_examinations(essay_id, exam_type, examined_at desc);

-- ── 3. essaycards.essay_oral_state ─────────────────────────────────────────
-- One row per essay that has had at least one essay-scope attempt; an ABSENT
-- row means "no attempts: both passed flags false". Single writer:
-- backend/oral_state.py, in the same transaction as the attempt INSERT.
--
-- guided_passed is STICKY (a later failed guided attempt never clears it).
-- unguided_passed is the CURRENT mastery claim (Essay Violet): set by a
-- passing unguided attempt, cleared by a failing unguided attempt made while
-- it was true (backend/oral_state.py failure cascade).
-- *_latest_score caches the most recent attempt's score (pass or fail).
-- unguided_passed_at is retained after invalidation as "last time passed";
-- unguided_invalidated_at records when the claim was last revoked and is set
-- back to null by the next passing unguided attempt.
create table if not exists essaycards.essay_oral_state (
    essay_id                 uuid        primary key references essaycards.essays(id) on delete cascade,
    guided_passed            boolean     not null default false,
    guided_passed_at         timestamptz,
    guided_latest_score      smallint,
    unguided_passed          boolean     not null default false,
    unguided_passed_at       timestamptz,
    unguided_invalidated_at  timestamptz,
    unguided_latest_score    smallint,
    updated_at               timestamptz not null default now(),
    constraint ck_essay_oral_state_guided_score
        check (guided_latest_score is null or guided_latest_score between 0 and 6),
    constraint ck_essay_oral_state_unguided_score
        check (unguided_latest_score is null or unguided_latest_score between 0 and 6),
    constraint ck_essay_oral_state_guided_ts
        check (not guided_passed or guided_passed_at is not null),
    constraint ck_essay_oral_state_unguided_ts
        check (not unguided_passed or unguided_passed_at is not null)
);

-- ── 4. essaycards.section_oral_state (+ one-time backfill) ─────────────────
-- Same semantics as essay_oral_state, per section. Absent row = not started.
-- guided_pass_source distinguishes a real passing exam ('exam') from the
-- one-time Sprint14 grandfathering ('grandfathered', see backfill below) so
-- grandfathered unlocks stay visible and auditable (R-CON-BP-03).
--
-- Unguided pass state is invalidated for every section of an essay when a
-- Violet essay fails its unguided essay oral (backend/oral_state.py). A
-- failed SECTION-scope unguided attempt does NOT clear unguided_passed.
--
-- The whole block (create + backfill) is guarded by the table's own absence,
-- so the backfill runs exactly once — never re-grandfathering a section that
-- was deliberately left locked after this sprint ships.
do $$ begin
    if not exists (
        select 1 from information_schema.tables
        where table_schema = 'essaycards' and table_name = 'section_oral_state'
    ) then
        create table essaycards.section_oral_state (
            section_id               uuid        primary key references essaycards.essay_sections(id) on delete cascade,
            guided_passed            boolean     not null default false,
            guided_pass_source       text,
            guided_passed_at         timestamptz,
            guided_latest_score      smallint,
            unguided_passed          boolean     not null default false,
            unguided_passed_at       timestamptz,
            unguided_invalidated_at  timestamptz,
            unguided_latest_score    smallint,
            updated_at               timestamptz not null default now(),
            constraint ck_section_oral_state_guided_source
                check (guided_pass_source is null or guided_pass_source in ('exam', 'grandfathered')),
            constraint ck_section_oral_state_guided_source_required
                check (not guided_passed or guided_pass_source is not null),
            constraint ck_section_oral_state_guided_score
                check (guided_latest_score is null or guided_latest_score between 0 and 6),
            constraint ck_section_oral_state_unguided_score
                check (unguided_latest_score is null or unguided_latest_score between 0 and 6),
            constraint ck_section_oral_state_unguided_ts
                check (not unguided_passed or unguided_passed_at is not null)
        );

        -- One-time backfill. Rows are created only for sections with some
        -- history; a section with none keeps an absent row (= not started).
        --   guided_passed (grandfathered) if ANY of:
        --     (a) a guided exam passes under the new 70% rule  -> source 'exam'
        --     (b) a guided exam scored >= 3 (the Sprint12 pass bar) or
        --     (c) the section has at least one reviewed card (learning already
        --         in progress; locking it would strand reviewed cards)
        --                                                      -> 'grandfathered'
        --   unguided_passed: any unguided attempt passes under the new rule.
        --   guided_passed_at is set only for source 'exam' (a real exam date).
        insert into essaycards.section_oral_state
            (section_id, guided_passed, guided_pass_source, guided_passed_at, guided_latest_score,
             unguided_passed, unguided_passed_at, unguided_latest_score)
        select
            s.id,
            (coalesce(g.pass_new, false) or coalesce(g.pass_legacy, false) or rv.has_reviewed),
            case when coalesce(g.pass_new, false) then 'exam'
                 when coalesce(g.pass_legacy, false) or rv.has_reviewed then 'grandfathered' end,
            case when coalesce(g.pass_new, false) then g.last_pass_new_at end,
            g.latest_score,
            coalesce(u.pass_new, false),
            u.last_pass_new_at,
            u.latest_score
        from essaycards.essay_sections s
        left join lateral (
            select bool_or(passed)                                  as pass_new,
                   bool_or(score >= 3)                              as pass_legacy,
                   max(examined_at) filter (where passed)           as last_pass_new_at,
                   (array_agg(score order by examined_at desc))[1]  as latest_score
            from essaycards.section_examinations
            where section_id = s.id and exam_type = 'guided'
        ) g on true
        left join lateral (
            select bool_or(passed)                                  as pass_new,
                   max(examined_at) filter (where passed)           as last_pass_new_at,
                   (array_agg(score order by examined_at desc))[1]  as latest_score
            from essaycards.section_examinations
            where section_id = s.id and exam_type = 'unguided'
        ) u on true
        left join lateral (
            select exists (
                select 1
                from essaycards.flashcards f
                join essaycards.flashcard_review_state frs on frs.flashcard_id = f.id
                where f.section_id = s.id and frs.last_reviewed_at is not null
            ) as has_reviewed
        ) rv on true
        where coalesce(g.pass_new, false) or coalesce(g.pass_legacy, false) or rv.has_reviewed
           or g.latest_score is not null
           or coalesce(u.pass_new, false) or u.latest_score is not null;
    end if;
end $$;

-- ── 5. flashcard_review_state.needs_revalidation ───────────────────────────
-- Temporary diagnostic flag (draft §13). true = the card was flagged when its
-- essay's unguided full-essay oral was failed while Violet, and has not yet
-- been checked. Cleared by exactly one writer: POST /flashcards/{id}/review
-- (either outcome). Setting/clearing it NEVER touches last_reviewed_at,
-- next_due_at, review_interval or fsrs_card_state by itself. Only cards with
-- last_reviewed_at IS NOT NULL are ever flagged.
alter table essaycards.flashcard_review_state
    add column if not exists needs_revalidation boolean not null default false;

-- Partial index: the revalidation queue and per-essay pending counts only
-- ever look at the (small) flagged subset.
create index if not exists ix_review_state_needs_revalidation
    on essaycards.flashcard_review_state(flashcard_id) where needs_revalidation;

-- ── 6. essaycards.revalidation_events ──────────────────────────────────────
-- Append-only audit: one row per revalidation check. NOT review_events — a
-- 'preserved' check is deliberately not a normal FSRS review and must not
-- inflate recall/unique/first review statistics. A 'failed' check ALSO
-- produces a normal review_events row (it is a genuine FSRS failure); this
-- table additionally records that it came from a revalidation.
create table if not exists essaycards.revalidation_events (
    id            uuid        primary key default gen_random_uuid(),
    flashcard_id  uuid        not null references essaycards.flashcards(id) on delete cascade,
    essay_id      uuid        not null references essaycards.essays(id) on delete cascade,
    grade         text        not null,
    outcome       text        not null,
    checked_at    timestamptz not null default now(),
    constraint ck_revalidation_events_grade check (grade in ('again', 'hard', 'good', 'easy')),
    constraint ck_revalidation_events_outcome check (outcome in ('preserved', 'failed'))
);

create index if not exists ix_revalidation_events_essay_checked
    on essaycards.revalidation_events(essay_id, checked_at desc);
