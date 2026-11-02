begin;

-- Lighter movement days (running, stretching, mobility) that have no workout_log rows.
-- Strength days are NOT copied here: they are derived from finished workout_log sessions,
-- so edits and deletions of sessions always recalculate statistics. One row per (date, kind).
create table if not exists workout.activity_day (
  activity_date date        not null,
  kind          text        not null,
  created_at    timestamptz not null default now(),

  primary key (activity_date, kind),
  constraint ck_activity_day_kind check (kind in ('running', 'stretching', 'mobility'))
);

commit;
