BEGIN;

-- Add 'pending' as a valid task status.
-- Drop the existing check constraint and recreate it with the expanded set.
ALTER TABLE tasktracker.tasks DROP CONSTRAINT IF EXISTS tasks_status_check;
ALTER TABLE tasktracker.tasks DROP CONSTRAINT IF EXISTS tasks_status_check1;

ALTER TABLE tasktracker.tasks ADD CONSTRAINT tasks_status_check
    CHECK (status IN ('open', 'in_progress', 'pending', 'done'));

COMMIT;
