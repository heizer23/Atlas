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
