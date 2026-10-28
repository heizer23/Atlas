begin;

-- Derived timing, measured values only. Nothing here is estimated or stored: a missing start or
-- end stays NULL, and a quantity that needs it is NULL too.
--
-- workout.set_timing: one row per performed set (reps present).
--   duration_sec : ended - started           (needs both)
--   rest_sec     : started - previous set's end within the same exercise (needs both; NULL if the
--                  start precedes the previous end, i.e. the next set was tapped early)
--   interval_sec : ended - previous set's end (set + rest together; needs only confirmations,
--                  so it exists even when a start tap was forgotten)
--   interrupted  : rest_sec above 10 minutes (the workout was probably interrupted); keep the
--                  value, exclude it from averages
-- The gap between two exercises is a transition, not rest, and is never computed here.
create or replace view workout.set_timing as
with sets as (
  select
    l.workout_log_id, l.workout_id, l.exercise, l.workout_date,
    s.n as set_no, s.reps, s.started_at, s.ended_at
  from workout.workout_log l
  cross join lateral (values
    (1, l.set1_reps, l.set1_started_at, l.set1_ended_at),
    (2, l.set2_reps, l.set2_started_at, l.set2_ended_at),
    (3, l.set3_reps, l.set3_started_at, l.set3_ended_at),
    (4, l.set4_reps, l.set4_started_at, l.set4_ended_at),
    (5, l.set5_reps, l.set5_started_at, l.set5_ended_at)
  ) s(n, reps, started_at, ended_at)
  where l.status = 'done' and s.reps is not null
),
prev as (
  select *, lag(ended_at) over (partition by workout_log_id order by set_no) as prev_ended_at
  from sets
)
select
  workout_log_id, workout_id, exercise, workout_date, set_no, reps, started_at, ended_at,
  case when started_at is not null and ended_at is not null
       then extract(epoch from ended_at - started_at)::int end                  as duration_sec,
  case when started_at is not null and prev_ended_at is not null and started_at >= prev_ended_at
       then extract(epoch from started_at - prev_ended_at)::int end             as rest_sec,
  case when ended_at is not null and prev_ended_at is not null
       then extract(epoch from ended_at - prev_ended_at)::int end               as interval_sec,
  coalesce(started_at is not null and prev_ended_at is not null
           and started_at >= prev_ended_at
           and extract(epoch from started_at - prev_ended_at) > 600, false)     as interrupted
from prev;

-- workout.exercise_timing: one row per performed exercise occurrence.
--   started_at / ended_at : first measured set start / last measured set end
--   duration_sec          : ended - started (elapsed, includes rests; needs both)
--   rest_avg_sec          : mean measured rest, interrupted rests excluded
--   time_of_day           : HH24:MI of started_at (else of the first confirmation) in the
--                           workout's time zone; sessions without a stored tz (all legacy
--                           sessions) are read as Europe/Berlin, the zone they were logged in.
create or replace view workout.exercise_timing as
select
  t.workout_log_id,
  min(t.started_at)                                                  as started_at,
  max(t.ended_at)                                                    as ended_at,
  case when min(t.started_at) is not null and max(t.ended_at) is not null
       then extract(epoch from max(t.ended_at) - min(t.started_at))::int end as duration_sec,
  round(avg(t.rest_sec) filter (where not t.interrupted))::int       as rest_avg_sec,
  to_char(coalesce(min(t.started_at), min(t.ended_at))
          at time zone coalesce(max(s.tz), 'Europe/Berlin'), 'HH24:MI') as time_of_day
from workout.set_timing t
left join workout.workout_session s on s.workout_id = t.workout_id
group by t.workout_log_id
having min(t.started_at) is not null or min(t.ended_at) is not null;

commit;

-- Rollback: drop view workout.exercise_timing; drop view workout.set_timing;
