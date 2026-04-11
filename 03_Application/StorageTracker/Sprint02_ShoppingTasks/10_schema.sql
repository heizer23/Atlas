-- Sprint02_ShoppingTasks schema additions
-- All changes are additive and idempotent.
-- Applied on top of the Sprint01_Core schema already present in Postgres.

begin;

-- Add restock_quantity to items table
alter table storagetracker.items
    add column if not exists restock_quantity integer
        check (restock_quantity is null or restock_quantity >= 0);

-- Shopping tasks table
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

-- Enforces at-most-one open task per item
create unique index if not exists uq_shopping_tasks_item_open
    on storagetracker.shopping_tasks (item_id)
    where status = 'open';

create index if not exists ix_shopping_tasks_status
    on storagetracker.shopping_tasks(status);

create index if not exists ix_shopping_tasks_item_id
    on storagetracker.shopping_tasks(item_id);

commit;
