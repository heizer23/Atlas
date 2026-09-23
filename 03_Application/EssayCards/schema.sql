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

-- ── Sprint10_DualSchedulerAB ─────────────────────────────────────────────────
--
-- Folded verbatim from Sprint10_DualSchedulerAB/10_schema.sql, with one
-- documentation fix carried in from 13_design_review.md's approved-as-is
-- optional cleanup: the review_events index below (and its comment) now
-- matches the corrected prior_review_interval-based dashboard filter instead
-- of the disproven was_due-based one.
--
-- essaycards.flashcard_review_state — scheduler assignment columns.
-- Assignment is permanent, decided exactly once per card
-- (backend/scheduling.py::decide_scheduler_assignment), at the existing
-- `if was_inserted:` gate already present at all three flashcard-creation
-- call sites (backend/ingest.py, backend/routers/flashcards.py,
-- backend/exploration.py), or by the one-time migration backfill below for
-- cards that already existed before this sprint. No endpoint accepts a
-- scheduler field in any request body — this is exclusively a server-side
-- side effect.
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

-- Supports the experiment dashboard's GROUP BY scheduler ... FILTER (WHERE
-- prior_review_interval >= interval '24 hours') aggregates — the actual
-- corrected ordinary-due-review filter (NOT was_due; see the table comment
-- above and 13_design_review.md's approved optional cleanup).
create index if not exists ix_review_events_scheduler_prior_interval
    on essaycards.review_events(scheduler, prior_review_interval);

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
