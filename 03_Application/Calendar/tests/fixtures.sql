-- Calendar Sprint01_Core — test fixtures
--
-- Three events covering the main scenarios:
--   fix-morning:  standalone personal block (no task link, has notes)
--   fix-task-lnk: task_block linked to task-abc-123 (has notes, for null-clear test)
--   fix-personal:  simple personal block (for delete test)

INSERT INTO calendar_events
  (id, title, start_at, end_at, event_type, source_object_type, source_object_id, notes)
VALUES
  (
    'f0000001-0000-0000-0000-000000000000',
    'Morning Focus Block',
    '2026-01-05T09:00:00+00:00',
    '2026-01-05T10:00:00+00:00',
    'personal_block',
    NULL,
    NULL,
    'Deep work session'
  ),
  (
    'f0000002-0000-0000-0000-000000000000',
    'Task Linked Block',
    '2026-01-06T14:00:00+00:00',
    '2026-01-06T15:00:00+00:00',
    'task_block',
    'task',
    'task-abc-123',
    'Working on sprint'
  ),
  (
    'f0000003-0000-0000-0000-000000000000',
    'Personal Block',
    '2026-01-07T10:00:00+00:00',
    '2026-01-07T11:00:00+00:00',
    'personal_block',
    NULL,
    NULL,
    NULL
  );
