-- Sprint09 schema additions — idempotent
-- Applied to the running DB via schema.sql at startup;
-- New deployments use migrations/009_scheduled_status.sql.

-- Expand status CHECK constraint to include 'scheduled'
ALTER TABLE tasktracker.tasks
    DROP CONSTRAINT IF EXISTS tasks_status_check;

ALTER TABLE tasktracker.tasks
    ADD CONSTRAINT tasks_status_check
        CHECK (status IN ('open', 'in_progress', 'scheduled', 'pending', 'done'));

-- Add scheduled_at column (timestamptz, nullable)
ALTER TABLE tasktracker.tasks
    ADD COLUMN IF NOT EXISTS scheduled_at timestamptz;

-- Partial index on scheduled tasks for efficient promotion and view queries
CREATE INDEX IF NOT EXISTS ix_tasks_scheduled_at
    ON tasktracker.tasks(scheduled_at)
    WHERE status = 'scheduled';
