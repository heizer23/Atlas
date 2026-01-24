begin;

-- Domain schema (inside database "atlas")
create schema if not exists workout;

create table if not exists workout.workout_log (
  workout_log_id bigserial primary key,

  -- Your required fields
  workout_date   date not null,
  split          text not null,        -- e.g. Pull / Push / HotelPull
  exercise       text not null,        -- e.g. Benchpress
  weight_kg      numeric(10,3) null,
  pause_sec      integer null,

  set1_reps      integer null,
  set2_reps      integer null,
  set3_reps      integer null,
  set4_reps      integer null,
  set5_reps      integer null,

  comment        text null,

  -- Atlas audit facts (still useful, even if everything is Atlas)
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),

  -- Constraints (loud, but not annoying)
  constraint ck_weight_nonneg check (weight_kg is null or weight_kg >= 0),
  constraint ck_pause_nonneg  check (pause_sec is null or pause_sec >= 0),

  constraint ck_set_reps_nonneg check (
    (set1_reps is null or set1_reps >= 0) and
    (set2_reps is null or set2_reps >= 0) and
    (set3_reps is null or set3_reps >= 0) and
    (set4_reps is null or set4_reps >= 0) and
    (set5_reps is null or set5_reps >= 0)
  ),

  -- Prevent empty rows
  constraint ck_at_least_one_set check (
    set1_reps is not null or
    set2_reps is not null or
    set3_reps is not null or
    set4_reps is not null or
    set5_reps is not null
  )
);

-- Indexes for the obvious access paths
create index if not exists ix_workout_log_date
  on workout.workout_log(workout_date);

create index if not exists ix_workout_log_exercise
  on workout.workout_log(exercise);

create index if not exists ix_workout_log_split
  on workout.workout_log(split);

commit;
