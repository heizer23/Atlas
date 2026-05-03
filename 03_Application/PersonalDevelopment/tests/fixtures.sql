-- PersonalDevelopment Sprint01-Core test fixtures
-- Loaded before each test (after truncating tasktracker.tasks).
-- IDs use fix- prefix for readability.

-- Training units
INSERT INTO tasktracker.tasks
    (id, title, description, status, priority, task_type)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'Learn Python',
     E'A deep dive into Python.\n\n## Potential Subtasks\n- [ ] Session 1\n- [ ] Session 2',
     'open', 'high', 'training_unit'),

    ('00000000-0000-0000-0000-000000000004', 'Learn Rust',
     'Systems programming unit.', 'done', 'medium', 'training_unit'),

    ('00000000-0000-0000-0000-000000000005', 'Learn SQL',
     'Database fundamentals.', 'open', 'low', 'training_unit');

-- Child tasks for fix-unit-1 (Learn Python)
INSERT INTO tasktracker.tasks
    (id, title, status, priority, task_type, parent_task_id, completed_at)
VALUES
    ('00000000-0000-0000-0000-000000000002', 'Python Session 1',
     'done', 'medium', 'training_session',
     '00000000-0000-0000-0000-000000000001',
     '2026-04-01T10:00:00Z'),

    ('00000000-0000-0000-0000-000000000003', 'Python Session 2',
     'open', 'medium', 'training_session',
     '00000000-0000-0000-0000-000000000001',
     NULL);

-- A normal task (should appear in main list, not in training-units)
INSERT INTO tasktracker.tasks
    (id, title, status, priority, task_type)
VALUES
    ('00000000-0000-0000-0000-000000000006', 'Buy groceries',
     'open', 'low', 'normal');
