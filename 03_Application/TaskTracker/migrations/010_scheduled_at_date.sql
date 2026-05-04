-- Sprint10 fix: change scheduled_at from timestamptz to date.
-- The exact time lives in the calendar event; the task only needs the date.

begin;

-- Drop the partial index before altering the column type
drop index if exists tasktracker.ix_tasks_scheduled_at;

alter table tasktracker.tasks
    alter column scheduled_at type date using scheduled_at::date;

create index if not exists ix_tasks_scheduled_at
    on tasktracker.tasks(scheduled_at)
    where status = 'scheduled';

commit;
