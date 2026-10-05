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
  (id, essay_id, section_id, section_version_at, examined_at, question, answer_transcript, score, passed, feedback) VALUES
  ('5e000001-0000-0000-0000-000000000001', 'ea000001-0000-0000-0000-000000000001', 'ec000001-0000-0000-0000-000000000001',
    (select updated_at from essaycards.essay_sections where id = 'ec000001-0000-0000-0000-000000000001'),
    now() - interval '30 days', 'Explain the origins of the format.', 'It emerged gradually from earlier forms.', 3, false, 'Good enough for now.'),
  ('5e000002-0000-0000-0000-000000000002', 'ea000001-0000-0000-0000-000000000001', 'ec000001-0000-0000-0000-000000000001',
    (select updated_at from essaycards.essay_sections where id = 'ec000001-0000-0000-0000-000000000001'),
    now() - interval '2 days', 'Explain the origins again, in more depth.', 'A more developed account connecting it to related material.', 4, false, 'Clear improvement since last time.');

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

-- ── Sprint12_FSRSAndUXOverhaul — FSRS is the sole scheduler ─────────────────
--
-- schema.sql drops flashcard_review_state's scheduler/scheduler_assigned_at/
-- scheduler_assignment_reason/experiment_version columns and
-- review_events.scheduler entirely (the Sprint10 A/B experiment is retired).
-- Every flashcard_review_state/review_events row below is written WITHOUT
-- those columns. Card ids/keys below still read "classic"/"fsrs" in a few
-- places for historical traceability only (fix-classic-established,
-- fix-mix-recent-classic, etc.) — these are now just labels; every card is
-- reviewed through the single FSRS scheduler regardless of what its key says.
--
-- Essay H: dedicated fixture set for FSRS state / due-queue-ordering-is-
-- scheduler-agnostic coverage. Every card here is placed carefully with
-- respect to GET /flashcards/due's UNSCOPED (system-wide REVIEW) query,
-- which has no essay filter: an unscoped-visible card must be both due
-- (next_due_at <= now()) AND established (review_interval >= 24h). The
-- pre-existing test_due_no_params_returns_review_queue asserts an EXACT ids
-- list for that unscoped query, so no card added here may satisfy both
-- conditions at once — established cards (fix-fsrs-established,
-- fix-classic-established) are kept NOT due (next_due_at in the future;
-- POST /review does not require due-ness), and every card that IS due here
-- is kept sub-24h (learning), so none can ever leak into that exact-match
-- assertion.
INSERT INTO essaycards.essays (id, title, slug, created_at, updated_at) VALUES
  ('ea000008-0000-0000-0000-000000000008', 'Essay H (Sprint10 scheduler fixtures)', 'essay-h-scheduler', now() - interval '10 days', now() - interval '10 days');

INSERT INTO essaycards.essay_sections (id, essay_id, order_index, heading, anchor_slug, body_markdown) VALUES
  ('ec000009-0000-0000-0000-000000000009', 'ea000008-0000-0000-0000-000000000008', 0, 'H Section', 'h-section', 'Essay H content.');

INSERT INTO essaycards.flashcards (id, essay_id, section_id, card_key, question, answer) VALUES
  ('fc000023-0000-0000-0000-000000000023', 'ea000008-0000-0000-0000-000000000008', 'ec000009-0000-0000-0000-000000000009', 'fix-fsrs-established',   'H q1 (fsrs established)',      'H a1'),
  ('fc000024-0000-0000-0000-000000000024', 'ea000008-0000-0000-0000-000000000008', 'ec000009-0000-0000-0000-000000000009', 'fix-fsrs-fresh',         'H q2 (fsrs, no prior state)',  'H a2'),
  ('fc000025-0000-0000-0000-000000000025', 'ea000008-0000-0000-0000-000000000008', 'ec000009-0000-0000-0000-000000000009', 'fix-classic-established','H q3 (classic established)',   'H a3'),
  ('fc000026-0000-0000-0000-000000000026', 'ea000008-0000-0000-0000-000000000008', 'ec000009-0000-0000-0000-000000000009', 'fix-mix-recent-classic', 'H q4 (recent, classic)',       'H a4'),
  ('fc000027-0000-0000-0000-000000000027', 'ea000008-0000-0000-0000-000000000008', 'ec000009-0000-0000-0000-000000000009', 'fix-mix-recent-fsrs',    'H q5 (recent, fsrs)',          'H a5'),
  ('fc000028-0000-0000-0000-000000000028', 'ea000008-0000-0000-0000-000000000008', 'ec000009-0000-0000-0000-000000000009', 'fix-mix-backlog-classic','H q6 (backlog, classic)',      'H a6'),
  ('fc000029-0000-0000-0000-000000000029', 'ea000008-0000-0000-0000-000000000008', 'ec000009-0000-0000-0000-000000000009', 'fix-mix-backlog-fsrs',   'H q7 (backlog, fsrs)',         'H a7'),
  ('fc000030-0000-0000-0000-000000000030', 'ea000008-0000-0000-0000-000000000008', 'ec000009-0000-0000-0000-000000000009', 'fix-legacy-no-fsrs-state', 'H q8 (reviewed, no fsrs_card_state row)', 'H a8');

-- fix-fsrs-established: already reviewed, established (review_interval
-- ~10d1h >= 24h), NOT currently due (kept out of every /due query — see
-- note above). Has a pre-existing fsrs_card_state row in the library's
-- Review state, simulating state surviving an application restart (state is
-- read fresh from the DB on every request, never cached in-process) —
-- exercises reload/relearning.
INSERT INTO essaycards.flashcard_review_state
    (flashcard_id, last_reviewed_at, next_due_at, review_interval) VALUES
  ('fc000023-0000-0000-0000-000000000023',
   now() - interval '10 days', now() + interval '1 hour', interval '10 days 1 hour');

INSERT INTO essaycards.fsrs_card_state
    (flashcard_id, stability, difficulty, fsrs_state, step, last_review_at, raw_state) VALUES
  ('fc000023-0000-0000-0000-000000000023', 15.0, 4.5, 2, null, now() - interval '10 days',
   jsonb_build_object(
     'card_id', 1,
     'state', 2,
     'step', null,
     'stability', 15.0,
     'difficulty', 4.5,
     'due', now() + interval '1 hour',
     'last_review', now() - interval '10 days'
   ));

-- fix-fsrs-fresh: never reviewed, NO fsrs_card_state row yet — exercises
-- FSRSScheduler.review's fresh fsrs.Card() path on first-ever review. Not
-- currently due (see note above; POST /review doesn't require due-ness).
INSERT INTO essaycards.flashcard_review_state (flashcard_id, last_reviewed_at, next_due_at) VALUES
  ('fc000024-0000-0000-0000-000000000024', null, now() + interval '1 hour');

-- fix-classic-established: already established (review_interval ~40d1h >=
-- 24h), NOT currently due — a dedicated mature card target for generic
-- "review an established card via the endpoint" coverage (POST /review
-- doesn't require due-ness).
INSERT INTO essaycards.flashcard_review_state
    (flashcard_id, last_reviewed_at, next_due_at, review_interval) VALUES
  ('fc000025-0000-0000-0000-000000000025',
   now() - interval '40 days', now() + interval '1 hour', interval '40 days 1 hour');

-- fix-mix-recent-classic / fix-mix-recent-fsrs / fix-mix-backlog-classic /
-- fix-mix-backlog-fsrs: four cards interleaved across BOTH due-queue
-- ordering categories, all kept sub-24h (learning) so none can ever appear
-- in the unscoped/system-wide REVIEW query (which requires review_interval
-- >= 24h) — every assertion against this set uses a FOCUS query scoped to
-- essay_id=essay-h-scheduler. (Names predate Sprint12's single-scheduler
-- model — see module note above; they are ordinary cards now.)
--   RECENT  (last_reviewed_at within 24h), sorted next_due_at DESC:
--     fix-mix-recent-classic (due 5m ago)  before
--     fix-mix-recent-fsrs    (due 20m ago)
--   BACKLOG (last_reviewed_at more than 24h ago), sorted review_interval DESC:
--     fix-mix-backlog-classic (12h interval) before
--     fix-mix-backlog-fsrs    (6h interval)
INSERT INTO essaycards.flashcard_review_state
    (flashcard_id, last_reviewed_at, next_due_at, review_interval) VALUES
  ('fc000026-0000-0000-0000-000000000026',
   now() - interval '2 hours', now() - interval '5 minutes', interval '115 minutes'),
  ('fc000027-0000-0000-0000-000000000027',
   now() - interval '3 hours', now() - interval '20 minutes', interval '160 minutes'),
  ('fc000028-0000-0000-0000-000000000028',
   now() - interval '2 days', now() - interval '1 day 12 hours', interval '12 hours'),
  ('fc000029-0000-0000-0000-000000000029',
   now() - interval '3 days', now() - interval '2 days 18 hours', interval '6 hours');

-- fix-legacy-no-fsrs-state (Sprint12_FSRSAndUXOverhaul): reviewed (real
-- history) but deliberately given NO fsrs_card_state row — the direct
-- target of backend/migrate_fsrs_state.py's legacy backfill. Every test run
-- re-fires backend.main's startup handler (see tests/conftest.py's `client`
-- fixture), so by the time any test queries this card the migration has
-- already run once against it and it should already carry a synthesized
-- fsrs_card_state row. Kept established and NOT due so it can never affect
-- any /due assertion.
INSERT INTO essaycards.flashcard_review_state
    (flashcard_id, last_reviewed_at, next_due_at, review_interval) VALUES
  ('fc000030-0000-0000-0000-000000000030',
   now() - interval '5 days', now() + interval '2 hours', interval '5 days 2 hours');

-- ── Learning progress (Sprint12_FSRSAndUXOverhaul) ──────────────────────────
--
-- Essay I: sections but zero flashcards, with BOTH sections having a passing
-- guided examination — proves milestones 1/2 (card-based) stay false for a
-- zero-card essay (00_draft.md "essays without active cards must not
-- automatically satisfy the card milestones") while milestone 3 (exam-based,
-- no card dependency) can still be true, giving learning_level 1, not 0 and
-- not vacuously 4.
INSERT INTO essaycards.essays (id, title, slug, created_at, updated_at) VALUES
  ('ea000009-0000-0000-0000-000000000009', 'Essay I (zero cards, guided-passed)', 'essay-i-zero-cards', now() - interval '6 days', now() - interval '6 days');

INSERT INTO essaycards.essay_sections (id, essay_id, order_index, heading, anchor_slug, body_markdown) VALUES
  ('ec000010-0000-0000-0000-000000000010', 'ea000009-0000-0000-0000-000000000009', 0, 'I Section 1', 'i-section-1', 'Essay I section 1 content.'),
  ('ec000011-0000-0000-0000-000000000011', 'ea000009-0000-0000-0000-000000000009', 1, 'I Section 2', 'i-section-2', 'Essay I section 2 content.');

INSERT INTO essaycards.section_examinations
  (id, essay_id, section_id, section_version_at, examined_at, question, answer_transcript, score, passed, exam_type) VALUES
  ('5e000003-0000-0000-0000-000000000003', 'ea000009-0000-0000-0000-000000000009', 'ec000010-0000-0000-0000-000000000010',
    (select updated_at from essaycards.essay_sections where id = 'ec000010-0000-0000-0000-000000000010'),
    now() - interval '5 days', 'Explain I.1', 'Good account.', 5, true, 'guided'),
  ('5e000004-0000-0000-0000-000000000004', 'ea000009-0000-0000-0000-000000000009', 'ec000011-0000-0000-0000-000000000011',
    (select updated_at from essaycards.essay_sections where id = 'ec000011-0000-0000-0000-000000000011'),
    now() - interval '4 days', 'Explain I.2', 'Good account.', 4, false, 'guided');

-- Essay J: two sections, each with a GUIDED and an UNGUIDED examination on
-- record — one section's guided exam scores below the pass threshold while
-- every other guided/unguided exam passes. Exercises:
--   - guided-passed requires EVERY section to individually meet the
--     threshold (one section below 3 keeps milestone_guided_passed false
--     even though the other section passes)
--   - guided/unguided independence (every section's unguided exam passes,
--     so milestone_unguided_passed is true while milestone_guided_passed is
--     false)
INSERT INTO essaycards.essays (id, title, slug, created_at, updated_at) VALUES
  ('ea00000a-0000-0000-0000-00000000000a', 'Essay J (mixed guided pass/fail, unguided passed)', 'essay-j-mixed-exam-types', now() - interval '6 days', now() - interval '6 days');

INSERT INTO essaycards.essay_sections (id, essay_id, order_index, heading, anchor_slug, body_markdown) VALUES
  ('ec00000a-0000-0000-0000-00000000000a', 'ea00000a-0000-0000-0000-00000000000a', 0, 'J Section 1', 'j-section-1', 'Essay J section 1 content.'),
  ('ec00000b-0000-0000-0000-00000000000b', 'ea00000a-0000-0000-0000-00000000000a', 1, 'J Section 2', 'j-section-2', 'Essay J section 2 content.');

INSERT INTO essaycards.section_examinations
  (id, essay_id, section_id, section_version_at, examined_at, question, answer_transcript, score, passed, exam_type) VALUES
  -- section 1: guided passes (score 4), unguided passes (score 3)
  ('5e000005-0000-0000-0000-000000000005', 'ea00000a-0000-0000-0000-00000000000a', 'ec00000a-0000-0000-0000-00000000000a',
    (select updated_at from essaycards.essay_sections where id = 'ec00000a-0000-0000-0000-00000000000a'),
    now() - interval '5 days', 'Explain J.1 guided', 'Good account.', 4, false, 'guided'),
  ('5e000006-0000-0000-0000-000000000006', 'ea00000a-0000-0000-0000-00000000000a', 'ec00000a-0000-0000-0000-00000000000a',
    (select updated_at from essaycards.essay_sections where id = 'ec00000a-0000-0000-0000-00000000000a'),
    now() - interval '3 days', 'Explain J.1 unguided', 'Good account.', 3, false, 'unguided'),
  -- section 2: guided FAILS (score 2, below threshold), unguided passes (score 5)
  ('5e000007-0000-0000-0000-000000000007', 'ea00000a-0000-0000-0000-00000000000a', 'ec00000b-0000-0000-0000-00000000000b',
    (select updated_at from essaycards.essay_sections where id = 'ec00000b-0000-0000-0000-00000000000b'),
    now() - interval '5 days', 'Explain J.2 guided', 'Weak account.', 2, false, 'guided'),
  ('5e000008-0000-0000-0000-000000000008', 'ea00000a-0000-0000-0000-00000000000a', 'ec00000b-0000-0000-0000-00000000000b',
    (select updated_at from essaycards.essay_sections where id = 'ec00000b-0000-0000-0000-00000000000b'),
    now() - interval '2 days', 'Explain J.2 unguided', 'Good account.', 5, true, 'unguided');

-- Essay-K-level-4 and Essay-L-level-1 scenarios (every card seen/future-safe;
-- one card seen but not future-safe) are deliberately NOT static SQL fixture
-- rows here — any new flashcard_review_state row perturbs
-- test_stats_system_wide_partitions_all_bands' exact system-wide horizon-band
-- counts in tests/test_flashcards.py (same reasoning the Sprint11_ReviewStats
-- note below already documents for review_events). Built instead inside the
-- relevant test bodies in tests/test_essays.py via the existing
-- `_mk_essay` + POST .../review API-call pattern, same convention that file
-- already uses for `test_overview_progress_and_open_counts` etc.

-- ── review_events ─────────────────────────────────────────────────────────
--
-- Spans both prior_review_interval regimes:
--   fix-classic-established (fc000025): 2 "ordinary due" events (>=24h prior
--     — one success, one failure) + 1 rapid-retry event (<24h prior).
--   fix-fsrs-established (fc000023): 1 "ordinary due" success event (>=24h
--     prior) + 1 rapid-retry event (<24h prior).
INSERT INTO essaycards.review_events
    (flashcard_id, grade, reviewed_at, was_due, prior_review_interval, resulting_review_interval) VALUES
  ('fc000025-0000-0000-0000-000000000025', 'good',  now() - interval '4 days', true, interval '2 days', interval '4 days'),
  ('fc000025-0000-0000-0000-000000000025', 'again', now() - interval '3 days', true, interval '3 days', interval '5 seconds'),
  ('fc000025-0000-0000-0000-000000000025', 'good',  now() - interval '30 minutes', true, interval '10 minutes', interval '20 minutes'),
  ('fc000023-0000-0000-0000-000000000023', 'good',  now() - interval '5 days', true, interval '5 days', interval '10 days'),
  ('fc000023-0000-0000-0000-000000000023', 'again', now() - interval '20 minutes', true, interval '30 seconds', interval '60 seconds');

-- ── Sprint11_ReviewStats — review-performance stats page fixtures ───────────
--
-- GET /review-stats/summary aggregates essaycards.review_events with NO
-- essay/section scoping (global, across everything) — the same shape of
-- global aggregation backend/routers/experiment.py already performs over
-- the same table. Adding review_events rows tied to a NEW flashcard would
-- require a matching flashcard_review_state row too (or the two exact
-- hardcoded fixture-count assertions in tests/test_experiment.py, whose own
-- ground truth query JOINs flashcard_review_state to review_events, would
-- silently under-count relative to the real endpoint) — and ANY new
-- flashcard_review_state row would also perturb
-- test_stats_system_wide_partitions_all_bands' exact system-wide horizon-band
-- total in tests/test_flashcards.py. To avoid both, every new review_events
-- row below is attached to one of the two PRE-EXISTING established cards
-- from "Sprint10_DualSchedulerAB — dual-scheduler fixtures" above
-- (fc000025 classic / fc000023 fsrs, both already carry a
-- flashcard_review_state row), and every new row's prior_review_interval is
-- kept below 24 hours so it can never enter experiment.py's
-- prior_review_interval >= '24 hours' (ordinary_due_reviews/recall_rate/
-- failures) filter — that endpoint's existing hardcoded exact assertions
-- (ordinary_due_reviews == 2/1, recall_rate == 0.5/1.0) are therefore
-- unaffected; only its unfiltered completed_reviews count grows, which that
-- test only asserts with >=.
--
--   now()-2h  on fc000025 (classic, good)  -> counted in day/week/month
--   now()-3d  on fc000023 (fsrs,    hard)  -> counted in week/month, NOT day
--   now()-20d on fc000025 (classic, easy)  -> counted in month only
--   now()-40d on fc000025 (classic, good)  -> excluded from every window
--   now()-1h  on fc000023 (fsrs,    again, prior_review_interval 30s — a
--             rapid retry) -> counted in day/week/month same as any other
--             review (this endpoint applies no prior_review_interval
--             filter, unlike /experiment/summary's ordinary_due_reviews)
--   now()-2d  on fc000025 (classic, again) -> counted in week/month, NOT
--             day; exercises the grade breakdown / failures / recall_rate
--             math together with the now()-2h/-3d rows above
--
-- Two different cards are deliberately mixed within the same window (the
-- now()-2h row on fc000025 and the now()-1h row on fc000023 both land in the
-- day window) to exercise multi-card aggregation.
INSERT INTO essaycards.review_events
    (flashcard_id, grade, reviewed_at, was_due, prior_review_interval, resulting_review_interval) VALUES
  ('fc000025-0000-0000-0000-000000000025', 'good',  now() - interval '2 hours',  true, interval '10 minutes', interval '6 hours'),
  ('fc000023-0000-0000-0000-000000000023', 'hard',  now() - interval '3 days',   true, interval '5 minutes',  interval '9 hours'),
  ('fc000025-0000-0000-0000-000000000025', 'easy',  now() - interval '20 days',  true, interval '1 minute',   interval '25 hours'),
  ('fc000025-0000-0000-0000-000000000025', 'good',  now() - interval '40 days',  true, interval '2 minutes',  interval '20 hours'),
  ('fc000023-0000-0000-0000-000000000023', 'again', now() - interval '1 hour',   true, interval '30 seconds', interval '60 seconds'),
  ('fc000025-0000-0000-0000-000000000025', 'again', now() - interval '2 days',   true, interval '15 minutes', interval '5 seconds');

-- ── Sprint13_ReviewStatsSentenceFeedback — sentence splitting + feedback ─────
--
-- Essay S has no flashcards (so it perturbs no due-queue/progress assertion).
--   ec000012 fix-sent-plain    -> 3 sentences (the draft's "sky is blue" example)
--   ec000013 fix-sent-link     -> 2 sentences; first contains a markdown link
--                                 whose URL has an internal period
--   ec000014 fix-sent-nugget   -> 2 sentences; first contains [[nugget:...]]
--   ec000015 fix-sent-code     -> 2 prose sentences around a fenced code block
--   ec000016 fix-sent-feedback -> 4 sentences; index 0 marked difficult only,
--                                 index 1 marked thumbs-up only, 2 and 3 unmarked
INSERT INTO essaycards.essays (id, title, slug, created_at, updated_at) VALUES
  ('ea00000b-0000-0000-0000-00000000000b', 'Essay S (sentences)', 'essay-s-sentences', now() - interval '1 hour', now() - interval '1 hour');

INSERT INTO essaycards.essay_sections (id, essay_id, order_index, heading, anchor_slug, body_markdown) VALUES
  ('ec000012-0000-0000-0000-000000000012', 'ea00000b-0000-0000-0000-00000000000b', 0, 'S Plain', 'fix-sent-plain',
    'The sky is blue. The grass is green. Is that surprising?'),
  ('ec000013-0000-0000-0000-000000000013', 'ea00000b-0000-0000-0000-00000000000b', 1, 'S Link', 'fix-sent-link',
    'See [source](http://example.com/a.b) for details on this. Another sentence follows.'),
  ('ec000014-0000-0000-0000-000000000014', 'ea00000b-0000-0000-0000-00000000000b', 2, 'S Nugget', 'fix-sent-nugget',
    'Consider [[nugget:some-key]] carefully before moving on. Then continue.'),
  ('ec000015-0000-0000-0000-000000000015', 'ea00000b-0000-0000-0000-00000000000b', 3, 'S Code', 'fix-sent-code',
    E'Before the code block. Still before it.\n\n```python\nx = 1. Y = 2\n```\n\nAfter the code.'),
  ('ec000016-0000-0000-0000-000000000016', 'ea00000b-0000-0000-0000-00000000000b', 4, 'S Feedback', 'fix-sent-feedback',
    'Alpha is first. Beta is second. Gamma is third. Delta is fourth.');

INSERT INTO essaycards.sentence_feedback (section_id, sentence_index, sentence_text, is_difficult, is_thumbs_up) VALUES
  ('ec000016-0000-0000-0000-000000000016', 0, 'Alpha is first.',  true,  false),
  ('ec000016-0000-0000-0000-000000000016', 1, 'Beta is second.',  false, true);

-- ════════════════════════════════════════════════════════════════════════════
-- Sprint14_SectionProgressionAndRevalidation
-- ════════════════════════════════════════════════════════════════════════════
--
-- (a) Every EXISTING fixture section (ec000001..ec000016) is grandfathered as
--     guided_passed (source 'grandfathered'), so every prior sprint's cards stay
--     eligible for queues and review exactly as before.
INSERT INTO essaycards.section_oral_state (section_id, guided_passed, guided_pass_source) VALUES
  ('ec000001-0000-0000-0000-000000000001', true, 'grandfathered'),
  ('ec000002-0000-0000-0000-000000000002', true, 'grandfathered'),
  ('ec000003-0000-0000-0000-000000000003', true, 'grandfathered'),
  ('ec000004-0000-0000-0000-000000000004', true, 'grandfathered'),
  ('ec000005-0000-0000-0000-000000000005', true, 'grandfathered'),
  ('ec000006-0000-0000-0000-000000000006', true, 'grandfathered'),
  ('ec000007-0000-0000-0000-000000000007', true, 'grandfathered'),
  ('ec000008-0000-0000-0000-000000000008', true, 'grandfathered'),
  ('ec000009-0000-0000-0000-000000000009', true, 'grandfathered'),
  ('ec000010-0000-0000-0000-000000000010', true, 'grandfathered'),
  ('ec000011-0000-0000-0000-000000000011', true, 'grandfathered'),
  ('ec00000a-0000-0000-0000-00000000000a', true, 'grandfathered'),
  ('ec00000b-0000-0000-0000-00000000000b', true, 'grandfathered'),
  ('ec000012-0000-0000-0000-000000000012', true, 'grandfathered'),
  ('ec000013-0000-0000-0000-000000000013', true, 'grandfathered'),
  ('ec000014-0000-0000-0000-000000000014', true, 'grandfathered'),
  ('ec000015-0000-0000-0000-000000000015', true, 'grandfathered'),
  ('ec000016-0000-0000-0000-000000000016', true, 'grandfathered');

-- (b) Progression worlds. Name -> id traceability:
--   fix-essay-locked   ea00000c  section ec000017 'fix-locked-1'   cards fc000031/32
--   fix-essay-yellow   ea00000d  sections ec000018 'fix-yellow-1' (2 cards, one learning),
--                                         ec000019 'fix-yellow-2' (guided passed, ZERO cards);
--                                essay guided oral passed, 2 essay attempts
--   fix-essay-green    ea00000e  section ec00001a 'fix-green-1' (every card established)
--   fix-essay-learned  ea00000f  section ec00001b 'fix-learned-1' (cards at 29d and 45d)
--   fix-essay-maturity ea000010  section ec00001c 'fix-maturity-1' (23h59m, 24h, 29d, 30d, new)
--   fix-essay-blue     ea000011  sections ec00001d/1e (guided + unguided passed), essay NOT violet
--   fix-essay-violet   ea000012  sections ec00001f (all cards established -> falls back to green),
--                                         ec000020 (learning + never-reviewed card -> yellow);
--                                essay guided + unguided passed (Violet)
-- No fixture card is due now except the two LOCKED fix-essay-locked cards (excluded
-- from queues and stats by the unlock rule), so the unscoped /due and the
-- system-wide /stats band counts of earlier sprints only grow in future bands.
INSERT INTO essaycards.essays (id, title, slug, created_at, updated_at) VALUES
  ('ea00000c-0000-0000-0000-00000000000c', 'Locked essay',   'fix-essay-locked',   now() - interval '20 hours', now() - interval '20 hours'),
  ('ea00000d-0000-0000-0000-00000000000d', 'Yellow essay',   'fix-essay-yellow',   now() - interval '19 hours', now() - interval '19 hours'),
  ('ea00000e-0000-0000-0000-00000000000e', 'Green essay',    'fix-essay-green',    now() - interval '18 hours', now() - interval '18 hours'),
  ('ea00000f-0000-0000-0000-00000000000f', 'Learned essay',  'fix-essay-learned',  now() - interval '17 hours', now() - interval '17 hours'),
  ('ea000010-0000-0000-0000-000000000010', 'Maturity essay', 'fix-essay-maturity', now() - interval '16 hours', now() - interval '16 hours'),
  ('ea000011-0000-0000-0000-000000000011', 'Blue essay',     'fix-essay-blue',     now() - interval '15 hours', now() - interval '15 hours'),
  ('ea000012-0000-0000-0000-000000000012', 'Violet essay',   'fix-essay-violet',   now() - interval '14 hours', now() - interval '14 hours');

INSERT INTO essaycards.essay_sections (id, essay_id, order_index, heading, anchor_slug, body_markdown) VALUES
  ('ec000017-0000-0000-0000-000000000017', 'ea00000c-0000-0000-0000-00000000000c', 0, 'Locked 1',   'fix-locked-1',   'Locked section body.'),
  ('ec000018-0000-0000-0000-000000000018', 'ea00000d-0000-0000-0000-00000000000d', 0, 'Yellow 1',   'fix-yellow-1',   'Yellow section 1 body.'),
  ('ec000019-0000-0000-0000-000000000019', 'ea00000d-0000-0000-0000-00000000000d', 1, 'Yellow 2',   'fix-yellow-2',   'Yellow section 2 body (no cards).'),
  ('ec00001a-0000-0000-0000-00000000001a', 'ea00000e-0000-0000-0000-00000000000e', 0, 'Green 1',    'fix-green-1',    'Green section body.'),
  ('ec00001b-0000-0000-0000-00000000001b', 'ea00000f-0000-0000-0000-00000000000f', 0, 'Learned 1',  'fix-learned-1',  'Learned section body.'),
  ('ec00001c-0000-0000-0000-00000000001c', 'ea000010-0000-0000-0000-000000000010', 0, 'Maturity 1', 'fix-maturity-1', 'Maturity section body.'),
  ('ec00001d-0000-0000-0000-00000000001d', 'ea000011-0000-0000-0000-000000000011', 0, 'Blue 1',     'fix-blue-1',     'Blue section 1 body.'),
  ('ec00001e-0000-0000-0000-00000000001e', 'ea000011-0000-0000-0000-000000000011', 1, 'Blue 2',     'fix-blue-2',     'Blue section 2 body.'),
  ('ec00001f-0000-0000-0000-00000000001f', 'ea000012-0000-0000-0000-000000000012', 0, 'Violet 1',   'fix-violet-1',   'Violet section 1 body.'),
  ('ec000020-0000-0000-0000-000000000020', 'ea000012-0000-0000-0000-000000000012', 1, 'Violet 2',   'fix-violet-2',   'Violet section 2 body.');

INSERT INTO essaycards.flashcards (id, essay_id, section_id, card_key, question, answer, level) VALUES
  -- locked essay: never reviewed, due by date, but locked
  ('fc000031-0000-0000-0000-000000000031', 'ea00000c-0000-0000-0000-00000000000c', 'ec000017-0000-0000-0000-000000000017', 'fix-locked-c1',   'Locked q1', 'Locked a1', 1),
  ('fc000032-0000-0000-0000-000000000032', 'ea00000c-0000-0000-0000-00000000000c', 'ec000017-0000-0000-0000-000000000017', 'fix-locked-c2',   'Locked q2', 'Locked a2', 2),
  -- yellow
  ('fc000033-0000-0000-0000-000000000033', 'ea00000d-0000-0000-0000-00000000000d', 'ec000018-0000-0000-0000-000000000018', 'fix-yellow-est',   'Yellow q1 (established)', 'Yellow a1', 1),
  ('fc000034-0000-0000-0000-000000000034', 'ea00000d-0000-0000-0000-00000000000d', 'ec000018-0000-0000-0000-000000000018', 'fix-yellow-learn', 'Yellow q2 (learning)',    'Yellow a2', 2),
  -- green
  ('fc000035-0000-0000-0000-000000000035', 'ea00000e-0000-0000-0000-00000000000e', 'ec00001a-0000-0000-0000-00000000001a', 'fix-green-c1',     'Green q1', 'Green a1', 1),
  ('fc000036-0000-0000-0000-000000000036', 'ea00000e-0000-0000-0000-00000000000e', 'ec00001a-0000-0000-0000-00000000001a', 'fix-green-c2',     'Green q2', 'Green a2', 2),
  -- learned
  ('fc000037-0000-0000-0000-000000000037', 'ea00000f-0000-0000-0000-00000000000f', 'ec00001b-0000-0000-0000-00000000001b', 'fix-learned-29d',  'Learned q1 (29d)', 'Learned a1', 1),
  ('fc000038-0000-0000-0000-000000000038', 'ea00000f-0000-0000-0000-00000000000f', 'ec00001b-0000-0000-0000-00000000001b', 'fix-learned-45d',  'Learned q2 (45d)', 'Learned a2', 2),
  -- maturity
  ('fc000039-0000-0000-0000-000000000039', 'ea000010-0000-0000-0000-000000000010', 'ec00001c-0000-0000-0000-00000000001c', 'fix-mat-23h59m',   'Maturity q1', 'Maturity a1', 1),
  ('fc000040-0000-0000-0000-000000000040', 'ea000010-0000-0000-0000-000000000010', 'ec00001c-0000-0000-0000-00000000001c', 'fix-mat-24h',      'Maturity q2', 'Maturity a2', 1),
  ('fc000041-0000-0000-0000-000000000041', 'ea000010-0000-0000-0000-000000000010', 'ec00001c-0000-0000-0000-00000000001c', 'fix-mat-29d',      'Maturity q3', 'Maturity a3', 1),
  ('fc000042-0000-0000-0000-000000000042', 'ea000010-0000-0000-0000-000000000010', 'ec00001c-0000-0000-0000-00000000001c', 'fix-mat-30d',      'Maturity q4', 'Maturity a4', 1),
  ('fc000043-0000-0000-0000-000000000043', 'ea000010-0000-0000-0000-000000000010', 'ec00001c-0000-0000-0000-00000000001c', 'fix-mat-new',      'Maturity q5', 'Maturity a5', 1),
  -- blue
  ('fc000044-0000-0000-0000-000000000044', 'ea000011-0000-0000-0000-000000000011', 'ec00001d-0000-0000-0000-00000000001d', 'fix-blue-c1',      'Blue q1', 'Blue a1', 1),
  ('fc000045-0000-0000-0000-000000000045', 'ea000011-0000-0000-0000-000000000011', 'ec00001e-0000-0000-0000-00000000001e', 'fix-blue-c2',      'Blue q2', 'Blue a2', 1),
  -- violet: section 1 (two established/learned cards), section 2 (one learning + one never-reviewed)
  ('fc000046-0000-0000-0000-000000000046', 'ea000012-0000-0000-0000-000000000012', 'ec00001f-0000-0000-0000-00000000001f', 'fix-violet-c1',    'Violet q1', 'Violet a1', 1),
  ('fc000047-0000-0000-0000-000000000047', 'ea000012-0000-0000-0000-000000000012', 'ec00001f-0000-0000-0000-00000000001f', 'fix-violet-c2',    'Violet q2', 'Violet a2', 2),
  ('fc000048-0000-0000-0000-000000000048', 'ea000012-0000-0000-0000-000000000012', 'ec000020-0000-0000-0000-000000000020', 'fix-violet-c3',    'Violet q3 (learning)', 'Violet a3', 1),
  ('fc000049-0000-0000-0000-000000000049', 'ea000012-0000-0000-0000-000000000012', 'ec000020-0000-0000-0000-000000000020', 'fix-violet-new',   'Violet q4 (never reviewed)', 'Violet a4', 2);

-- review_interval is written explicitly (= next_due_at - last_reviewed_at).
INSERT INTO essaycards.flashcard_review_state (flashcard_id, last_reviewed_at, next_due_at, review_interval) VALUES
  ('fc000031-0000-0000-0000-000000000031', null, now() - interval '10 minutes', interval '0'),
  ('fc000032-0000-0000-0000-000000000032', null, now() - interval '5 minutes',  interval '0'),
  -- yellow
  ('fc000033-0000-0000-0000-000000000033', now() - interval '1 day',   now() + interval '2 days',  interval '3 days'),
  ('fc000034-0000-0000-0000-000000000034', now() - interval '1 hour',  now() + interval '1 hour',  interval '2 hours'),
  -- green
  ('fc000035-0000-0000-0000-000000000035', now() - interval '1 day',   now() + interval '20 hours', interval '44 hours'),
  ('fc000036-0000-0000-0000-000000000036', now() - interval '2 days',  now() + interval '8 days',   interval '10 days'),
  -- learned
  ('fc000037-0000-0000-0000-000000000037', now() - interval '10 days', now() + interval '19 days',  interval '29 days'),
  ('fc000038-0000-0000-0000-000000000038', now() - interval '5 days',  now() + interval '40 days',  interval '45 days'),
  -- maturity (23h59m / 24h / 29d / 30d / never reviewed but unlocked)
  ('fc000039-0000-0000-0000-000000000039', now() - interval '10 hours', now() - interval '10 hours' + interval '23 hours 59 minutes', interval '23 hours 59 minutes'),
  ('fc000040-0000-0000-0000-000000000040', now() - interval '10 hours', now() - interval '10 hours' + interval '24 hours',             interval '24 hours'),
  ('fc000041-0000-0000-0000-000000000041', now() - interval '5 days',   now() + interval '24 days',   interval '29 days'),
  ('fc000042-0000-0000-0000-000000000042', now() - interval '5 days',   now() + interval '25 days',   interval '30 days'),
  ('fc000043-0000-0000-0000-000000000043', null,                         now() + interval '3 hours',   interval '0'),
  -- blue
  ('fc000044-0000-0000-0000-000000000044', now() - interval '2 days',  now() + interval '3 days',  interval '5 days'),
  ('fc000045-0000-0000-0000-000000000045', now() - interval '2 days',  now() + interval '3 days',  interval '5 days'),
  -- violet
  ('fc000046-0000-0000-0000-000000000046', now() - interval '15 days', now() + interval '25 days',  interval '40 days'),
  ('fc000047-0000-0000-0000-000000000047', now() - interval '10 days', now() + interval '25 days',  interval '35 days'),
  ('fc000048-0000-0000-0000-000000000048', now() - interval '1 hour',  now() + interval '4 hours',  interval '5 hours'),
  ('fc000049-0000-0000-0000-000000000049', null,                        now() + interval '6 hours',  interval '0');

-- Known FSRS memory state for one violet card (revalidation 'preserved' test
-- compares this row before/after a correct revalidation).
INSERT INTO essaycards.fsrs_card_state
    (flashcard_id, stability, difficulty, fsrs_state, step, last_review_at, raw_state) VALUES
  ('fc000046-0000-0000-0000-000000000046', 40.0, 5.0, 2, null, now() - interval '15 days',
   jsonb_build_object(
     'card_id', 1, 'state', 2, 'step', null, 'stability', 40.0, 'difficulty', 5.0,
     'due', now() + interval '25 days', 'last_review', now() - interval '15 days'
   ));

-- Oral state. Absent row == not started (locked / grey): fix-essay-locked has none.
INSERT INTO essaycards.section_oral_state
    (section_id, guided_passed, guided_pass_source, guided_passed_at, guided_latest_score,
     unguided_passed, unguided_passed_at, unguided_latest_score) VALUES
  ('ec000018-0000-0000-0000-000000000018', true, 'exam', now() - interval '9 days', 5, false, null, null),
  ('ec000019-0000-0000-0000-000000000019', true, 'exam', now() - interval '9 days', 6, false, null, null),
  ('ec00001a-0000-0000-0000-00000000001a', true, 'exam', now() - interval '9 days', 5, false, null, null),
  ('ec00001b-0000-0000-0000-00000000001b', true, 'exam', now() - interval '9 days', 5, false, null, null),
  ('ec00001c-0000-0000-0000-00000000001c', true, 'exam', now() - interval '9 days', 5, false, null, null),
  ('ec00001d-0000-0000-0000-00000000001d', true, 'exam', now() - interval '9 days', 5, true, now() - interval '5 days', 5),
  ('ec00001e-0000-0000-0000-00000000001e', true, 'exam', now() - interval '9 days', 5, true, now() - interval '5 days', 6),
  ('ec00001f-0000-0000-0000-00000000001f', true, 'exam', now() - interval '20 days', 5, true, now() - interval '10 days', 5),
  ('ec000020-0000-0000-0000-000000000020', true, 'exam', now() - interval '20 days', 6, true, now() - interval '10 days', 5);

INSERT INTO essaycards.essay_oral_state
    (essay_id, guided_passed, guided_passed_at, guided_latest_score,
     unguided_passed, unguided_passed_at, unguided_latest_score) VALUES
  ('ea00000d-0000-0000-0000-00000000000d', true, now() - interval '10 days', 5, false, null, 3),
  ('ea000011-0000-0000-0000-000000000011', true, now() - interval '8 days',  5, false, null, null),
  ('ea000012-0000-0000-0000-000000000012', true, now() - interval '20 days', 6, true, now() - interval '10 days', 5);

INSERT INTO essaycards.essay_examinations
    (id, essay_id, exam_type, examined_at, question, answer_transcript, score, passed, feedback) VALUES
  ('e5000001-0000-0000-0000-000000000001', 'ea00000d-0000-0000-0000-00000000000d', 'guided',   now() - interval '10 days', 'Explain the essay (guided).',   'A solid account.', 5, true,  'Good.'),
  ('e5000002-0000-0000-0000-000000000002', 'ea00000d-0000-0000-0000-00000000000d', 'unguided', now() - interval '2 days',  'Explain the essay (unguided).', 'A partial account.', 3, false, 'Not yet.'),
  ('e5000003-0000-0000-0000-000000000003', 'ea000012-0000-0000-0000-000000000012', 'guided',   now() - interval '20 days', 'Explain the essay (guided).',   'A strong account.', 6, true,  'Excellent.'),
  ('e5000004-0000-0000-0000-000000000004', 'ea000012-0000-0000-0000-000000000012', 'unguided', now() - interval '10 days', 'Explain the essay (unguided).', 'A strong account.', 5, true,  'Good.');
