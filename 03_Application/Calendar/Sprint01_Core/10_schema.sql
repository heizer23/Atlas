-- Calendar application schema
-- Component: 03_Application/Calendar
-- Sprint: Sprint01_Core
-- Owned by: Calendar application (private state — not a shared cross-application contract)

-- Migration 001: initial calendar_events table

CREATE TABLE IF NOT EXISTS calendar_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title               TEXT NOT NULL,
    start_at            TIMESTAMPTZ NOT NULL,
    end_at              TIMESTAMPTZ NOT NULL,
    event_type          TEXT NOT NULL CHECK (event_type IN ('task_block', 'personal_block', 'blocker')),
    source_object_type  TEXT CHECK (source_object_type IN ('task') OR source_object_type IS NULL),
    source_object_id    TEXT,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Enforce start before end at DB level as a belt-and-braces check
    -- (business logic in application layer is the primary enforcement)
    CONSTRAINT calendar_events_start_before_end CHECK (start_at < end_at),

    -- Source object fields must either both be set or both be null
    CONSTRAINT calendar_events_source_consistency
        CHECK (
            (source_object_type IS NULL AND source_object_id IS NULL)
            OR (source_object_type IS NOT NULL AND source_object_id IS NOT NULL)
        )
);

-- Index for time-range queries (the primary UI access pattern)
CREATE INDEX IF NOT EXISTS idx_calendar_events_start_at
    ON calendar_events (start_at ASC);
