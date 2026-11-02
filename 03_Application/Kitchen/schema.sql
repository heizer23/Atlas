begin;

create schema if not exists kitchen;

-- Recipe = reusable definition. Ingredient quantities are for the full `servings`.
create table if not exists kitchen.recipes (
    id              uuid        primary key default gen_random_uuid(),
    name            text        not null unique,
    kind            text        not null check (kind in ('base', 'derived', 'favorite')),
    servings        numeric     not null default 1 check (servings > 0),
    yield_unit      text        not null default 'portions',
    steps           text        not null default '',
    shelf_life_days integer     check (shelf_life_days is null or shelf_life_days >= 0),
    storage_location text,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

-- Raw ingredient (base_recipe_id null) or prepared base (base_recipe_id set; unit = yield_unit).
create table if not exists kitchen.recipe_ingredients (
    id             uuid    primary key default gen_random_uuid(),
    recipe_id      uuid    not null references kitchen.recipes(id) on delete cascade,
    position       integer not null default 0,
    name           text    not null,
    qty            numeric not null check (qty > 0),
    unit           text    not null,
    base_recipe_id uuid    references kitchen.recipes(id)
);

create index if not exists ix_recipe_ingredients_recipe on kitchen.recipe_ingredients(recipe_id);

create table if not exists kitchen.plans (
    id         uuid        primary key default gen_random_uuid(),
    week_start date        not null,
    created_at timestamptz not null default now()
);

-- kind 'cook' = cooking session of a base recipe (produces a batch);
-- kind 'meal' = a meal to eat (derived dish / favorite); recipe_id null = flexible day.
create table if not exists kitchen.planned_meals (
    id        uuid        primary key default gen_random_uuid(),
    plan_id   uuid        not null references kitchen.plans(id) on delete cascade,
    recipe_id uuid        references kitchen.recipes(id),
    kind      text        not null check (kind in ('cook', 'meal')),
    day       date        not null,
    slot      text        not null default 'dinner',
    portions  numeric     not null default 1 check (portions > 0),
    status    text        not null default 'planned'
                          check (status in ('planned', 'cooked', 'eaten', 'skipped')),
    revision  integer     not null default 0,   -- bumped by undo; part of idempotency keys
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists ix_planned_meals_plan on kitchen.planned_meals(plan_id, day);

-- Business events (one per meal and kind => repeat confirmation is a no-op).
create table if not exists kitchen.cook_events (
    id            uuid        primary key default gen_random_uuid(),
    meal_id       uuid        not null unique references kitchen.planned_meals(id) on delete cascade,
    produced_qty  numeric     not null,
    batch_item_id integer     not null,
    created_at    timestamptz not null default now()
);

create table if not exists kitchen.consumption_events (
    id         uuid        primary key default gen_random_uuid(),
    meal_id    uuid        not null unique references kitchen.planned_meals(id) on delete cascade,
    portions   numeric     not null,
    created_at timestamptz not null default now()
);

-- Every StorageTracker movement posted on behalf of a meal; used for undo.
create table if not exists kitchen.meal_bookings (
    id          uuid        primary key default gen_random_uuid(),
    meal_id     uuid        not null references kitchen.planned_meals(id) on delete cascade,
    purpose     text        not null check (purpose in ('cook', 'eat')),
    item_id     integer     not null,
    movement_id uuid        not null unique,
    created_at  timestamptz not null default now()
);

create index if not exists ix_meal_bookings_meal on kitchen.meal_bookings(meal_id);

-- Sprint 1.1: ingredient identity = StorageTracker item id; recipe status; import metadata
alter table kitchen.recipes add column if not exists description text;
alter table kitchen.recipes add column if not exists prep_minutes integer check (prep_minutes is null or prep_minutes >= 0);
alter table kitchen.recipes add column if not exists cook_minutes integer check (cook_minutes is null or cook_minutes >= 0);
alter table kitchen.recipes add column if not exists status text not null default 'active';

do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'recipes_status_check') then
        alter table kitchen.recipes add constraint recipes_status_check check (status in ('draft', 'active'));
    end if;
end $$;

-- item_id: storagetracker.items.id = article number (opaque cross-app reference, no FK by design).
-- null + base_recipe_id null = unresolved line; name is a display label only.
alter table kitchen.recipe_ingredients add column if not exists item_id integer;

-- Article numbers are integers now (were storagetracker uuids). Databases still holding uuid references are
-- converted without values; migrate_legacy_ingredients() re-resolves recipe lines by name+unit (deploy runs a
-- precise remap first, see Sprint 1.2 notes).
do $$
declare r record;
begin
    for r in select * from (values ('recipe_ingredients', 'item_id'), ('meal_bookings', 'item_id'),
                                   ('cook_events', 'batch_item_id')) v(t, c) loop
        if (select data_type from information_schema.columns
            where table_schema = 'kitchen' and table_name = r.t and column_name = r.c) = 'uuid' then
            execute format('alter table kitchen.%I alter column %I drop not null', r.t, r.c);
            execute format('alter table kitchen.%I alter column %I type integer using null', r.t, r.c);
        end if;
    end loop;
end $$;

alter table kitchen.recipes alter column yield_unit set default 'portions';

-- Plans cover 1-7 days from week_start (the first day; name kept for compatibility).
alter table kitchen.plans add column if not exists days integer not null default 7 check (days between 1 and 7);

commit;
