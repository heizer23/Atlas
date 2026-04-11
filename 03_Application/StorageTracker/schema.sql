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

commit;
