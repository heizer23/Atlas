begin;

create schema if not exists essaycards;

create table if not exists essaycards.essays (
    id         uuid        primary key default gen_random_uuid(),
    title      text        not null,
    slug       text        not null,
    -- Which overview-page group the essay is filed under (e.g. 'Art',
    -- 'History', 'Philosophy'). Free text, deliberately NOT constrained to a
    -- fixed set — new categories are added without a schema change and without
    -- a lookup table. An essay has at most one category; null means
    -- "uncategorized" and is rendered in its own trailing group by the UI.
    category   text,
    -- Author-assigned position of the essay WITHIN its category, ascending.
    -- Distinct from essay_sections.order_index (which is auto-derived from the
    -- ingest payload's array order): this one is set explicitly by the author
    -- and is the "sequence number" that used to be written into the title.
    -- Not unique — ties break on created_at asc.
    sort_index integer     not null default 0,
    -- Minimal essay lifecycle. 'planned' = the essay exists as a stub whose
    -- body text is a planning document; 'complete' = content is finished
    -- enough to learn from. More values may be added later. Default 'complete'
    -- because a normal ingest is a finished essay; a stub is ingested with an
    -- explicit status: planned.
    status     text        not null default 'complete',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint uq_essays_slug unique (slug),
    constraint ck_essays_status check (status in ('planned', 'complete'))
);

-- Additive columns for databases created before category/sort_index/status
-- existed. (create table ... if not exists above covers only fresh databases.)
alter table essaycards.essays add column if not exists category   text;
alter table essaycards.essays add column if not exists sort_index integer not null default 0;
alter table essaycards.essays add column if not exists status     text    not null default 'complete';

do $$ begin
    if not exists (select 1 from pg_constraint where conname = 'ck_essays_status') then
        alter table essaycards.essays
            add constraint ck_essays_status check (status in ('planned', 'complete'));
    end if;
end $$;

-- GET /essays returns every essay ordered (category nulls last, sort_index,
-- created_at) so the overview page can render it grouped without a re-sort.
create index if not exists ix_essays_category_sort
    on essaycards.essays(category, sort_index, created_at);

create table if not exists essaycards.essay_sections (
    id            uuid        primary key default gen_random_uuid(),
    essay_id      uuid        not null references essaycards.essays(id) on delete cascade,
    order_index   integer     not null,
    heading       text        not null,
    anchor_slug   text        not null,
    body_markdown text        not null default '',
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now(),
    constraint uq_essay_sections_anchor unique (essay_id, anchor_slug)
);

create index if not exists ix_essay_sections_essay_order
    on essaycards.essay_sections(essay_id, order_index);

create table if not exists essaycards.flashcards (
    id         uuid        primary key default gen_random_uuid(),
    essay_id   uuid        not null references essaycards.essays(id) on delete cascade,
    section_id uuid        not null references essaycards.essay_sections(id) on delete cascade,
    card_key   text        not null,
    question   text        not null,
    answer     text        not null,
    -- Structural depth (Sprint08_QuestionLevelsAndStructure): 1 = foundational
    -- / spine, 2 = building / explanatory structure, 3 = decorating / examples,
    -- terminology, anecdotes, supporting detail. Plain integer, not an enum —
    -- deliberately open-ended upward so a finer scale can be introduced later
    -- without a schema change; only >= 1 is enforced. Set exclusively by
    -- POST /flashcards/upsert (backend/routers/flashcards.py) — the
    -- essay/section JSON ingest paths (backend/ingest.py) never read or write
    -- this column, so re-ingesting an essay or section can never change it.
    level      integer     not null default 2,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint uq_flashcards_card_key unique (essay_id, card_key),
    constraint ck_flashcards_level check (level >= 1)
);

create index if not exists ix_flashcards_essay_id
    on essaycards.flashcards(essay_id);

create index if not exists ix_flashcards_section_id
    on essaycards.flashcards(section_id);

-- Additive column for databases created before level existed (Sprint08).
-- Default 2 ("building/explanatory") for every pre-existing card — a
-- neutral mid-tier guess absent any signal for which cards are foundational
-- vs. decorative; see CLAUDE.md "Question levels".
alter table essaycards.flashcards add column if not exists level integer not null default 2;

do $$ begin
    if not exists (select 1 from pg_constraint where conname = 'ck_flashcards_level') then
        alter table essaycards.flashcards add constraint ck_flashcards_level check (level >= 1);
    end if;
end $$;

create table if not exists essaycards.flashcard_review_state (
    flashcard_id      uuid        primary key references essaycards.flashcards(id) on delete cascade,
    last_reviewed_at  timestamptz,
    next_due_at       timestamptz not null,
    -- The span the card is currently scheduled across: next_due_at -
    -- last_reviewed_at, fixed at the last review. '0' for a never-reviewed
    -- ("new") card. This is a WRITE-TIME CACHE — the timestamp difference is
    -- the definition of record. Single writer: POST /flashcards/{id}/review
    -- writes it in the same statement as next_due_at; ingest seeds it '0'.
    -- Used to classify cards (new / learning / established, threshold 24h) and
    -- to order the BACKLOG queue without recomputing the difference each time.
    review_interval   interval    not null default '0',
    updated_at        timestamptz not null default now(),
    constraint ck_review_state_interval check (review_interval >= interval '0')
);

-- Additive column for databases created before review_interval existed.
alter table essaycards.flashcard_review_state
    add column if not exists review_interval interval not null default '0';

-- Backfill the cache for rows that predate the column. Guarded on
-- review_interval = '0' so it is a one-shot no-op on every subsequent startup:
-- a reviewed card's real span (next_due_at - last_reviewed_at) is always > 0
-- (the scheduler floors even `again` at 5s), so once backfilled it never
-- re-matches. Without this, an existing DB that only gets the ADD COLUMN above
-- would read every established card as interval '0' -> new/learning, emptying
-- the review queue until each card is re-reviewed.
update essaycards.flashcard_review_state
   set review_interval = next_due_at - last_reviewed_at
 where last_reviewed_at is not null
   and review_interval = interval '0';

do $$ begin
    if not exists (select 1 from pg_constraint where conname = 'ck_review_state_interval') then
        alter table essaycards.flashcard_review_state
            add constraint ck_review_state_interval check (review_interval >= interval '0');
    end if;
end $$;

-- Supports both the global due queue (no filter) and the essay/section-scoped
-- due queue (WHERE next_due_at <= now() AND essay_id = ... AND section_id = ...)
create index if not exists ix_review_state_next_due
    on essaycards.flashcard_review_state(next_due_at);

-- Historical oral-examination results. Append-only: the app never updates or
-- deletes a row here. "Current understanding" of a section is always derived
-- by querying the latest row per section_id — there is no separate stored
-- current-score field anywhere in the schema.
--
-- section_version_at is a snapshot of essay_sections.updated_at captured at
-- export time, so a later re-read of that column tells you whether the
-- section has been edited since this examination. It is a timestamp
-- equality/inequality check, not a precise content diff: an essay re-ingested
-- with byte-identical content still bumps updated_at (a false positive on
-- "changed", never a false negative).
create table if not exists essaycards.section_examinations (
    id                 uuid        primary key default gen_random_uuid(),
    essay_id           uuid        not null references essaycards.essays(id) on delete cascade,
    section_id         uuid        not null references essaycards.essay_sections(id) on delete cascade,
    section_version_at timestamptz not null,
    examined_at        timestamptz not null,
    question           text        not null,
    answer_transcript  text        not null,
    score              smallint    not null,
    feedback           text,
    created_at         timestamptz not null default now(),
    constraint ck_section_examinations_score check (score between 0 and 6)
);

-- Supports both "history for this section, most recent first" and the
-- distinct-on latest-per-section query used to build the export package.
create index if not exists ix_section_examinations_section_examined
    on essaycards.section_examinations(section_id, examined_at desc);

create index if not exists ix_section_examinations_essay
    on essaycards.section_examinations(essay_id);

-- ── Sprint03_Images ─────────────────────────────────────────────────────────
--
-- Private metadata for images imported from the staging folder. This is the
-- Postgres half of a split durable store (R-CON-BP-03): the processed image
-- bytes live as <slug>.<ext> files under images_dir (${DATA_ROOT}/essaycards/
-- images), which is NOT covered by the daily pg_dump. Both halves are owned
-- by EssayCards. The two are kept consistent by a per-file import transaction
-- (write file, INSERT row, commit; unlink on INSERT failure); GET
-- /images/{slug} returns 404 (never 500) when a row exists but its file is
-- missing.
--
-- slug is the primary key and the only public identifier — derived purely
-- from the original staged filename, plus a "-"+hash suffix on collision with
-- a different source_sha256. No slug is derived from image content or a
-- sequence.
--
-- source_sha256 (SHA-256 of the ORIGINAL staged bytes) is the idempotency
-- key: a scan re-run imports only files whose source_sha256 is not already
-- present. The CHECK on byte_size hard-codes the 5 MiB ceiling that the
-- import core (backend/import_images.py MAX_BYTES) also enforces — the two
-- are one decision and must be changed together.
create table if not exists essaycards.images (
    slug            text        primary key,
    stored_filename text        not null,       -- '<slug>.<ext>', relative to images_dir
    content_type    text        not null,
    byte_size       integer     not null,
    width           integer,                    -- null only if a pass-through GIF's dims are unreadable
    height          integer,
    source_sha256   text        not null,
    source_filename text        not null,       -- original staged name, for the Images list view
    created_at      timestamptz not null default now(),
    constraint uq_images_source_sha256 unique (source_sha256),
    constraint ck_images_content_type
        check (content_type in ('image/png', 'image/jpeg', 'image/gif', 'image/webp')),
    constraint ck_images_byte_size check (byte_size > 0 and byte_size <= 5242880)
);

-- GET /api/essaycards/images is an unfiltered "newest first" list; this index
-- keeps that ordering cheap and matches the created_at-ordered read pattern
-- already indexed for section_examinations.
create index if not exists ix_images_created_at
    on essaycards.images(created_at desc);

-- ── Sprint06_FlashcardExploration ───────────────────────────────────────────
--
-- Two tables recording the outcome of exploring a single flashcard with
-- ChatGPT (see CLAUDE.md "Flashcard exploration"). The JSON ChatGPT returns is
-- transport only — it is decomposed into these relational rows on import and is
-- never stored verbatim.
--
-- flashcard_discussions: one row per completed exploration. question_at_time /
-- answer_at_time / section_id_at_time are snapshots of the live flashcard taken
-- BEFORE any update_card action from the same import is applied, so the record
-- still means something after the card is later edited. knowledge_gap is null
-- when the discussion concluded the user's understanding was fine and only the
-- card wording was at fault. The app never updates or deletes a row here.
--
-- flashcard_revisions: one row per question/answer edit. Both the old and the
-- new value of BOTH fields are always stored (old_answer == new_answer when
-- only the question changed, and vice versa). reason is mandatory and retained
-- as evidence about what makes a flashcard question good or bad.
-- source_discussion_id links the edit to the discussion that motivated it.
-- Historical values live ONLY here — essaycards.flashcards always holds just
-- the current version used for review, so an edited-away question can never
-- reappear in the GET /flashcards/due queue.
create table if not exists essaycards.flashcard_discussions (
    id                   uuid        primary key default gen_random_uuid(),
    card_id              uuid        not null references essaycards.flashcards(id) on delete cascade,
    section_id_at_time   uuid        not null references essaycards.essay_sections(id) on delete cascade,
    question_at_time     text        not null,
    answer_at_time       text        not null,
    exploration_question text        not null,
    discussion_summary   text        not null,
    resolution           text        not null,
    knowledge_gap        text,
    created_at           timestamptz not null default now()
);

create index if not exists ix_flashcard_discussions_card
    on essaycards.flashcard_discussions(card_id, created_at desc);

create table if not exists essaycards.flashcard_revisions (
    id                   uuid        primary key default gen_random_uuid(),
    card_id              uuid        not null references essaycards.flashcards(id) on delete cascade,
    source_discussion_id uuid        references essaycards.flashcard_discussions(id) on delete set null,
    old_question         text        not null,
    new_question         text        not null,
    old_answer           text        not null,
    new_answer           text        not null,
    reason               text        not null,
    changed_at           timestamptz not null default now()
);

create index if not exists ix_flashcard_revisions_card
    on essaycards.flashcard_revisions(card_id, changed_at desc);

-- ── Sprint09_Nuggets ─────────────────────────────────────────────────────────
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
-- main_spine_markdown = '' until edited through the JSON path.
alter table essaycards.essays
    add column if not exists main_spine_markdown text not null default '';

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
-- identical-re-save limitation the section-level check already has — not
-- solved here, just not made worse.
alter table essaycards.section_examinations
    add column if not exists nugget_versions_at jsonb;

-- ── Sprint10_DualSchedulerAB (retired by Sprint12_FSRSAndUXOverhaul) ────────
--
-- Sprint10 introduced flashcard_review_state.scheduler/scheduler_assigned_at/
-- scheduler_assignment_reason/experiment_version and review_events.scheduler
-- as a permanent 50/50 Classic-vs-FSRS A/B experiment. Sprint12 makes FSRS
-- the sole scheduler and drops all five columns for good (see the
-- "Sprint12_FSRSAndUXOverhaul" block below, which backs them up to
-- essaycards.pre_fsrs_migration_backup_sprint12 first).
--
-- The ADD COLUMN / CREATE INDEX / backfill-UPDATE statements that used to
-- live here are intentionally NOT reproduced: re-adding a column in the same
-- file that later drops it would make every second execution of this file
-- (this file reruns on every application startup) re-create, re-populate,
-- and re-drop the column forever — churn with no purpose once the columns
-- are permanently retired. essaycards.fsrs_card_state (below) and the
-- `review_events` table (further below, now without its own `scheduler`
-- column) are UNCHANGED by this retirement.

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
-- POST /flashcards/{id}/review, one row inserted per review — this is what
-- backs GET /review-stats/summary|activity (the Sprint10 experiment
-- dashboard that originally motivated this table, and its own `scheduler`
-- column, were both retired by Sprint12_FSRSAndUXOverhaul), since
-- flashcard_review_state only ever holds the latest snapshot and
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
    grade                     text        not null,
    reviewed_at               timestamptz not null,
    was_due                   boolean     not null,
    prior_review_interval     interval    not null,  -- review_interval value immediately before this review
    resulting_review_interval interval    not null,  -- review_interval value this review produced
    constraint ck_review_events_grade check (grade in ('again', 'hard', 'good', 'easy'))
);

create index if not exists ix_review_events_flashcard
    on essaycards.review_events(flashcard_id, reviewed_at desc);

-- ── Sprint12_FSRSAndUXOverhaul — FSRS becomes the sole scheduler ───────────
--
-- Folded from Sprint12_FSRSAndUXOverhaul/10_schema.sql. Order within this
-- same transaction matters: back up the Sprint10 scheduler-assignment data
-- BEFORE dropping the columns that carry it (R-CON-BP-03 — this is new,
-- retained-indefinitely durable state, an audit snapshot only, never read by
-- live code), then drop those columns, then add the new exam_type column.
-- The legacy FSRS-state NUMERIC synthesis itself is deliberately NOT done
-- here in SQL — see backend/migrate_fsrs_state.py +
-- backend/scheduling.py::estimate_initial_fsrs_state, run once at every
-- startup immediately after this file, so it can reuse the exact same fsrs
-- library code/constants the live scheduler uses with zero risk of a
-- hand-duplicated SQL formula drifting from it.

-- Guarded by BOTH (a) the backup table's own absence and (b) the source
-- `scheduler` column still existing on flashcard_review_state. (a) alone is
-- not a sufficient guard: on an application instance that is upgrading from
-- a pre-Sprint12 deploy, the Sprint10 columns exist on the first run of this
-- file and must be captured before being dropped below; on a brand-new
-- database (or any rerun after the first successful pass, here or on a
-- prior deploy), those columns never exist in the first place (no Sprint10
-- ADD COLUMN statements remain in this file — see the retirement note
-- above), so the SELECT below would itself fail with UndefinedColumn if
-- attempted. Checking column existence makes this correctly idempotent in
-- both directions regardless of how many times this file reruns.
do $$ begin
    if not exists (
        select 1 from information_schema.tables
        where table_schema = 'essaycards' and table_name = 'pre_fsrs_migration_backup_sprint12'
    ) and exists (
        select 1 from information_schema.columns
        where table_schema = 'essaycards' and table_name = 'flashcard_review_state' and column_name = 'scheduler'
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

-- Every card is FSRS-only from this sprint forward — scheduler assignment is
-- no longer a live decision anywhere in the app (00_draft.md §1 "Remove
-- experimental assignment, scheduler badges, and comparison statistics").
-- `if exists` on each column/constraint/index makes every one of these
-- statements a no-op on an instance where the Sprint10 columns were never
-- (re)created in the first place (see the retirement note above) — safe on
-- both an upgrading database (columns present, backed up just above) and a
-- database that never had them.
alter table essaycards.flashcard_review_state drop column if exists scheduler;
alter table essaycards.flashcard_review_state drop column if exists scheduler_assigned_at;
alter table essaycards.flashcard_review_state drop column if exists scheduler_assignment_reason;
alter table essaycards.flashcard_review_state drop column if exists experiment_version;

-- review_events itself survives unchanged otherwise — it remains the
-- general-purpose append-only review-history log GET /review-stats/* reads
-- from.
alter table essaycards.review_events drop column if exists scheduler;

-- Distinguishes a calibration-aware "guided" oral exam (the only mode that
-- existed before this sprint) from a new, genuinely cold "unguided" mode that
-- passes no prior history/calibration context to the examiner. Required,
-- never silently defaulted by the application going forward
-- (validate_import_body rejects a missing exam_type) — the column DEFAULT
-- below exists only to backfill every pre-Sprint12 row, which was always
-- examined under the one pre-existing calibration-aware flow and is
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


-- ── Sprint13_ReviewStatsSentenceFeedback ───────────────────────────────────
-- Folded from Sprint13_ReviewStatsSentenceFeedback/10_schema.sql.

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

-- ════════════════════════════════════════════════════════════════════════════
-- Sprint14_SectionProgressionAndRevalidation (folded from Sprint14/10_schema.sql)
-- ════════════════════════════════════════════════════════════════════════════
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

commit;
