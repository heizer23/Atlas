BEGIN;

ALTER TABLE tasktracker.tasks ADD COLUMN IF NOT EXISTS effort_hours double precision;

ALTER TABLE tasktracker.tasks ADD CONSTRAINT tasks_effort_hours_non_negative
    CHECK (effort_hours IS NULL OR effort_hours >= 0);

COMMIT;
