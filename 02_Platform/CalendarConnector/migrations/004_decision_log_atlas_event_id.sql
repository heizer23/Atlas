-- CalendarConnector Sprint03-Edit and Delete: add atlas_event_id to calendar_decision_log
-- Adds the atlas_event_id column to calendar_decision_log so that update and delete log entries
-- carry Atlas event identity even when google_event_id is unavailable (e.g., EVENT_NOT_FOUND path).
-- Column is nullable: Sprint02 create entries will have NULL for atlas_event_id.
-- Uses ADD COLUMN IF NOT EXISTS for idempotency (consistent with prior migrations).

BEGIN;

ALTER TABLE calendar_decision_log
    ADD COLUMN IF NOT EXISTS atlas_event_id TEXT;
-- Nullable. Populated on all Sprint03 update and delete attempts.
-- NULL for Sprint02 create entries (backward-compatible).

COMMIT;
