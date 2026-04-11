-- StorageTracker Sprint 1 — test fixtures
--
-- IDs use pattern f1000001-... (f1 = fixture, 000001 = sequence number)
-- All chars are valid hex — readable in test output.

-- ── Consumables ──────────────────────────────────────────────────────────────

INSERT INTO storagetracker.items
  (id, name, item_type, state, quantity, min_quantity, source_tags, location, notes)
VALUES
  ('f1000001-0000-0000-0000-000000000000', 'milk',           'consumable', 'low_stock',    1,    3,    '["Rewe"]',           'fridge',          null),
  ('f1000002-0000-0000-0000-000000000000', 'coffee',         'consumable', 'stored',       4,    2,    '["Rewe", "Aldi"]',   'kitchen cabinet', null),
  ('f1000003-0000-0000-0000-000000000000', 'razor blades',   'consumable', 'out_of_stock', 0,    2,    '["DM"]',             'bathroom',        null),
  ('f1000004-0000-0000-0000-000000000000', 'salt',           'consumable', 'low_stock',    null, null, '["Aldi"]',           'kitchen cabinet', null),
  ('f1000005-0000-0000-0000-000000000000', 'dishwasher tabs','consumable', 'stored',       30,   6,    '["Rewe", "Amazon"]', 'under sink',      null);

-- ── Objects ───────────────────────────────────────────────────────────────────

INSERT INTO storagetracker.items
  (id, name, item_type, state, location, notes)
VALUES
  ('f1000006-0000-0000-0000-000000000000', 'spare charger', 'object', 'stored',               'desk drawer',    null),
  ('f1000007-0000-0000-0000-000000000000', 'friend''s key', 'object', 'lent_out',             'with friend',    'Alex has it'),
  ('f1000008-0000-0000-0000-000000000000', 'passport',      'object', 'missing',              null,             'last seen: hallway'),
  ('f1000009-0000-0000-0000-000000000000', 'old printer',   'object', 'marked_for_recycling', 'basement shelf', null);

-- ── History entries ───────────────────────────────────────────────────────────

INSERT INTO storagetracker.item_history
  (item_id, change_type, old_value, new_value, notes)
VALUES
  ('f1000001-0000-0000-0000-000000000000', 'quantity_change', '3',      '1',                   null),
  ('f1000001-0000-0000-0000-000000000000', 'state_change',    'stored', 'low_stock',            'auto-transition'),
  ('f1000007-0000-0000-0000-000000000000', 'state_change',    'stored', 'lent_out',             null),
  ('f1000007-0000-0000-0000-000000000000', 'location_change', 'hallway drawer', 'with friend',  null),
  ('f1000009-0000-0000-0000-000000000000', 'state_change',    'stored', 'marked_for_recycling', null);
