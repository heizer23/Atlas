CREATE SCHEMA IF NOT EXISTS shared_views;

CREATE TABLE IF NOT EXISTS shared_views.calendar_source_selection (
    application  TEXT NOT NULL,
    source_label TEXT NOT NULL,
    selected     BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (application, source_label)
);

CREATE OR REPLACE VIEW shared_views.calendar_event_view AS

-- Workout days: one row per day
SELECT
    w.workout_date::date AS date,
    'workout'::text AS application,
    'Workout Days'::text AS source_label,
    string_agg(DISTINCT w.split, ', ' ORDER BY w.split)::text AS label,
    100::int AS value,
    COALESCE(s.selected, FALSE) AS selected,
    NULL::text AS detail,
    NULL::text AS deep_link
FROM workout.workout_log w
LEFT JOIN shared_views.calendar_source_selection s
    ON s.application = 'workout'
   AND s.source_label = 'Workout Days'
GROUP BY
    w.workout_date,
    s.selected

UNION ALL

-- Protein intake: one row per day
SELECT
    f.logged_at::date AS date,
    'food'::text AS application,
    'Protein Intake'::text AS source_label,
    'Protein'::text AS label,
    LEAST(100, GREATEST(1, ROUND(SUM(f.protein_g))::int)) AS value,
    COALESCE(s.selected, FALSE) AS selected,
    NULL::text AS detail,
    NULL::text AS deep_link
FROM foodtracker.food_logs f
LEFT JOIN shared_views.calendar_source_selection s
    ON s.application = 'food'
   AND s.source_label = 'Protein Intake'
GROUP BY
    f.logged_at::date,
    s.selected;