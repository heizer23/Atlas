-- Undo scripts/backfill_activity_days.sql: removes only rows marked source = 'import'.
delete from workout.activity_day where source = 'import';
