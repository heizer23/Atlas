-- CalendarConnector initial schema
-- Atlas is system-scoped: no user_id FK on any table.
-- Token fields are stored plaintext for this slice — known security gap, see architecture.json risks.

BEGIN;

-- Represents a Google Calendar authorization connection for this Atlas instance.
-- One row per Atlas instance (system-scoped).
CREATE TABLE IF NOT EXISTS calendar_connection (
    id               SERIAL       PRIMARY KEY,
    provider         TEXT         NOT NULL DEFAULT 'google',
    account_email    TEXT,
    status           TEXT         NOT NULL DEFAULT 'connected',
    -- status values: connected | expired | revoked | error
    granted_scopes   TEXT         NOT NULL DEFAULT '',
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_success_at  TIMESTAMPTZ,
    last_error       TEXT
);

-- Stores the OAuth tokens for the calendar connection.
-- One row per calendar_connection row.
-- SECURITY GAP: access_token and refresh_token stored as plaintext.
CREATE TABLE IF NOT EXISTS calendar_token (
    id               SERIAL       PRIMARY KEY,
    connection_id    INTEGER      NOT NULL REFERENCES calendar_connection(id) ON DELETE CASCADE,
    access_token     TEXT         NOT NULL,
    refresh_token    TEXT,
    token_expiry     TIMESTAMPTZ  NOT NULL,
    token_type       TEXT,
    scope            TEXT,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (connection_id)
);

-- Short-lived CSRF nonce for the OAuth state parameter.
-- One row per in-flight connect flow; deleted on callback consumption.
CREATE TABLE IF NOT EXISTS calendar_oauth_state (
    id               SERIAL       PRIMARY KEY,
    nonce            TEXT         NOT NULL UNIQUE,
    expires_at       TIMESTAMPTZ  NOT NULL,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMIT;
