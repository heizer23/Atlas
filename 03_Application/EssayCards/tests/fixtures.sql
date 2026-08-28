-- EssayCards Sprint01 — test fixtures
--
-- ID prefixes are valid-hex and readable:
--   ea = essay, ec = essay section (essaycards), fc = flashcard
--
-- fix-id traceability (referenced by name in Sprint01_Core/10_test_spec.md):
--   fc-origins-1 -> fc000001-...-000000000001 (essay A / section "origins", due, never reviewed)
--   fc-origins-2 -> fc000002-...-000000000002 (essay A / section "origins", due, never reviewed)
--   fc-origins-3 -> fc000003-...-000000000003 (essay A / section "structure", due, last reviewed 60m ago)
--   fc-not-due   -> fc000004-...-000000000004 (essay A / section "structure", NOT due — 1h in the future)
--   fc-b-1       -> fc000005-...-000000000005 (essay B, due — second essay for system-wide queue test)
--   fc-c-1       -> fc000006-...-000000000006 (essay C, NOT due — essay with nothing due)

-- ── Essays ────────────────────────────────────────────────────────────────────
INSERT INTO essaycards.essays (id, title, slug, created_at, updated_at) VALUES
  ('ea000001-0000-0000-0000-000000000001', 'The Origins of Long-Form Formats', 'origins-of-long-form-formats', now() - interval '3 hours', now() - interval '3 hours'),
  ('ea000002-0000-0000-0000-000000000002', 'Essay B',                          'essay-b',                      now() - interval '2 hours', now() - interval '2 hours'),
  ('ea000003-0000-0000-0000-000000000003', 'Essay C (nothing due)',            'essay-c',                      now() - interval '1 hour',  now() - interval '1 hour');

-- ── Sections ─────────────────────────────────────────────────────────────────
INSERT INTO essaycards.essay_sections (id, essay_id, order_index, heading, anchor_slug, body_markdown) VALUES
  ('ec000001-0000-0000-0000-000000000001', 'ea000001-0000-0000-0000-000000000001', 0, 'Origins',   'origins',   'The essay begins with the origins of the format.'),
  ('ec000002-0000-0000-0000-000000000002', 'ea000001-0000-0000-0000-000000000001', 1, 'Structure', 'structure', 'This section discusses structure.'),
  ('ec000003-0000-0000-0000-000000000003', 'ea000002-0000-0000-0000-000000000002', 0, 'B Section', 'b-section', 'Essay B content.'),
  ('ec000004-0000-0000-0000-000000000004', 'ea000003-0000-0000-0000-000000000003', 0, 'C Section', 'c-section', 'Essay C content.');

-- ── Flashcards ───────────────────────────────────────────────────────────────
INSERT INTO essaycards.flashcards (id, essay_id, section_id, card_key, question, answer) VALUES
  ('fc000001-0000-0000-0000-000000000001', 'ea000001-0000-0000-0000-000000000001', 'ec000001-0000-0000-0000-000000000001', 'fc-origins-1', 'Who coined the term?',         'Nobody knows for certain.'),
  ('fc000002-0000-0000-0000-000000000002', 'ea000001-0000-0000-0000-000000000001', 'ec000001-0000-0000-0000-000000000001', 'fc-origins-2', 'When did the format emerge?',  'In the early modern period.'),
  ('fc000003-0000-0000-0000-000000000003', 'ea000001-0000-0000-0000-000000000001', 'ec000002-0000-0000-0000-000000000002', 'fc-origins-3', 'What defines structure here?', 'A clear beginning, middle, and end.'),
  ('fc000004-0000-0000-0000-000000000004', 'ea000001-0000-0000-0000-000000000001', 'ec000002-0000-0000-0000-000000000002', 'fc-not-due',   'Why is this card not due yet?', 'Because it was reviewed recently.'),
  ('fc000005-0000-0000-0000-000000000005', 'ea000002-0000-0000-0000-000000000002', 'ec000003-0000-0000-0000-000000000003', 'fc-b-1',       'Essay B question?',            'Essay B answer.'),
  ('fc000006-0000-0000-0000-000000000006', 'ea000003-0000-0000-0000-000000000003', 'ec000004-0000-0000-0000-000000000004', 'fc-c-1',       'Essay C question?',            'Essay C answer.');

-- ── Review state ─────────────────────────────────────────────────────────────
INSERT INTO essaycards.flashcard_review_state (flashcard_id, last_reviewed_at, next_due_at) VALUES
  ('fc000001-0000-0000-0000-000000000001', null,                            now() - interval '10 minutes'),
  ('fc000002-0000-0000-0000-000000000002', null,                            now() - interval '5 minutes'),
  ('fc000003-0000-0000-0000-000000000003', now() - interval '60 minutes',   now() - interval '1 minute'),
  ('fc000004-0000-0000-0000-000000000004', null,                            now() + interval '1 hour'),
  ('fc000005-0000-0000-0000-000000000005', null,                            now() - interval '2 minutes'),
  ('fc000006-0000-0000-0000-000000000006', null,                            now() + interval '1 hour');
