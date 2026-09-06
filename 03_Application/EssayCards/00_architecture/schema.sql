begin;

create schema if not exists essaycards;

create table if not exists essaycards.essays (
    id         uuid        primary key default gen_random_uuid(),
    title      text        not null,
    slug       text        not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint uq_essays_slug unique (slug)
);

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
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint uq_flashcards_card_key unique (essay_id, card_key)
);

create index if not exists ix_flashcards_essay_id
    on essaycards.flashcards(essay_id);

create index if not exists ix_flashcards_section_id
    on essaycards.flashcards(section_id);

create table if not exists essaycards.flashcard_review_state (
    flashcard_id      uuid        primary key references essaycards.flashcards(id) on delete cascade,
    last_reviewed_at  timestamptz,
    next_due_at       timestamptz not null,
    updated_at        timestamptz not null default now()
);

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

-- ── Sprint06_FlashcardExploration ───────────────────────────────────────────
-- Outcome of exploring a single flashcard with ChatGPT. The returned JSON is
-- transport only and is decomposed into these relational rows on import.
-- flashcard_discussions: one row per completed exploration, with pre-edit
-- snapshots of the live card. flashcard_revisions: one row per question/answer
-- edit, storing both old and new values of both fields plus a mandatory reason;
-- historical values live only here so an edited-away question never reappears
-- in GET /flashcards/due.
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

commit;
