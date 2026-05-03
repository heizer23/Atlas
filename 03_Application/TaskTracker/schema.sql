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

-- Sprint01-Core (PersonalDevelopment): learning domain columns
-- All statements are idempotent via IF NOT EXISTS / ADD COLUMN IF NOT EXISTS.

alter table tasktracker.tasks
    add column if not exists task_type text not null default 'normal'
        check (task_type in ('normal', 'training_unit', 'training_session'));

alter table tasktracker.tasks
    add column if not exists parent_task_id uuid
        references tasktracker.tasks(id) on delete set null;

alter table tasktracker.tasks
    add column if not exists actual_duration_minutes integer
        check (actual_duration_minutes is null or actual_duration_minutes >= 0);

alter table tasktracker.tasks
    add column if not exists completed_at timestamptz;

create index if not exists ix_tasks_task_type
    on tasktracker.tasks(task_type);

create index if not exists ix_tasks_parent_task_id
    on tasktracker.tasks(parent_task_id);

commit;
