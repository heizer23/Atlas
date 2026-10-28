begin;

-- Session lifecycle.
-- A row here marks a session started through the Session tab. Sessions without
-- a row (all legacy data) are treated as finished. No backfill, no invented times.
create table if not exists workout.workout_session (
  workout_id   uuid primary key,
  split        text not null,   -- archetype name frozen at start; later edits don't rewrite history
  workout_date date not null,
  status       text not null default 'active',
  started_at   timestamptz not null default now(),
  finished_at  timestamptz null,

  constraint ck_session_status check (status in ('active', 'finished'))
);

-- At most one active session at a time (single-user app; guards against duplicates).
create unique index if not exists ux_workout_session_one_active
  on workout.workout_session ((status)) where status = 'active';

-- Exercise state. 'planned' = prefilled from an archetype/repeat, not yet performed.
-- Existing rows default to 'done', so legacy data is unchanged.
alter table workout.workout_log
  add column if not exists status text not null default 'done';

alter table workout.workout_log
  drop constraint if exists ck_workout_log_status;
alter table workout.workout_log
  add constraint ck_workout_log_status check (status in ('planned', 'done'));

-- A planned exercise has no reps yet; a done exercise still needs at least one.
alter table workout.workout_log drop constraint if exists ck_at_least_one_set;
alter table workout.workout_log drop constraint if exists ck_done_has_reps;
alter table workout.workout_log
  add constraint ck_done_has_reps check (
    status = 'planned' or
    set1_reps is not null or set2_reps is not null or set3_reps is not null or
    set4_reps is not null or set5_reps is not null
  );

-- exercise_session_history: only performed exercises count, and delta is only
-- defined when the previous occurrence used the same weight. Two unrecorded (NULL)
-- weights count as the same weight; NULL is NOT interpreted as bodyweight.
-- Different weights => delta IS NULL (not comparable).
create or replace view workout.exercise_session_history as
with done as (
  select
    workout_log_id, workout_id, exercise, workout_date, weight_kg,
    set1_reps, set2_reps, set3_reps, set4_reps, set5_reps, created_at,
    coalesce(set1_reps,0)+coalesce(set2_reps,0)+coalesce(set3_reps,0)+
    coalesce(set4_reps,0)+coalesce(set5_reps,0) as total_reps
  from workout.workout_log
  where status = 'done'
),
prev as (
  select
    d.*,
    lag(total_reps) over w as prev_total,
    lag(weight_kg)  over w as prev_weight
  from done d
  window w as (partition by lower(exercise) order by workout_date asc, created_at asc, workout_log_id asc)
)
select
  workout_log_id::text as id,
  workout_id::text     as session_id,
  exercise,
  workout_date,
  weight_kg,
  set1_reps, set2_reps, set3_reps, set4_reps, set5_reps,
  created_at,
  total_reps,
  case
    when prev_total is not null and weight_kg is not distinct from prev_weight
    then total_reps - prev_total
  end as delta
from prev;

commit;
