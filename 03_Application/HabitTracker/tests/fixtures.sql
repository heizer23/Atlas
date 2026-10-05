-- HabitTracker — Sprint01_Core test fixtures
--
-- fix-id traceability (referenced by name in Sprint01_Core/10_test_spec.md):
--   fix-habit-worked-out -> 10000001-...-000000000001 ("Worked out",               display_order 0, active_from 2026-01-01)
--   fix-habit-no-sweets  -> 10000002-...-000000000002 ("No sweets",                display_order 1, active_from 2026-01-01)
--   fix-habit-no-vaping  -> 10000003-...-000000000003 ("No vaping",                display_order 2, active_from 2026-01-01)
--   fix-habit-bp         -> 10000004-...-000000000004 ("Measured blood pressure",  display_order 3, active_from 2026-01-01)
--   fix-habit-essaycards -> 10000005-...-000000000005 ("Reviewed EssayCards",      display_order 4, active_from 2026-01-01)
--   fix-habit-archived   -> 10000006-...-000000000006 ("Retired habit",            display_order 5, active 2025-01-01..2025-06-01, archived)
--
-- "Habit list — starter seed present on first run" (10_test_spec.md) needs a
-- genuinely empty habits table, which this fixtures.sql's named habits (needed
-- by every other scenario) cannot simultaneously provide — test_habits.py
-- tests that scenario by truncating locally within that one test and calling
-- seed_starter_habits() directly (see its docstring; logged as an
-- implementer_note in 00_Blueprint/Quality/agent_rule_evidence.md).

INSERT INTO habittracker.habits (id, name, description, default_checked, display_order, active_from, end_date) VALUES
  ('10000001-0000-0000-0000-000000000001', 'Worked out',               NULL, false, 0, '2026-01-01', NULL),
  ('10000002-0000-0000-0000-000000000002', 'No sweets',                NULL, false, 1, '2026-01-01', NULL),
  ('10000003-0000-0000-0000-000000000003', 'No vaping',                NULL, false, 2, '2026-01-01', NULL),
  ('10000004-0000-0000-0000-000000000004', 'Measured blood pressure',  NULL, false, 3, '2026-01-01', NULL),
  ('10000005-0000-0000-0000-000000000005', 'Reviewed EssayCards',      NULL, false, 4, '2026-01-01', NULL),
  ('10000006-0000-0000-0000-000000000006', 'Retired habit',            NULL, false, 5, '2025-01-01', '2025-06-01');
