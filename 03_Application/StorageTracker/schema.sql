begin;

create schema if not exists storagetracker;

create table if not exists storagetracker.items (
    id              uuid        primary key default gen_random_uuid(),
    name            text        not null,
    item_type       text        not null
                                check (item_type in ('consumable', 'object', 'pending_action')),
    state           text        not null default 'stored'
                                check (state in ('stored', 'low_stock', 'out_of_stock', 'marked_for_recycling', 'missing', 'lent_out')),
    location        text,
    notes           text,
    source_tags     jsonb       not null default '[]'::jsonb,
    quantity        integer     check (quantity is null or quantity >= 0),
    min_quantity    integer     check (min_quantity is null or min_quantity >= 0),
    restock_quantity integer    check (restock_quantity is null or restock_quantity >= 0),
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

-- Sprint02: add restock_quantity to existing deployments
alter table storagetracker.items
    add column if not exists restock_quantity integer
        check (restock_quantity is null or restock_quantity >= 0);

create index if not exists ix_items_state
    on storagetracker.items(state);

create index if not exists ix_items_item_type
    on storagetracker.items(item_type);

create index if not exists ix_items_created_at
    on storagetracker.items(created_at desc);

create table if not exists storagetracker.item_history (
    id          uuid        primary key default gen_random_uuid(),
    item_id     uuid        not null references storagetracker.items(id) on delete cascade,
    timestamp   timestamptz not null default now(),
    change_type text        not null
                            check (change_type in ('created', 'state_change', 'location_change', 'quantity_change')),
    old_value   text,
    new_value   text,
    notes       text
);

create index if not exists ix_item_history_item_id_ts
    on storagetracker.item_history(item_id, timestamp desc);

-- Sprint02: shopping tasks
create table if not exists storagetracker.shopping_tasks (
    id           uuid        primary key default gen_random_uuid(),
    item_id      uuid        not null references storagetracker.items(id) on delete cascade,
    status       text        not null default 'open'
                             check (status in ('open', 'done', 'dismissed')),
    source_tags  jsonb       not null default '[]'::jsonb,
    notes        text,
    created_at   timestamptz not null default now(),
    completed_at timestamptz
);

create unique index if not exists uq_shopping_tasks_item_open
    on storagetracker.shopping_tasks (item_id)
    where status = 'open';

create index if not exists ix_shopping_tasks_status
    on storagetracker.shopping_tasks(status);

create index if not exists ix_shopping_tasks_item_id
    on storagetracker.shopping_tasks(item_id);

-- Kitchen Sprint01: units, batches, stock-movement ledger
do $$
begin
    if (select data_type from information_schema.columns
        where table_schema = 'storagetracker' and table_name = 'items'
          and column_name = 'quantity') = 'integer' then
        alter table storagetracker.items alter column quantity type numeric;
    end if;
end $$;

alter table storagetracker.items add column if not exists unit text;
alter table storagetracker.items add column if not exists expires_at date;
alter table storagetracker.items add column if not exists recipe_ref text;
alter table storagetracker.items add column if not exists kind text not null default 'ingredient';

do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'items_kind_check') then
        alter table storagetracker.items
            add constraint items_kind_check check (kind in ('ingredient', 'batch'));
    end if;
end $$;

-- quantity is the cached sum of applied deltas; delta = applied (clamped) change
create table if not exists storagetracker.stock_movements (
    id              uuid        primary key default gen_random_uuid(),
    item_id         uuid        not null references storagetracker.items(id) on delete cascade,
    delta           numeric     not null,
    requested_delta numeric     not null,
    reason          text        not null,
    ref             text,
    idempotency_key text        unique,
    reverses_id     uuid        unique references storagetracker.stock_movements(id),
    created_at      timestamptz not null default now()
);

create index if not exists ix_stock_movements_item_ts
    on storagetracker.stock_movements(item_id, created_at desc);

-- Kitchen 1.1+: items.id becomes a single fortlaufende article number (SKU), replacing the uuid.
-- One-time conversion (runs only while items.id is still uuid). Numbering: created_at, name, old id.
-- legacy_item_ids (old uuid -> new number) was created for one-off remapping and dropped after use; the conversion
-- only runs while items.id is still uuid, so the table is never recreated.
do $$
declare
    start_n bigint;
    t text;
begin
    if (select data_type from information_schema.columns
        where table_schema = 'storagetracker' and table_name = 'items' and column_name = 'id') = 'uuid' then

        alter table storagetracker.items add column id_new integer;
        update storagetracker.items i set id_new = r.n
        from (select id, row_number() over (order by created_at, name, id) as n from storagetracker.items) r
        where i.id = r.id;

        create table if not exists storagetracker.legacy_item_ids (
            old_id uuid primary key,
            id     integer not null unique
        );
        insert into storagetracker.legacy_item_ids (old_id, id)
            select id, id_new from storagetracker.items on conflict do nothing;

        foreach t in array array['item_history', 'shopping_tasks', 'stock_movements'] loop
            execute format('alter table storagetracker.%I add column item_id_new integer', t);
            execute format('update storagetracker.%I x set item_id_new = i.id_new
                            from storagetracker.items i where x.item_id = i.id', t);
            execute format('alter table storagetracker.%I alter column item_id_new set not null', t);
            execute format('alter table storagetracker.%I drop column item_id', t);   -- drops FK + indexes
            execute format('alter table storagetracker.%I rename column item_id_new to item_id', t);
        end loop;

        alter table storagetracker.items drop constraint items_pkey;
        alter table storagetracker.items drop column id;
        alter table storagetracker.items rename column id_new to id;
        alter table storagetracker.items alter column id set not null;
        alter table storagetracker.items add primary key (id);
        select coalesce(max(id), 0) + 1 into start_n from storagetracker.items;
        execute format('alter table storagetracker.items alter column id add generated by default as identity (start with %s)', start_n);

        foreach t in array array['item_history', 'shopping_tasks', 'stock_movements'] loop
            execute format('alter table storagetracker.%I add foreign key (item_id)
                            references storagetracker.items(id) on delete cascade', t);
        end loop;
    end if;
end $$;

-- indexes dropped with the old uuid columns (idempotent for every other start)
create index if not exists ix_item_history_item_id_ts
    on storagetracker.item_history(item_id, timestamp desc);
create unique index if not exists uq_shopping_tasks_item_open
    on storagetracker.shopping_tasks (item_id) where status = 'open';
create index if not exists ix_shopping_tasks_item_id
    on storagetracker.shopping_tasks(item_id);
create index if not exists ix_stock_movements_item_ts
    on storagetracker.stock_movements(item_id, created_at desc);

-- Kitchen batch management: production date, archive flag (depleted batches leave active inventory, history stays),
-- and freeze / thaw / expiry events in the item history.
alter table storagetracker.items add column if not exists produced_at date;
alter table storagetracker.items add column if not exists archived_at timestamptz;

create index if not exists ix_items_archived on storagetracker.items(archived_at) where archived_at is not null;

alter table storagetracker.item_history drop constraint if exists item_history_change_type_check;
alter table storagetracker.item_history add constraint item_history_change_type_check
    check (change_type in ('created', 'state_change', 'location_change', 'quantity_change',
                           'expiry_change', 'freeze', 'thaw'));

-- Inventory management: per-article stock management type + category.
-- QUANTITY (default) = ledger-based counting. KANBAN = no quantity bookkeeping; items.state is the manual
-- status (stored = In Stock, low_stock = Low, out_of_stock = Out) and low/out feed the shopping list.
alter table storagetracker.items add column if not exists stock_management_type text not null default 'QUANTITY';
alter table storagetracker.items add column if not exists category text not null default 'Other';

do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'items_stock_management_type_check') then
        alter table storagetracker.items
            add constraint items_stock_management_type_check check (stock_management_type in ('QUANTITY', 'KANBAN'));
    end if;
    if not exists (select 1 from pg_constraint where conname = 'items_category_check') then
        alter table storagetracker.items
            add constraint items_category_check check (category in (
                'Vegetables & Fruit', 'Meat & Fish', 'Dairy', 'Dry Goods', 'Spices', 'Frozen', 'Beverages', 'Other'));
    end if;
end $$;

create index if not exists ix_items_category on storagetracker.items(category);

-- Central shopping list: purchase rules per article, task origin, source-tagged demands.
-- purchase_multiple = pack size (shortages are rounded UP to a multiple of it), min_purchase_qty = minimum order quantity.
-- Both are in the article's base unit; null = buy exactly the shortage.
alter table storagetracker.items add column if not exists purchase_multiple numeric
    check (purchase_multiple is null or purchase_multiple > 0);
alter table storagetracker.items add column if not exists min_purchase_qty numeric
    check (min_purchase_qty is null or min_purchase_qty > 0);

-- manual = added by the user, low_stock = created by the low/out-of-stock transition
alter table storagetracker.shopping_tasks add column if not exists origin text not null default 'manual';
do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'shopping_tasks_origin_check') then
        alter table storagetracker.shopping_tasks
            add constraint shopping_tasks_origin_check check (origin in ('manual', 'low_stock'));
    end if;
end $$;

-- Gross demand published by other apps (Kitchen, ...). One row per (source, external_ref); a source's snapshot is
-- replaced atomically and never touches other sources, manual tasks or stock. Demand is NOT a stock movement.
create table if not exists storagetracker.demands (
    id            uuid        primary key default gen_random_uuid(),
    source        text        not null,
    external_ref  text        not null,
    item_id       integer     not null references storagetracker.items(id) on delete cascade,
    qty           numeric     not null check (qty > 0),
    unit          text        not null,
    required_date date,
    label         text,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now(),
    unique (source, external_ref)
);
create index if not exists ix_demands_item on storagetracker.demands(item_id);

-- Per-source sync bookkeeping (last accepted snapshot + last rejected attempt).
create table if not exists storagetracker.demand_sync (
    source         text        primary key,
    snapshot_hash  text,
    line_count     integer     not null default 0,
    last_ok_at     timestamptz,
    last_error     jsonb,
    last_error_at  timestamptz
);

commit;
