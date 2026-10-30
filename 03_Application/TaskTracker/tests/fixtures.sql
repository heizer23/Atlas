-- TaskTracker test fixtures — Sprint09_ScheduledStatus
-- Loaded by conftest.py before each test (after truncate).
-- IDs use fix- prefix for self-documenting assertions.

-- A standard open task
insert into tasktracker.tasks (id, title, status, priority)
values ('00000000-0000-0000-0000-000000000001', 'fix-open-task', 'open', 'medium');

-- A scheduled task due in the future (tomorrow = schedule not yet due)
-- scheduled_at set to a far-future date so auto-promotion never fires in tests
insert into tasktracker.tasks (id, title, status, priority, scheduled_at)
values (
    '00000000-0000-0000-0000-000000000002',
    'fix-scheduled-future',
    'scheduled',
    'high',
    now() + interval '7 days'
);

-- A second scheduled task due in the future (later than the first above)
insert into tasktracker.tasks (id, title, status, priority, scheduled_at)
values (
    '00000000-0000-0000-0000-000000000003',
    'fix-scheduled-further',
    'scheduled',
    'low',
    now() + interval '14 days'
);

-- A scheduled task that is past-due (yesterday) — used in auto-promotion tests
insert into tasktracker.tasks (id, title, status, priority, scheduled_at)
values (
    '00000000-0000-0000-0000-000000000004',
    'fix-scheduled-past',
    'scheduled',
    'medium',
    now() - interval '1 day'
);

-- ── Sprint11_TodayAndRecurrence ──────────────────────────────────────────────
-- Agenda and recurrence fixtures; dates relative to current_date.
-- Note: fix-scheduled-future lands on today+7 (upcoming boundary), fix-scheduled-further on today+14 (outside window).

insert into tasktracker.tasks (id, title, status, priority, due_date, effort_hours)
values ('00000000-0000-0000-0000-000000000011', 'fix-overdue', 'open', 'medium', current_date - 2, 1);

insert into tasktracker.tasks (id, title, status, priority, due_date, effort_hours)
values ('00000000-0000-0000-0000-000000000012', 'fix-due-today', 'open', 'high', current_date, 1);

-- Recurring: weekly every 2, fixed
insert into tasktracker.tasks
    (id, title, description, status, priority, due_date, effort_hours,
     recurrence_freq, recurrence_interval, recurrence_mode)
values ('00000000-0000-0000-0000-000000000013', 'fix-recurring-weekly', 'fixture description', 'open', 'high',
        current_date + 1, 2.5, 'weekly', 2, 'fixed');

-- Recurring: daily, after completion, no dates
insert into tasktracker.tasks (id, title, status, priority, recurrence_freq, recurrence_mode)
values ('00000000-0000-0000-0000-000000000014', 'fix-recurring-after', 'open', 'medium', 'daily', 'after_completion');

-- Recurring: scheduled weekly (blocker successor)
insert into tasktracker.tasks
    (id, title, status, priority, scheduled_at, due_date, recurrence_freq)
values ('00000000-0000-0000-0000-000000000015', 'fix-recurring-scheduled', 'scheduled', 'medium',
        current_date + 2, current_date + 4, 'weekly');
