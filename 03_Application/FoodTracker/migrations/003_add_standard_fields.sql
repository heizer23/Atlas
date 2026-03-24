-- Sprint 04: Add standard, source_standard_id, and alcohol_g to foodtracker.food_logs.
-- Safe to run on an already-migrated database (uses ADD COLUMN IF NOT EXISTS).

BEGIN;

ALTER TABLE foodtracker.food_logs
    ADD COLUMN IF NOT EXISTS standard          BOOLEAN      NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS source_standard_id UUID         NULL,
    ADD COLUMN IF NOT EXISTS alcohol_g         NUMERIC(7,1) NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_food_logs_source_standard_id
    ON foodtracker.food_logs (source_standard_id);

COMMIT;
