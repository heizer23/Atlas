-- 10_schema.sql — TaskTracker — Sprint11_TodayAndRecurrence
-- Seeded from runtime schema.sql (03_Application/TaskTracker/schema.sql); only the Sprint11 block at the end is new.
-- The implementer appends that block to the runtime schema.sql (canonical path) and writes the SAME block to
-- 03_Application/TaskTracker/migrations/011_recurrence.sql (wrapped in begin/commit). All statements idempotent.

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

-- Sprint09: scheduled status support
alter table tasktracker.tasks
    drop constraint if exists tasks_status_check;

alter table tasktracker.tasks
    add constraint tasks_status_check
        check (status in ('open', 'in_progress', 'scheduled', 'pending', 'done'));

alter table tasktracker.tasks
    add column if not exists scheduled_at date;

create index if not exists ix_tasks_scheduled_at
    on tasktracker.tasks(scheduled_at)
    where status = 'scheduled';

-- ── Sprint11 [NEW]: recurring tasks ───────────────────────────────────────────
-- Recurring iff recurrence_freq is not null. Cross-column rules (task_type = 'normal',
-- fixed mode requires a date) are enforced at API level only, not in DDL.

alter table tasktracker.tasks
    add column if not exists recurrence_freq text
        check (recurrence_freq is null or recurrence_freq in ('daily', 'weekly', 'monthly'));

alter table tasktracker.tasks
    add column if not exists recurrence_interval integer not null default 1
        check (recurrence_interval >= 1);

alter table tasktracker.tasks
    add column if not exists recurrence_mode text not null default 'fixed'
        check (recurrence_mode in ('fixed', 'after_completion'));

-- Successor pointer = idempotency guard. Deleting the successor nulls the pointer.
alter table tasktracker.tasks
    add column if not exists recurrence_next_id uuid
        references tasktracker.tasks(id) on delete set null;

commit;
