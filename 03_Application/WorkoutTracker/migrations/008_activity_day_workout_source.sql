begin;

-- Historic strength days imported as plain days (no exercises): kind 'workout'.
-- source separates hand-logged rows ('manual') from imported ones ('import') so an import can be undone.
alter table workout.activity_day drop constraint if exists ck_activity_day_kind;
alter table workout.activity_day
  add constraint ck_activity_day_kind check (kind in ('running', 'stretching', 'mobility', 'other', 'workout'));

alter table workout.activity_day add column if not exists source text not null default 'manual';
alter table workout.activity_day drop constraint if exists ck_activity_day_source;
alter table workout.activity_day
  add constraint ck_activity_day_source check (source in ('manual', 'import'));

commit;
