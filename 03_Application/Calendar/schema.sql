-- Calendar application schema — loaded idempotently at startup.
-- Source: Sprint01_Core/10_schema.sql

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

    CONSTRAINT calendar_events_start_before_end CHECK (start_at < end_at),

    CONSTRAINT calendar_events_source_consistency
        CHECK (
            (source_object_type IS NULL AND source_object_id IS NULL)
            OR (source_object_type IS NOT NULL AND source_object_id IS NOT NULL)
        )
);

CREATE INDEX IF NOT EXISTS idx_calendar_events_start_at
    ON calendar_events (start_at ASC);
