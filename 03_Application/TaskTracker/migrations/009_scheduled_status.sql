-- Migration 009: add scheduled task status
-- Expands the status CHECK constraint to include 'scheduled',
-- adds scheduled_at timestamptz column, and creates a partial index.

begin;

alter table tasktracker.tasks
    drop constraint if exists tasks_status_check;

alter table tasktracker.tasks
    add constraint tasks_status_check
        check (status in ('open', 'in_progress', 'scheduled', 'pending', 'done'));

alter table tasktracker.tasks
    add column if not exists scheduled_at timestamptz;

create index if not exists ix_tasks_scheduled_at
    on tasktracker.tasks(scheduled_at)
    where status = 'scheduled';

commit;
