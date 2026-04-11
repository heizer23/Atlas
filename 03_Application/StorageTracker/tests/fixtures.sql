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

-- ── Sprint02: additional items ────────────────────────────────────────────────
-- f1000010: stored_item — for manual task creation (has source_tags=['Rewe'])
-- f1000011: low_stock_item — already low_stock, has an open task (open_task)
-- f1000012: watch_item — stored, no open task (for auto-task creation test)
-- f1000013: milk (restock) — consumable with restock_quantity=6 for done+restock test
-- f1000014: low_restock_item — restock_quantity=4 < min_quantity=5, stays low_stock on done
-- f1000015: cable — object, out_of_stock, no restock_quantity (done→stored without qty change)
-- f1000016: dismiss_item — low_stock with open task (for dismissed test)
-- f1000017: cascade_item — stored, has open task (for cascade delete test)
-- f1000018: notag_item — no source_tags, has open task (by_source 'Other' group)
-- f1000019: multi_tag_item — source_tags=['Rewe','Amazon'], has open task (by_source multi-group)
-- f1000020: delete_item — has a task to be explicitly deleted (delete_task)

INSERT INTO storagetracker.items
  (id, name, item_type, state, quantity, min_quantity, restock_quantity, source_tags, location, notes)
VALUES
  ('f1000010-0000-0000-0000-000000000000', 'stored_item',      'consumable', 'stored',    5,  2, null, '["Rewe"]',             null, null),
  ('f1000011-0000-0000-0000-000000000000', 'low_stock_item',   'consumable', 'low_stock', 1,  3, null, '["DM"]',               null, null),
  ('f1000012-0000-0000-0000-000000000000', 'watch_item',       'object',     'stored',    null, null, null, '["Ebay"]',         null, null),
  ('f1000013-0000-0000-0000-000000000000', 'restock_milk',     'consumable', 'low_stock', 1,  3, 6,    '["Rewe"]',             'fridge', null),
  ('f1000014-0000-0000-0000-000000000000', 'low_restock_item', 'consumable', 'low_stock', 1,  5, 4,    '[]',                   null, null),
  ('f1000015-0000-0000-0000-000000000000', 'cable',            'object',     'out_of_stock', null, null, null, '[]',            null, null),
  ('f1000016-0000-0000-0000-000000000000', 'dismiss_item',     'consumable', 'low_stock', 1,  3, null, '["Aldi"]',             null, null),
  ('f1000017-0000-0000-0000-000000000000', 'cascade_item',     'object',     'stored',    null, null, null, '[]',               null, null),
  ('f1000018-0000-0000-0000-000000000000', 'notag_item',       'consumable', 'low_stock', 0,  1, null, '[]',                   null, null),
  ('f1000019-0000-0000-0000-000000000000', 'multi_tag_item',   'consumable', 'low_stock', 1,  3, null, '["Rewe","Amazon"]',    null, null),
  ('f1000020-0000-0000-0000-000000000000', 'delete_item',      'consumable', 'low_stock', 1,  3, null, '["Rewe"]',             null, null);

-- ── Sprint02: shopping tasks ──────────────────────────────────────────────────
-- open_task:     open task for low_stock_item (used in duplicate rejection + not-duplicated tests)
-- milk_task:     open task for restock_milk
-- low_restock_task: open task for low_restock_item
-- cable_task:    open task for cable
-- dismiss_task:  open task for dismiss_item
-- cascade_task:  open task for cascade_item (deleted with item)
-- notag_task:    open task for notag_item (by_source 'Other' group)
-- multi_task:    open task for multi_tag_item (by_source multi-group)
-- delete_task:   open task for delete_item (to be explicitly deleted)
-- done_task:     done task for stored_item (for status filter test)
-- dismissed_task: dismissed task for stored_item (for status filter test)

INSERT INTO storagetracker.shopping_tasks
  (id, item_id, status, source_tags, notes)
VALUES
  ('f2000001-0000-0000-0000-000000000000', 'f1000011-0000-0000-0000-000000000000', 'open',      '["DM"]',           null),
  ('f2000002-0000-0000-0000-000000000000', 'f1000013-0000-0000-0000-000000000000', 'open',      '["Rewe"]',         null),
  ('f2000003-0000-0000-0000-000000000000', 'f1000014-0000-0000-0000-000000000000', 'open',      '[]',               null),
  ('f2000004-0000-0000-0000-000000000000', 'f1000015-0000-0000-0000-000000000000', 'open',      '[]',               null),
  ('f2000005-0000-0000-0000-000000000000', 'f1000016-0000-0000-0000-000000000000', 'open',      '["Aldi"]',         null),
  ('f2000006-0000-0000-0000-000000000000', 'f1000017-0000-0000-0000-000000000000', 'open',      '[]',               null),
  ('f2000007-0000-0000-0000-000000000000', 'f1000018-0000-0000-0000-000000000000', 'open',      '[]',               null),
  ('f2000008-0000-0000-0000-000000000000', 'f1000019-0000-0000-0000-000000000000', 'open',      '["Rewe","Amazon"]', null),
  ('f2000009-0000-0000-0000-000000000000', 'f1000020-0000-0000-0000-000000000000', 'open',      '["Rewe"]',         null);

-- done and dismissed tasks use the Sprint01 coffee item (f1000002, state=stored — no open task conflict)
INSERT INTO storagetracker.shopping_tasks
  (id, item_id, status, source_tags, notes, completed_at)
VALUES
  ('f2000010-0000-0000-0000-000000000000', 'f1000002-0000-0000-0000-000000000000', 'done',      '["Rewe","Aldi"]',  null, now()),
  ('f2000011-0000-0000-0000-000000000000', 'f1000006-0000-0000-0000-000000000000', 'dismissed', '[]',               null, now());
