-- Sprint01-Core: PersonalDevelopment schema extension
-- Adds learning domain columns to tasktracker.tasks (owned by TaskTracker).
-- Apply against the shared Atlas Postgres instance.
-- All statements are idempotent.

BEGIN;

-- task_type distinguishes normal tasks, training units (logical containers),
-- and training sessions (executable work sessions).
ALTER TABLE tasktracker.tasks
    ADD COLUMN IF NOT EXISTS task_type TEXT NOT NULL DEFAULT 'normal'
        CHECK (task_type IN ('normal', 'training_unit', 'training_session'));

-- parent_task_id links a training_session to its training_unit parent.
-- Controlled deviation: LinkingEngine does not support aggregations (max, count
-- across children), so a direct FK column is used instead.
-- ON DELETE SET NULL: deleting a parent does not cascade-delete children.
ALTER TABLE tasktracker.tasks
    ADD COLUMN IF NOT EXISTS parent_task_id UUID
        REFERENCES tasktracker.tasks(id) ON DELETE SET NULL;

-- actual_duration_minutes: user-maintained duration for training_session tasks.
ALTER TABLE tasktracker.tasks
    ADD COLUMN IF NOT EXISTS actual_duration_minutes INTEGER
        CHECK (actual_duration_minutes IS NULL OR actual_duration_minutes >= 0);

-- completed_at: set server-side by TaskTracker when status transitions to done.
-- Never supplied by the frontend.
ALTER TABLE tasktracker.tasks
    ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;

-- Index on task_type for efficient training_unit list queries and
-- training_unit exclusion on the main task list.
CREATE INDEX IF NOT EXISTS ix_tasks_task_type
    ON tasktracker.tasks(task_type);

-- Index on parent_task_id for efficient child-task lookups.
CREATE INDEX IF NOT EXISTS ix_tasks_parent_task_id
    ON tasktracker.tasks(parent_task_id);

COMMIT;
