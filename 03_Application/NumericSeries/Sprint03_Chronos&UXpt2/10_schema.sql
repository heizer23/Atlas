-- NumericSeries private application schema
-- Carried forward from Sprint01 — no new tables in Sprint03.
-- The measurement catalog is a static JSON artifact (measurement_definitions.json),
-- not a database table.
-- Source of truth: 00_architecture/schema.sql

CREATE SCHEMA IF NOT EXISTS numeric_series;

-- series: one row per tracked label.
-- label_id references the label in LabelEngine (labels.labels).
-- NumericSeries does not enforce a foreign key to the LabelEngine schema
-- because LabelEngine manages its own schema independently.
CREATE TABLE IF NOT EXISTS numeric_series.series (
    label_id   TEXT        PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- measurements: one numeric value per entry.
-- recorded_at is the user-supplied timestamp of when the measurement was taken.
-- created_at is the server insertion time (audit use only).
CREATE TABLE IF NOT EXISTS numeric_series.measurements (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    label_id    TEXT        NOT NULL REFERENCES numeric_series.series(label_id) ON DELETE CASCADE,
    value       DOUBLE PRECISION NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index to support latest-value and sparkline queries (both order by recorded_at DESC)
CREATE INDEX IF NOT EXISTS measurements_label_recorded_idx
    ON numeric_series.measurements (label_id, recorded_at DESC);
