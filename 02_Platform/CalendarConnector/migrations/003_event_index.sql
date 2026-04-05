-- CalendarConnector Sprint03-Edit and Delete: event index table
-- Maps Atlas event identity (atlas_event_id) to Google Calendar event identity (google_event_id).
-- This is a lookup index, not a full event store.
-- Deleted rows are retained with status='deleted'. Hard deletes are never performed.
-- Uses CREATE TABLE IF NOT EXISTS for idempotency (consistent with 001_init.sql and 002_write_capability.sql).

BEGIN;

CREATE TABLE IF NOT EXISTS calendar_event_index (
    id                SERIAL       PRIMARY KEY,
    atlas_event_id    TEXT         NOT NULL UNIQUE,
    -- Stable Atlas-side identifier. UNIQUE enforces one index row per Atlas event identity.
    google_event_id   TEXT         NOT NULL,
    -- Google Calendar event id at time of last successful create or reactivation.
    calendar_id       TEXT         NOT NULL,
    -- Fixed to the operator-configured Chronos-Dates calendar id.
    status            TEXT         NOT NULL DEFAULT 'active',
    -- Valid values: 'active' | 'deleted' | 'error'
    -- 'active'  — mapping is live and usable for update/delete resolution
    -- 'deleted' — event was deleted (or confirmed absent during delete); row retained for audit
    -- 'error'   — Google event found missing during a PATCH; requires operator attention
    last_success_at   TIMESTAMPTZ,
    -- Populated on successful create or reactivation. NULL if never successfully created.
    last_error        TEXT,
    -- Populated when status='error' or when delete records a note about remote absence.
    -- NULL when status='active'.
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMIT;
