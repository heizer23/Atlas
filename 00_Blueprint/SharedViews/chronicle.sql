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

-- Protein intake: 100 = 180 g
SELECT
    f.logged_at::date AS date,
    'food'::text AS application,
    'Protein Intake'::text AS source_label,
    'Protein'::text AS label,
    LEAST(100, GREATEST(1, ROUND(SUM(f.protein_g) / 180.0 * 100)::int)) AS value,
    COALESCE(s.selected, FALSE) AS selected,
    NULL::text AS detail,
    NULL::text AS deep_link
FROM foodtracker.food_logs f
LEFT JOIN shared_views.calendar_source_selection s
    ON s.application = 'food'
   AND s.source_label = 'Protein Intake'
GROUP BY
    f.logged_at::date,
    s.selected

UNION ALL

-- Calorie intake: 100 = 1800 kcal, floor 10 at 4000 kcal, 0 only if no entries exist
SELECT
    f.logged_at::date AS date,
    'food'::text AS application,
    'Calorie Intake'::text AS source_label,
    'Calories'::text AS label,
    CASE
        WHEN SUM(f.kcal) <= 1800 THEN 100
        WHEN SUM(f.kcal) >= 4000 THEN 10
        ELSE ROUND(
            100 - ((SUM(f.kcal) - 1800) / (4000.0 - 1800.0) * 90)
        )::int
    END AS value,
    COALESCE(s.selected, FALSE) AS selected,
    NULL::text AS detail,
    NULL::text AS deep_link
FROM foodtracker.food_logs f
LEFT JOIN shared_views.calendar_source_selection s
    ON s.application = 'food'
   AND s.source_label = 'Calorie Intake'
GROUP BY
    f.logged_at::date,
    s.selected

UNION ALL

-- Fiber intake: 100 = 30 g
SELECT
    f.logged_at::date AS date,
    'food'::text AS application,
    'Fiber Intake'::text AS source_label,
    'Fiber'::text AS label,
    LEAST(100, GREATEST(1, ROUND(SUM(f.fiber_g) / 30.0 * 100)::int)) AS value,
    COALESCE(s.selected, FALSE) AS selected,
    NULL::text AS detail,
    NULL::text AS deep_link
FROM foodtracker.food_logs f
LEFT JOIN shared_views.calendar_source_selection s
    ON s.application = 'food'
   AND s.source_label = 'Fiber Intake'
GROUP BY
    f.logged_at::date,
    s.selected;