begin;

create schema if not exists habittracker;

-- Habit definitions. Never deleted — archiving sets end_date; un-archiving
-- clears it (PATCH /habits/{habit_id}, same endpoint, no separate archive
-- route). Seeded once at first run by backend/database.py::seed_starter_habits()
-- (idempotent by table-emptiness, not by name — see Sprint01_Core/10_architecture.json
-- contracts.invariants), not by a seed INSERT in this file, so active_from
-- can be the actual Europe/Berlin date the app first starts.
create table if not exists habittracker.habits (
    id               uuid        primary key default gen_random_uuid(),
    name             text        not null check (name <> ''),
    description      text,
    default_checked  boolean     not null default false,
    -- Unique and DEFERRABLE: POST /habits/reorder sets every habit's
    -- display_order in one multi-row UPDATE inside a transaction that defers
    -- this constraint to commit time, so a full permutation (including
    -- swaps) never trips a uniqueness violation mid-statement. See
    -- Sprint01_Core/10_architecture.json internal_flow step 5.
    display_order    integer     not null,
    active_from      date        not null,
    -- null = still active. Set only when archived; never deleted.
    end_date         date,
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now(),
    constraint uq_habits_display_order
        unique (display_order) deferrable initially immediate,
    -- Backstop for the backend's pre-write check in PATCH /habits/{habit_id}
    -- (Sprint01_Core/10_architecture.json internal_flow step 4) — resolved
    -- design question: validation lives in both layers (R-CON-BP-09).
    constraint ck_habits_end_date_after_active_from
        check (end_date is null or end_date >= active_from)
);

-- One row per calendar date, ever. No row = Unreviewed (there is no stored
-- "unreviewed" state). status transitions draft <-> confirmed freely;
-- confirmed_at is stamped on every transition INTO 'confirmed' and left
-- untouched otherwise (never cleared — a row's existence already implies
-- draft-or-later; see Sprint01_Core/10_architecture.json contracts.invariants).
create table if not exists habittracker.daily_reviews (
    id             uuid        primary key default gen_random_uuid(),
    review_date    date        not null,
    status         text        not null check (status in ('draft', 'confirmed')),
    confirmed_at   timestamptz,
    created_at     timestamptz not null default now(),
    updated_at     timestamptz not null default now(),
    constraint uq_daily_reviews_review_date unique (review_date)
);

-- Individual per-habit, per-date results. Paired with Habit by review_date
-- (a plain date column, not a surrogate FK to daily_reviews.id) so every
-- query reads directly as "where review_date = $1" without an extra join —
-- same rationale as StoryReader's version-pinning pattern. Referential
-- integrity to an existing daily_reviews row is still enforced, via the
-- composite-style FK on review_date below (daily_reviews.review_date is
-- itself unique).
create table if not exists habittracker.habit_results (
    id             uuid        primary key default gen_random_uuid(),
    review_date    date        not null,
    habit_id       uuid        not null references habittracker.habits(id),
    checked        boolean     not null,
    -- Reserved for a later sprint's automatic data sources. 'manual' is the
    -- only value this sprint — enforced here so a future migration only
    -- needs to relax this check, not add the column.
    source         text        not null default 'manual' check (source = 'manual'),
    created_at     timestamptz not null default now(),
    updated_at     timestamptz not null default now(),
    constraint uq_habit_results_review_date_habit
        unique (review_date, habit_id),
    constraint fk_habit_results_review_date
        foreign key (review_date)
        references habittracker.daily_reviews (review_date)
        on delete cascade
);

-- Serves both the (review_date, habit_id) lookup and the ORDER BY needs of
-- get_review_view / compute_report — the unique constraint above already
-- provides this leading-column index, so no separate index is added here.

-- Everyday-tracking sprint: habit kind + tap log.
-- kind 'binary' = done / not done today; 'quantity' = accumulates `increment`
-- per tap, shown with `unit`. Existing habits become binary.
alter table habittracker.habits add column if not exists kind text not null default 'binary';
alter table habittracker.habits add column if not exists unit text;
alter table habittracker.habits add column if not exists increment integer not null default 1;
do $$ begin
    if not exists (select 1 from pg_constraint where conname = 'ck_habits_kind') then
        alter table habittracker.habits add constraint ck_habits_kind check (kind in ('binary', 'quantity'));
        alter table habittracker.habits add constraint ck_habits_increment check (increment > 0);
    end if;
end $$;

-- Linked habits: source names an EssayCards activity kind; done-ness is read from
-- EssayCards (never logged here). null = manual habit.
alter table habittracker.habits add column if not exists source text;
do $$ begin
    if not exists (select 1 from pg_constraint where conname = 'ck_habits_source') then
        alter table habittracker.habits add constraint ck_habits_source
            check (source is null or source in ('essaycards_flashcards', 'essaycards_oral'));
    end if;
end $$;

-- One row per tap. Today's quantity = sum(amount); undo = delete the newest row.
-- Independent of the legacy daily_reviews/habit_results tables, which stay as history.
create table if not exists habittracker.habit_entries (
    id          uuid        primary key default gen_random_uuid(),
    habit_id    uuid        not null references habittracker.habits(id),
    entry_date  date        not null,
    amount      integer     not null check (amount > 0),
    created_at  timestamptz not null default now()
);
create index if not exists ix_habit_entries_date on habittracker.habit_entries (entry_date, habit_id);

-- Categories & priorities sprint. Both are plain data (editable), not code.
-- kind 'achievement' = an active task completed; 'discipline' = abstaining from something.
-- Level calculation is dispatched on kind in backend/category_progress.py.
create table if not exists habittracker.habit_categories (
    id             uuid        primary key default gen_random_uuid(),
    name           text        not null check (name <> ''),
    kind           text        not null default 'achievement' check (kind in ('achievement', 'discipline')),
    display_order  integer     not null default 0,
    created_at     timestamptz not null default now(),
    constraint uq_habit_categories_name unique (name)
);

-- Contribution levels (1 = small .. 3 = major). Labels are editable; the level number is the rank.
create table if not exists habittracker.habit_priorities (
    level        smallint primary key check (level >= 1),
    label        text     not null,
    description  text
);

-- null = legacy / uncategorised habit (excluded from category progress, shown ungrouped).
alter table habittracker.habits add column if not exists category_id uuid references habittracker.habit_categories(id);
alter table habittracker.habits add column if not exists priority smallint references habittracker.habit_priorities(level);
-- Which layer of the daily symbol (HabitSymbol) this category draws. Stable key, independent of
-- the display name. null = not drawn.
alter table habittracker.habit_categories add column if not exists symbol_layer text
    check (symbol_layer is null or symbol_layer in ('body', 'mind', 'organization', 'discipline'));
create index if not exists ix_habits_category on habittracker.habits (category_id);

commit;
