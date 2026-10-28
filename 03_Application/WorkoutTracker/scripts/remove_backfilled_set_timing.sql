-- Undo scripts/backfill_set_timing.sql: clear set timing on LEGACY rows only (sessions without a
-- workout_session row). Timing of sessions started from the app is never touched.
--
-- Run:  docker exec -i atlas-postgres psql -U atlas -d atlas -v ON_ERROR_STOP=1 < this_file

begin;

update workout.workout_log l set
  set1_started_at = null, set1_ended_at = null, set2_started_at = null, set2_ended_at = null,
  set3_started_at = null, set3_ended_at = null, set4_started_at = null, set4_ended_at = null,
  set5_started_at = null, set5_ended_at = null
where not exists (select 1 from workout.workout_session s where s.workout_id = l.workout_id);

commit;
