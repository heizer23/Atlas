BEGIN;

CREATE SCHEMA IF NOT EXISTS workout;

CREATE TABLE IF NOT EXISTS workout.workout_log (
  workout_log_id bigserial primary key,
  workout_id     uuid not null,

  workout_date   date not null,
  split          text not null,
  exercise       text not null,
  weight_kg      numeric(10,3) null,
  pause_sec      integer null,

  set1_reps      integer null,
  set2_reps      integer null,
  set3_reps      integer null,
  set4_reps      integer null,
  set5_reps      integer null,

  comment        text null,

  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),

  constraint ck_weight_nonneg check (weight_kg is null or weight_kg >= 0),
  constraint ck_pause_nonneg  check (pause_sec is null or pause_sec >= 0),

  constraint ck_set_reps_nonneg check (
    (set1_reps is null or set1_reps >= 0) and
    (set2_reps is null or set2_reps >= 0) and
    (set3_reps is null or set3_reps >= 0) and
    (set4_reps is null or set4_reps >= 0) and
    (set5_reps is null or set5_reps >= 0)
  ),

  constraint ck_at_least_one_set check (
    set1_reps is not null or
    set2_reps is not null or
    set3_reps is not null or
    set4_reps is not null or
    set5_reps is not null
  )
);

CREATE INDEX IF NOT EXISTS ix_workout_log_date
  ON workout.workout_log(workout_date);

CREATE INDEX IF NOT EXISTS ix_workout_log_exercise
  ON workout.workout_log(exercise);

CREATE INDEX IF NOT EXISTS ix_workout_log_split
  ON workout.workout_log(split);

CREATE INDEX IF NOT EXISTS ix_workout_log_workout_id
  ON workout.workout_log(workout_id);

COMMIT;
