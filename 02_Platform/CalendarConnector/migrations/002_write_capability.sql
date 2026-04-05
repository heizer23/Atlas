-- CalendarConnector Sprint02-Writing Skill: write capability additions
-- Adds calendar_decision_log table for audit persistence on all write attempts.
-- Uses CREATE TABLE IF NOT EXISTS for idempotency (consistent with 001_init.sql).

BEGIN;

-- Audit log for every calendar event create attempt.
-- Written for both successes and failures.
-- Write is best-effort: a failure to insert here must not fail the create operation.
CREATE TABLE IF NOT EXISTS calendar_decision_log (
    id                 SERIAL       PRIMARY KEY,
    operation          TEXT         NOT NULL,
    -- operation values: 'calendar_event_create'
    requested_at       TIMESTAMPTZ  NOT NULL,
    target_calendar_id TEXT         NOT NULL,
    outcome            TEXT         NOT NULL,
    -- outcome values: 'success' | 'failure'
    google_event_id    TEXT,
    -- populated on success; NULL on failure
    error_summary      TEXT,
    -- populated on failure; NULL on success
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMIT;
