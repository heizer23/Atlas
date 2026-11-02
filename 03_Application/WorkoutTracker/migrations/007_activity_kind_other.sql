begin;

-- Allow a free-form "other" light activity (e.g. skiing); it counts like any other activity day.
alter table workout.activity_day drop constraint if exists ck_activity_day_kind;
alter table workout.activity_day
  add constraint ck_activity_day_kind check (kind in ('running', 'stretching', 'mobility', 'other'));

commit;
