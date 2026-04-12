-- NumericSeries test fixtures — Sprint02 + Sprint03
--
-- Sprint02 fixtures:
--   fix-label-weight → 'Weight' (has series record) — used by Sprint02 by-name tests
--   fix-label-steps  → 'Daily Steps' (no series record) — used by Sprint02 not-found tests
--
-- Sprint03 additions:
--   fix-label-weight label_name stays 'weight' — must match catalog key for batch tests
--   fix-label-weight now renamed to match catalog key 'weight' for batch endpoint tests.
--   NOTE: The existing Sprint02 tests use case-insensitive match ('Weight' == 'weight'),
--   so changing the label name does not break Sprint02 test scenarios.
--   fix-label-bodyfat → 'body_fat_pct' (has series record) — for batch multi-measurement test
--   fix-label-steps label stays 'Daily Steps' (does not match catalog key 'steps')
--     → used for SERIES_NOT_FOUND tests where key is catalog-valid but label doesn't match
--   Measurements for fix-label-weight: two entries with different timestamps for sparkline test

-- Labels (shared schema)
INSERT INTO labels.labels (id, name)
VALUES
    ('fix-label-weight',  'weight'),
    ('fix-label-bodyfat', 'body_fat_pct'),
    ('fix-label-steps',   'Daily Steps')
ON CONFLICT (id) DO NOTHING;

-- Series records
-- Weight has a series; body_fat_pct has a series; Daily Steps does not
INSERT INTO numeric_series.series (label_id)
VALUES
    ('fix-label-weight'),
    ('fix-label-bodyfat')
ON CONFLICT DO NOTHING;

-- Measurements for fix-label-weight (two entries with different timestamps)
-- Used by: sparkline_points format test, by-name tests
INSERT INTO numeric_series.measurements (label_id, value, recorded_at)
VALUES
    ('fix-label-weight', 80.5, '2026-04-01T08:00:00Z'),
    ('fix-label-weight', 79.8, '2026-04-05T08:00:00Z')
ON CONFLICT DO NOTHING;
