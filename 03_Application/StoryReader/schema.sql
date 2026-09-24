begin;

create schema if not exists storyreader;

-- One story per stable, author-assigned slug. Never deleted or renamed via
-- any code path in this app (see 10_architecture.json contracts.invariants).
create table if not exists storyreader.stories (
    id             uuid        primary key default gen_random_uuid(),
    slug           text        not null,
    title          text        not null,
    -- Denormalized convenience — also derivable as max(version) from
    -- story_versions for this story_id. Maintained exclusively by
    -- backend/ingest.py at write time; never recomputed at read time.
    latest_version integer     not null check (latest_version >= 1),
    created_at     timestamptz not null default now(),
    updated_at     timestamptz not null default now(),
    constraint uq_stories_slug unique (slug)
);

create index if not exists ix_stories_updated_at
    on storyreader.stories(updated_at desc);

-- Immutable, append-only. No UPDATE statement in the codebase ever targets
-- this table's body_markdown/content_sha256/version columns after insert.
create table if not exists storyreader.story_versions (
    id             uuid        primary key default gen_random_uuid(),
    story_id       uuid        not null references storyreader.stories(id) on delete cascade,
    version        integer     not null check (version >= 1),
    body_markdown  text        not null,
    -- sha256 of body_markdown (front matter already stripped), the
    -- idempotency key compared against the story's CURRENT latest version
    -- only on re-ingestion — never against the full version history.
    content_sha256 text        not null,
    created_at     timestamptz not null default now(),
    constraint uq_story_versions_story_version unique (story_id, version)
);

create index if not exists ix_story_versions_story_id
    on storyreader.story_versions(story_id);

-- An annotation always carries the exact (story_id, version) it was made
-- against. version is deliberately NOT a foreign key to story_versions.id
-- (the surrogate key) so that every query's WHERE clause reads
-- "story_id = $1 and version = $2" textually, per the draft's Data Model
-- rationale — referential integrity to an existing version is instead
-- enforced via the composite foreign key below, targeting the
-- (story_id, version) unique constraint on story_versions.
create table if not exists storyreader.annotations (
    id              uuid        primary key default gen_random_uuid(),
    story_id        uuid        not null references storyreader.stories(id) on delete cascade,
    version         integer     not null,
    paragraph_index integer     not null check (paragraph_index >= 0),
    char_start      integer     not null check (char_start >= 0),
    char_end        integer     not null check (char_end > char_start),
    -- Verbatim substring at [char_start, char_end) of that paragraph's
    -- rendered plain text. Server-validated to match exactly on every
    -- POST /annotations (see 10_architecture.json internal_flow step 7) —
    -- this constraint alone cannot enforce that; the check happens in
    -- application code before insert.
    selected_text   text        not null check (selected_text <> ''),
    -- Captured client-side at creation time per the exact windowing rule in
    -- 10_architecture.json contracts.invariants. The 500-character cap here
    -- is a defensive bound only, not the authoritative ~200-character window
    -- definition (which the frontend applies before ever sending these).
    context_before  text        not null default '' check (char_length(context_before) <= 500),
    context_after   text        not null default '' check (char_length(context_after)  <= 500),
    reaction        text        not null
                                check (reaction in ('positive', 'negative', 'neutral', 'unclear')),
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now(),
    constraint uq_annotations_exact_span
        unique (story_id, version, paragraph_index, char_start, char_end),
    constraint fk_annotations_story_version
        foreign key (story_id, version)
        references storyreader.story_versions (story_id, version)
        on delete cascade
);

-- Serves both list_annotations' ORDER BY (paragraph_index asc, char_start
-- asc) and the (story_id, version) lookup — the unique constraint above
-- already provides this leading-column index, so no separate index is
-- added here.

-- Sprint03: reading-position memory. Both additive, idempotent (Sprint01/02
-- runtime rows already exist). last_opened_at is touched by every position
-- save (mount included, not just a scroll) — it doubles as "most recently
-- active story," read by GET /storyreader/last-read for the app-root
-- redirect. last_read_paragraph_index is pinned to one exact
-- (story_id, version) row, mirroring how annotations are pinned per
-- version — a new version starts with no remembered position, same as it
-- starts with zero annotations.
alter table storyreader.stories
    add column if not exists last_opened_at timestamptz;

alter table storyreader.story_versions
    add column if not exists last_read_paragraph_index integer;

commit;
