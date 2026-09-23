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

-- ── Queue-stats horizons (GET /flashcards/stats) ─────────────────────────────
-- Essay D exists only to exercise the horizon bands of GET /flashcards/stats.
-- Every card here is future-dated, so none appear in the /due queue and none
-- disturb the prior /due test expectations.
--   fc-stats-5min   -> now + 5 minutes  -> within_10_min band
--   fc-stats-3day   -> now + 3 days     -> within_7_days band
--   fc-stats-14day  -> now + 14 days    -> within_30_days band
--   fc-stats-60day  -> now + 60 days    -> within_90_days band  (Sprint05a split)
--   fc-stats-120day -> now + 120 days   -> beyond_90_days band  (Sprint05a split)
-- Combined with essays A/B (4 cards due now, 2 cards ~1h out) and Essay E's 9
-- eligible cards the system-wide forecast is: due_now=13, within_10_min=1,
-- within_1_day=2, within_7_days=1, within_30_days=1, within_90_days=1,
-- beyond_90_days=1 (sum 20).
INSERT INTO essaycards.essays (id, title, slug, created_at, updated_at) VALUES
  ('ea000004-0000-0000-0000-000000000004', 'Essay D (stats horizons)', 'essay-d', now() - interval '30 minutes', now() - interval '30 minutes');

INSERT INTO essaycards.essay_sections (id, essay_id, order_index, heading, anchor_slug, body_markdown) VALUES
  ('ec000005-0000-0000-0000-000000000005', 'ea000004-0000-0000-0000-000000000004', 0, 'D Section', 'd-section', 'Essay D content.');

INSERT INTO essaycards.flashcards (id, essay_id, section_id, card_key, question, answer) VALUES
  ('fc000007-0000-0000-0000-000000000007', 'ea000004-0000-0000-0000-000000000004', 'ec000005-0000-0000-0000-000000000005', 'fc-stats-5min',   'D q1', 'D a1'),
  ('fc000008-0000-0000-0000-000000000008', 'ea000004-0000-0000-0000-000000000004', 'ec000005-0000-0000-0000-000000000005', 'fc-stats-3day',   'D q2', 'D a2'),
  ('fc000009-0000-0000-0000-000000000009', 'ea000004-0000-0000-0000-000000000004', 'ec000005-0000-0000-0000-000000000005', 'fc-stats-14day',  'D q3', 'D a3'),
  ('fc000010-0000-0000-0000-000000000010', 'ea000004-0000-0000-0000-000000000004', 'ec000005-0000-0000-0000-000000000005', 'fc-stats-60day',  'D q4', 'D a4'),
  ('fc000020-0000-0000-0000-000000000020', 'ea000004-0000-0000-0000-000000000004', 'ec000005-0000-0000-0000-000000000005', 'fc-stats-120day', 'D q5', 'D a5');

INSERT INTO essaycards.flashcard_review_state (flashcard_id, last_reviewed_at, next_due_at) VALUES
  ('fc000007-0000-0000-0000-000000000007', null, now() + interval '5 minutes'),
  ('fc000008-0000-0000-0000-000000000008', null, now() + interval '3 days'),
  ('fc000009-0000-0000-0000-000000000009', null, now() + interval '14 days'),
  ('fc000010-0000-0000-0000-000000000010', null, now() + interval '60 days'),
  ('fc000020-0000-0000-0000-000000000020', null, now() + interval '120 days');

-- ── Review-queue ordering (Sprint05_ReviewQueueOrdering) ─────────────────────
-- Essay E exercises the two-category ordering of GET /flashcards/due:
--   RECENT  = last_reviewed_at >= now() - 24h  AND next_due_at <= now()
--             -> sorted by next_due_at DESC (closest to now first)
--   BACKLOG = every other eligible card
--             -> sorted by (next_due_at - last_reviewed_at) DESC (interval
--                the card is scheduled across; never-reviewed = interval 0 = last)
-- All nine cards below are eligible (next_due_at <= now()). Expected order:
--   RECENT : fc-e-recent-23h, fc-e-recent-near, fc-e-recent-far
--   BACKLOG: fc-e-back-90d, fc-e-back-30d, fc-e-back-25h, fc-e-back-1d,
--            fc-e-back-20min, fc-e-new
-- fc-e-recent-23h vs fc-e-back-25h isolate the ROLLING 24h window: both came
-- due ~90s ago, only last_reviewed_at (23h vs 25h ago) decides the category —
-- there is no calendar-day / midnight component.
-- fc-e-back-90d (1h overdue) precedes fc-e-back-1d (1d overdue) precedes
-- fc-e-back-20min (~3d overdue): interval DESC, the reverse of overdue DESC.
INSERT INTO essaycards.essays (id, title, slug, created_at, updated_at) VALUES
  ('ea000005-0000-0000-0000-000000000005', 'Essay E (review-queue ordering)', 'essay-e', now() - interval '120 days', now() - interval '120 days');

INSERT INTO essaycards.essay_sections (id, essay_id, order_index, heading, anchor_slug, body_markdown) VALUES
  ('ec000006-0000-0000-0000-000000000006', 'ea000005-0000-0000-0000-000000000005', 0, 'E Section', 'e-section', 'Essay E content.');

INSERT INTO essaycards.flashcards (id, essay_id, section_id, card_key, question, answer) VALUES
  ('fc000011-0000-0000-0000-000000000011', 'ea000005-0000-0000-0000-000000000005', 'ec000006-0000-0000-0000-000000000006', 'fc-e-recent-near', 'E q1', 'E a1'),
  ('fc000012-0000-0000-0000-000000000012', 'ea000005-0000-0000-0000-000000000005', 'ec000006-0000-0000-0000-000000000006', 'fc-e-recent-far',  'E q2', 'E a2'),
  ('fc000013-0000-0000-0000-000000000013', 'ea000005-0000-0000-0000-000000000005', 'ec000006-0000-0000-0000-000000000006', 'fc-e-recent-23h',  'E q3', 'E a3'),
  ('fc000014-0000-0000-0000-000000000014', 'ea000005-0000-0000-0000-000000000005', 'ec000006-0000-0000-0000-000000000006', 'fc-e-back-25h',    'E q4', 'E a4'),
  ('fc000015-0000-0000-0000-000000000015', 'ea000005-0000-0000-0000-000000000005', 'ec000006-0000-0000-0000-000000000006', 'fc-e-back-90d',    'E q5', 'E a5'),
  ('fc000016-0000-0000-0000-000000000016', 'ea000005-0000-0000-0000-000000000005', 'ec000006-0000-0000-0000-000000000006', 'fc-e-back-30d',    'E q6', 'E a6'),
  ('fc000017-0000-0000-0000-000000000017', 'ea000005-0000-0000-0000-000000000005', 'ec000006-0000-0000-0000-000000000006', 'fc-e-back-1d',     'E q7', 'E a7'),
  ('fc000018-0000-0000-0000-000000000018', 'ea000005-0000-0000-0000-000000000005', 'ec000006-0000-0000-0000-000000000006', 'fc-e-back-20min',  'E q8', 'E a8'),
  ('fc000019-0000-0000-0000-000000000019', 'ea000005-0000-0000-0000-000000000005', 'ec000006-0000-0000-0000-000000000006', 'fc-e-new',         'E q9', 'E a9');

INSERT INTO essaycards.flashcard_review_state (flashcard_id, last_reviewed_at, next_due_at) VALUES
  ('fc000011-0000-0000-0000-000000000011', now() - interval '2 hours',                 now() - interval '2 minutes'),
  ('fc000012-0000-0000-0000-000000000012', now() - interval '3 hours',                 now() - interval '20 minutes'),
  ('fc000013-0000-0000-0000-000000000013', now() - interval '23 hours',                now() - interval '90 seconds'),
  ('fc000014-0000-0000-0000-000000000014', now() - interval '25 hours',                now() - interval '90 seconds'),
  ('fc000015-0000-0000-0000-000000000015', now() - interval '90 days' - interval '1 hour',  now() - interval '1 hour'),
  ('fc000016-0000-0000-0000-000000000016', now() - interval '32 days',                 now() - interval '2 days'),
  ('fc000017-0000-0000-0000-000000000017', now() - interval '2 days',                  now() - interval '1 day'),
  ('fc000018-0000-0000-0000-000000000018', now() - interval '3 days',                  now() - interval '3 days' + interval '20 minutes'),
  ('fc000019-0000-0000-0000-000000000019', null,                                       now() - interval '5 minutes');

-- Materialise review_interval for every fixture review-state row, matching what
-- POST /flashcards/{id}/review would have written: (next_due_at - last_reviewed_at)
-- for a reviewed card, interval '0' for a never-reviewed one. Keeps the fixture
-- world consistent with the review_interval column (schema.sql) so BACKLOG
-- ordering and the new/learning/established classification behave as in prod.
UPDATE essaycards.flashcard_review_state
SET review_interval = GREATEST(interval '0', next_due_at - last_reviewed_at)
WHERE last_reviewed_at IS NOT NULL;

-- ── Section examinations ─────────────────────────────────────────────────────
-- Two prior sittings for essay A / section "origins" (se-origins-1 older,
-- se-origins-2 newer — export's last_examination and the history endpoint's
-- "most recent first" ordering should both surface se-origins-2). Essay A /
-- section "structure" has zero examinations on purpose, to exercise the
-- never-examined / empty-history / null last_examination paths.
INSERT INTO essaycards.section_examinations
  (id, essay_id, section_id, section_version_at, examined_at, question, answer_transcript, score, feedback) VALUES
  ('5e000001-0000-0000-0000-000000000001', 'ea000001-0000-0000-0000-000000000001', 'ec000001-0000-0000-0000-000000000001',
    (select updated_at from essaycards.essay_sections where id = 'ec000001-0000-0000-0000-000000000001'),
    now() - interval '30 days', 'Explain the origins of the format.', 'It emerged gradually from earlier forms.', 3, 'Good enough for now.'),
  ('5e000002-0000-0000-0000-000000000002', 'ea000001-0000-0000-0000-000000000001', 'ec000001-0000-0000-0000-000000000001',
    (select updated_at from essaycards.essay_sections where id = 'ec000001-0000-0000-0000-000000000001'),
    now() - interval '2 days', 'Explain the origins again, in more depth.', 'A more developed account connecting it to related material.', 4, 'Clear improvement since last time.');

-- ── Images (Sprint03_Images) ─────────────────────────────────────────────────
-- fix-img-alpha: the OLDER row. No matching file is placed in the (tmp) images
--   directory by tests, so GET /images/fix-img-alpha exercises the
--   row-present / file-missing -> 404 path.
-- fix-img-beta:  the NEWER row. GET /api/essaycards/images must list
--   fix-img-beta before fix-img-alpha (created_at desc).
INSERT INTO essaycards.images
  (slug, stored_filename, content_type, byte_size, width, height, source_sha256, source_filename, created_at) VALUES
  ('fix-img-alpha', 'fix-img-alpha.png', 'image/png',  1024, 100,  80,
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa01', 'alpha.png', now() - interval '2 hours'),
  ('fix-img-beta',  'fix-img-beta.jpg',  'image/jpeg', 2048, 200, 150,
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb02', 'beta.jpg',  now() - interval '1 hour');

-- ── Nuggets (Sprint09_Nuggets) ────────────────────────────────────────────────
--
-- fix-nugget-cogito    (ee000001): referenced by TWO fixture sections across
--                       TWO different essays (essay F / section F1, essay G /
--                       section G1) — exercises reuse-without-duplication and
--                       GET /nuggets/{id}/sections returning two rows. Also
--                       has one linked fixture flashcard (fc000021).
-- fix-nugget-wax       (ee000002): its own body_markdown references
--                       [[nugget:fix-nugget-cogito]] — exercises the
--                       authoring-package's connected_nuggets resolution.
--                       Not referenced by any fixture section itself.
-- fix-nugget-adequacy  (ee000003): referenced ONLY by essay F's
--                       main_spine_markdown, never by any of essay F's
--                       sections — exercises main_spine_nuggets resolving a
--                       main-spine-only reference (11_design_review.md Hard
--                       Rule Violation 1 / Minimal Change Set item 2).
-- fix-nugget-MixedCase (ee000004): nugget_key contains an uppercase letter,
--                       referenced by matching case in section F1's
--                       body_markdown — exercises extract_nugget_keys'
--                       character-class fix (Minimal Change Set item 1).
INSERT INTO essaycards.nuggets (id, nugget_key, title, body_markdown, created_at, updated_at) VALUES
  ('ee000001-0000-0000-0000-000000000001', 'fix-nugget-cogito', 'Cogito',
    'The cogito is not inferred from a syllogism; it is directly, immediately evident to the thinker.',
    now() - interval '5 days', now() - interval '5 days'),
  ('ee000002-0000-0000-0000-000000000002', 'fix-nugget-wax', 'Wax and the Intellect',
    'The wax argument builds on [[nugget:fix-nugget-cogito]] to show that the intellect, not the senses, perceives the wax''s true nature.',
    now() - interval '4 days', now() - interval '4 days'),
  ('ee000003-0000-0000-0000-000000000003', 'fix-nugget-adequacy', 'Adequacy',
    'An adequate idea represents its object fully and without confusion.',
    now() - interval '3 days', now() - interval '3 days'),
  ('ee000004-0000-0000-0000-000000000004', 'fix-nugget-MixedCase', 'Mixed Case Nugget',
    'Demonstrates that a nugget_key containing an uppercase letter is referenceable and resolved case-sensitively.',
    now() - interval '2 days', now() - interval '2 days');

-- ── Essays F/G (nugget-referencing fixture content) ──────────────────────────
--
-- Essay F's main_spine_markdown references fix-nugget-adequacy (main-spine-
-- only — not referenced by section F1). Section F1 references
-- fix-nugget-cogito and fix-nugget-MixedCase. Essay G / section G1 also
-- references fix-nugget-cogito, so GET /nuggets/{cogito}/sections returns two
-- rows across these two essays.
INSERT INTO essaycards.essays (id, title, slug, main_spine_markdown, created_at, updated_at) VALUES
  ('ea000006-0000-0000-0000-000000000006', 'Essay F (nuggets)', 'essay-f-nuggets',
    'The spine connects the ideas: [[nugget:fix-nugget-adequacy]] grounds the rest.',
    now() - interval '4 days', now() - interval '4 days'),
  ('ea000007-0000-0000-0000-000000000007', 'Essay G (nuggets)', 'essay-g-nuggets',
    '', now() - interval '4 days', now() - interval '4 days');

INSERT INTO essaycards.essay_sections (id, essay_id, order_index, heading, anchor_slug, body_markdown) VALUES
  ('ec000007-0000-0000-0000-000000000007', 'ea000006-0000-0000-0000-000000000006', 0, 'F Nuggets Section', 'f-nuggets',
    'This section references [[nugget:fix-nugget-cogito]] and [[nugget:fix-nugget-MixedCase]].'),
  ('ec000008-0000-0000-0000-000000000008', 'ea000007-0000-0000-0000-000000000007', 0, 'G Nuggets Section', 'g-nuggets',
    'This section also references [[nugget:fix-nugget-cogito]].');

INSERT INTO essaycards.section_nuggets (section_id, nugget_id) VALUES
  ('ec000007-0000-0000-0000-000000000007', 'ee000001-0000-0000-0000-000000000001'),  -- F1 -> cogito
  ('ec000007-0000-0000-0000-000000000007', 'ee000004-0000-0000-0000-000000000004'),  -- F1 -> MixedCase
  ('ec000008-0000-0000-0000-000000000008', 'ee000001-0000-0000-0000-000000000001');  -- G1 -> cogito

-- fc-nugget-linked: nugget_id set to fix-nugget-cogito. Exercises
-- GET /nuggets/{id}/flashcards, the due-row/export/questions nugget_id
-- field, and the exploration-package nugget-sourced context branch.
-- fc-nugget-unlinked: nugget_id null (legacy) in the SAME essay, for the
-- "one linked + one unlinked card in the same essay" question-overview and
-- due-row scenarios; also the target of the "set a valid nugget_id" upsert
-- scenario.
INSERT INTO essaycards.flashcards (id, essay_id, section_id, card_key, question, answer, nugget_id) VALUES
  ('fc000021-0000-0000-0000-000000000021', 'ea000006-0000-0000-0000-000000000006', 'ec000007-0000-0000-0000-000000000007',
    'fc-nugget-linked', 'What is directly evident to the thinker?', 'The cogito.', 'ee000001-0000-0000-0000-000000000001'),
  ('fc000022-0000-0000-0000-000000000022', 'ea000006-0000-0000-0000-000000000006', 'ec000007-0000-0000-0000-000000000007',
    'fc-nugget-unlinked', 'What does the wax argument show?', 'That the intellect, not the senses, perceives.', null);

INSERT INTO essaycards.flashcard_review_state (flashcard_id, last_reviewed_at, next_due_at) VALUES
  ('fc000021-0000-0000-0000-000000000021', null, now() - interval '10 minutes'),
  ('fc000022-0000-0000-0000-000000000022', null, now() - interval '10 minutes');
