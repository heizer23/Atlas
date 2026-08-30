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

commit;
