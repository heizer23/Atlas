begin;

-- Per-set timing, captured from the active-workout screen (P1.5/P2).
--   setN_started_at : user tapped the set to begin it (NULL = forgotten tap / not measured)
--   setN_ended_at   : user tapped the set's checkmark (confirmation)
-- Both come from the SERVER clock. No timestamp is ever estimated or stored on the user's behalf:
-- legacy rows and sets confirmed without a start tap simply have NULLs.
-- A set is "performed" when its reps are persisted; reps are persisted only by a confirmation
-- in the active workout (or by the explicit past-session edit flow).
alter table workout.workout_log
  add column if not exists set1_started_at timestamptz null,
  add column if not exists set1_ended_at   timestamptz null,
  add column if not exists set2_started_at timestamptz null,
  add column if not exists set2_ended_at   timestamptz null,
  add column if not exists set3_started_at timestamptz null,
  add column if not exists set3_ended_at   timestamptz null,
  add column if not exists set4_started_at timestamptz null,
  add column if not exists set4_ended_at   timestamptz null,
  add column if not exists set5_started_at timestamptz null,
  add column if not exists set5_ended_at   timestamptz null;

alter table workout.workout_log drop constraint if exists ck_set_timing_order;
alter table workout.workout_log
  add constraint ck_set_timing_order check (
    (set1_started_at is null or set1_ended_at is null or set1_ended_at >= set1_started_at) and
    (set2_started_at is null or set2_ended_at is null or set2_ended_at >= set2_started_at) and
    (set3_started_at is null or set3_ended_at is null or set3_ended_at >= set3_started_at) and
    (set4_started_at is null or set4_ended_at is null or set4_ended_at >= set4_started_at) and
    (set5_started_at is null or set5_ended_at is null or set5_ended_at >= set5_started_at)
  );

-- Client IANA time zone, taken from the browser when the workout is started
-- (time-of-day analysis stays correct when travelling). NULL for legacy sessions.
alter table workout.workout_session
  add column if not exists tz text null;

commit;

-- Rollback (additive migration; the previous application version ignores these columns):
--   alter table workout.workout_log drop constraint ck_set_timing_order;
--   alter table workout.workout_log drop column set1_started_at, ... set5_ended_at;
--   alter table workout.workout_session drop column tz;
