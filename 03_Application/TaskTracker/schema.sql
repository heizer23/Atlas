begin;

create schema if not exists tasktracker;

create table if not exists tasktracker.tasks (
    id          uuid        primary key default gen_random_uuid(),
    title       text        not null,
    description text,
    status      text        not null default 'open'
                            check (status in ('open', 'in_progress', 'pending', 'done')),
    priority    text        not null default 'medium'
                            check (priority in ('low', 'medium', 'high')),
    due_date     date,
    effort_hours double precision check (effort_hours is null or effort_hours >= 0),
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now()
);

create index if not exists ix_tasks_status
    on tasktracker.tasks(status);

create index if not exists ix_tasks_created_at
    on tasktracker.tasks(created_at desc);

commit;
