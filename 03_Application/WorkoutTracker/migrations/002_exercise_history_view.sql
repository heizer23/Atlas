begin;

-- exercise_session_history
-- One row per exercise entry. Adds total_reps (sum of all sets) and delta
-- (difference vs the previous time this exercise was performed, partitioned
-- by exercise name case-insensitively, ordered chronologically).
-- delta IS NULL for the first occurrence of an exercise.

create or replace view workout.exercise_session_history as
select
    workout_log_id::text                                                    as id,
    workout_id::text                                                        as session_id,
    exercise,
    workout_date,
    weight_kg,
    set1_reps, set2_reps, set3_reps, set4_reps, set5_reps,
    created_at,

    coalesce(set1_reps,0)+coalesce(set2_reps,0)+coalesce(set3_reps,0)+
    coalesce(set4_reps,0)+coalesce(set5_reps,0)                             as total_reps,

    (
        coalesce(set1_reps,0)+coalesce(set2_reps,0)+coalesce(set3_reps,0)+
        coalesce(set4_reps,0)+coalesce(set5_reps,0)
    ) - lag(
        coalesce(set1_reps,0)+coalesce(set2_reps,0)+coalesce(set3_reps,0)+
        coalesce(set4_reps,0)+coalesce(set5_reps,0)
    ) over (
        partition by lower(exercise)
        order by workout_date asc, created_at asc
    )                                                                       as delta

from workout.workout_log;

commit;
