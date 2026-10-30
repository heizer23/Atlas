-- Sprint11: recurring tasks (idempotent)

begin;

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
