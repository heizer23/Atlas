-- StoryReader Sprint01 — test fixtures
--
-- ID prefixes are valid-hex and readable:
--   st = story, sv = story_version, an = annotation
--
-- fix-id traceability (referenced by name in Sprint01_Core/10_test_spec.md):
--   fix-lighthouse         -> aa000001-...-000000000001 (slug 'lighthouse', 2 versions)
--     fix-lighthouse-v1    -> ab000001-...-000000000001 (version 1, superseded)
--     fix-lighthouse-v2    -> ab000002-...-000000000002 (version 2, latest)
--     fix-ann-v1-old       -> ac000001-...-000000000001 (version 1 annotation, paragraph 0 "Old")
--     fix-ann-v2-first     -> ac000002-...-000000000002 (version 2 annotation, paragraph 0 "First")
--     fix-ann-v2-second    -> ac000003-...-000000000003 (version 2 annotation, paragraph 1 "Second")
--   fix-tidepool            -> aa000002-...-000000000002 (slug 'tidepool', 1 version — ingestion round-trip
--                              fixture; its version-1 body_markdown matches
--                              tests/fixtures_md/tidepool.md byte-for-byte so ingesting that same file
--                              is a same-hash "unchanged" no-op, and ingesting
--                              tests/fixtures_md/tidepool_changed.md appends a new version 2)
--     fix-tidepool-v1      -> ab000003-...-000000000003
--     fix-ann-tidepool-v1  -> ac000004-...-000000000004 (version 1 annotation, paragraph 0 "The")

-- ── Stories ────────────────────────────────────────────────────────────────────

INSERT INTO storyreader.stories (id, slug, title, latest_version, created_at, updated_at) VALUES
  ('aa000001-0000-0000-0000-000000000001', 'lighthouse', 'The Lighthouse', 2, now() - interval '2 hours', now() - interval '1 hours'),
  ('aa000002-0000-0000-0000-000000000002', 'tidepool',   'Tidepool',       1, now() - interval '2 hours', now() - interval '2 hours');

-- ── Story versions (immutable, append-only) ──────────────────────────────────

INSERT INTO storyreader.story_versions (id, story_id, version, body_markdown, content_sha256, created_at) VALUES
  ('ab000001-0000-0000-0000-000000000001', 'aa000001-0000-0000-0000-000000000001', 1,
   E'Old paragraph text describing the beginning of the lighthouse story before any revisions were made.\n\nA second paragraph followed here, adding a bit more texture to this earlier draft of the tale.',
   'fix0000000000000000000000000000000000000000000000000000000lh1',
   now() - interval '2 hours'),
  ('ab000002-0000-0000-0000-000000000002', 'aa000001-0000-0000-0000-000000000001', 2,
   E'First paragraph of the lighthouse revision, giving the reader clear context and sufficient length for testing.\n\nSecond paragraph adds more detail about the lighthouse for annotation testing purposes.',
   'fix0000000000000000000000000000000000000000000000000000000lh2',
   now() - interval '1 hours'),
  ('ab000003-0000-0000-0000-000000000003', 'aa000002-0000-0000-0000-000000000002', 1,
   E'The tide pool glimmered under the morning sun, holding a hundred small worlds in its shallow water.\n\nAnemones waved gently while hermit crabs shuffled between the rocks, unseen by anyone passing above.\n',
   'cf5cd2c0461ebc9a5c693e32b07947edc8c6eaae61bc28ef9d39312ae57d902c',
   now() - interval '2 hours');

-- ── Annotations ───────────────────────────────────────────────────────────────
-- lighthouse v1 paragraph 0 = "Old paragraph text describing the beginning of the
--   lighthouse story before any revisions were made." -> [0:3] = "Old"
-- lighthouse v2 paragraph 0 = "First paragraph of the lighthouse revision, giving
--   the reader clear context and sufficient length for testing." -> [0:5] = "First"
-- lighthouse v2 paragraph 1 = "Second paragraph adds more detail about the
--   lighthouse for annotation testing purposes." -> [0:6] = "Second"
-- tidepool v1 paragraph 0 = "The tide pool glimmered..." -> [0:3] = "The"

INSERT INTO storyreader.annotations
  (id, story_id, version, paragraph_index, char_start, char_end, selected_text, context_before, context_after, reaction, created_at, updated_at)
VALUES
  ('ac000001-0000-0000-0000-000000000001', 'aa000001-0000-0000-0000-000000000001', 1, 0, 0, 3, 'Old', '',
   ' paragraph text describing the beginning of the lighthouse story before any revisions were made.',
   'neutral', now() - interval '2 hours', now() - interval '2 hours'),
  ('ac000002-0000-0000-0000-000000000002', 'aa000001-0000-0000-0000-000000000001', 2, 0, 0, 5, 'First', '',
   ' paragraph of the lighthouse revision, giving the reader clear context and sufficient length for testing.',
   'positive', now() - interval '1 hours', now() - interval '1 hours'),
  ('ac000003-0000-0000-0000-000000000003', 'aa000001-0000-0000-0000-000000000001', 2, 1, 0, 6, 'Second', '',
   ' paragraph adds more detail about the lighthouse for annotation testing purposes.',
   'negative', now() - interval '1 hours', now() - interval '1 hours'),
  ('ac000004-0000-0000-0000-000000000004', 'aa000002-0000-0000-0000-000000000002', 1, 0, 0, 3, 'The', '',
   ' tide pool glimmered under the morning sun, holding a hundred small worlds in its shallow water.',
   'unclear', now() - interval '2 hours', now() - interval '2 hours');
