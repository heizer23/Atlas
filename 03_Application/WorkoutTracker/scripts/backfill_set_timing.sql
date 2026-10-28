-- One-off backfill of set timing for LEGACY workouts (logged before set timing existed).
--
-- Rule (uniform, deterministic, no randomness): every legacy session is treated as one
-- optimal workout. Edit the params below to tune; the result depends only on exercise order and
-- the number of performed sets.
--   session start : start_local on the workout date, in tz (DST-correct)
--   per set       : set_sec long; rest_sec between the sets of an exercise
--   between exercises : transition_sec after an exercise's last set
--
-- Scope: only rows of sessions WITHOUT a workout_session row (= logged before the Session tab) that
-- are 'done' and have no timing at all. Every session started from the app has a workout_session
-- row, so real measurements can never be touched. The result is NOT marked in the data
-- (deliberate); legacy = "no workout_session row". Undo: scripts/remove_backfilled_set_timing.sql.
-- Idempotent: rows that already have timing are skipped. Weights, reps, comments, dates and
-- session relationships are not touched.
--
-- Run:  docker exec -i atlas-postgres psql -U atlas -d atlas -v ON_ERROR_STOP=1 < this_file

begin;

with p as (
  select time '17:00' as start_local, 'Europe/Berlin'::text as tz,
         40 as set_sec, 120 as rest_sec, 180 as transition_sec
),
ex as (
  select l.workout_log_id, l.workout_id, l.workout_date,
         row_number() over (partition by l.workout_id order by l.created_at, l.workout_log_id) as ord,
         (l.set1_reps is not null)::int + (l.set2_reps is not null)::int + (l.set3_reps is not null)::int
           + (l.set4_reps is not null)::int + (l.set5_reps is not null)::int as k
  from workout.workout_log l
  where l.status = 'done'
    and not exists (select 1 from workout.workout_session s where s.workout_id = l.workout_id)
    and num_nulls(l.set1_started_at, l.set1_ended_at, l.set2_started_at, l.set2_ended_at,
                  l.set3_started_at, l.set3_ended_at, l.set4_started_at, l.set4_ended_at,
                  l.set5_started_at, l.set5_ended_at) = 10
),
blocks as (
  select ex.*, ex.k * p.set_sec + greatest(ex.k - 1, 0) * p.rest_sec + p.transition_sec as block_sec
  from ex cross join p where ex.k > 0
),
offs as (
  select b.*,
         coalesce(sum(b.block_sec) over (partition by b.workout_id order by b.ord
                  rows between unbounded preceding and 1 preceding), 0) as off_sec,
         ((b.workout_date + p.start_local) at time zone p.tz) as t0
  from blocks b cross join p
),
sets as (
  select o.workout_log_id, s.n, o.t0, o.off_sec,
         row_number() over (partition by o.workout_log_id order by s.n) - 1 as pos
  from offs o
  join workout.workout_log l using (workout_log_id)
  cross join lateral (values (1, l.set1_reps), (2, l.set2_reps), (3, l.set3_reps),
                             (4, l.set4_reps), (5, l.set5_reps)) s(n, reps)
  where s.reps is not null
),
timed as (
  select s.workout_log_id, s.n,
         s.t0 + make_interval(secs => s.off_sec + s.pos * (p.set_sec + p.rest_sec))              as st,
         s.t0 + make_interval(secs => s.off_sec + s.pos * (p.set_sec + p.rest_sec) + p.set_sec)  as en
  from sets s cross join p
),
agg as (
  select workout_log_id,
    max(st) filter (where n = 1) as s1, max(en) filter (where n = 1) as e1,
    max(st) filter (where n = 2) as s2, max(en) filter (where n = 2) as e2,
    max(st) filter (where n = 3) as s3, max(en) filter (where n = 3) as e3,
    max(st) filter (where n = 4) as s4, max(en) filter (where n = 4) as e4,
    max(st) filter (where n = 5) as s5, max(en) filter (where n = 5) as e5
  from timed group by workout_log_id
)
update workout.workout_log l set
  set1_started_at = a.s1, set1_ended_at = a.e1,
  set2_started_at = a.s2, set2_ended_at = a.e2,
  set3_started_at = a.s3, set3_ended_at = a.e3,
  set4_started_at = a.s4, set4_ended_at = a.e4,
  set5_started_at = a.s5, set5_ended_at = a.e5
from agg a
where l.workout_log_id = a.workout_log_id;

commit;
