BEGIN;

CREATE SCHEMA IF NOT EXISTS tasktracker;

CREATE TABLE IF NOT EXISTS tasktracker.tasks (
    id          uuid        primary key default gen_random_uuid(),
    title       text        not null,
    description text,
    status      text        not null default 'open'
                            check (status in ('open', 'in_progress', 'done')),
    priority    text        not null default 'medium'
                            check (priority in ('low', 'medium', 'high')),
    due_date    date,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);

CREATE INDEX IF NOT EXISTS ix_tasks_status
    ON tasktracker.tasks(status);

CREATE INDEX IF NOT EXISTS ix_tasks_created_at
    ON tasktracker.tasks(created_at desc);

COMMIT;
