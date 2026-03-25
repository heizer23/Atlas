-- Notifications platform schema
-- Owned by: 02_Platform/Notifications
-- Do not add application-specific columns here.

CREATE SCHEMA IF NOT EXISTS notifications;

CREATE TABLE IF NOT EXISTS notifications.notification (
    id          UUID        PRIMARY KEY,
    source      TEXT        NOT NULL,
    fire_at     TIMESTAMPTZ NOT NULL,
    title       TEXT        NOT NULL,
    body        TEXT        NOT NULL,
    label       TEXT        NOT NULL,
    deep_link   TEXT        NOT NULL,
    fcm_token   TEXT        NOT NULL,
    status      TEXT        NOT NULL CHECK (status IN ('pending', 'dispatched', 'cancelled', 'failed')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for the dispatch job query: WHERE status = 'pending' AND fire_at <= NOW()
CREATE INDEX IF NOT EXISTS notification_dispatch_idx
    ON notifications.notification (status, fire_at);

-- Single-row device registry (MVP: one device per device_id key).
-- Device registration table is intentionally minimal for this slice.
CREATE TABLE IF NOT EXISTS notifications.device (
    device_id   TEXT        PRIMARY KEY,
    fcm_token   TEXT        NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
