"""
Database access layer for calendar_connection, calendar_token, and calendar_oauth_state tables.

All DB reads and writes for this component go through this module.
No token values are returned in API responses — this module returns raw dicts
for internal use only; the router layer is responsible for omitting sensitive fields.
"""
import logging
from typing import Optional

import psycopg2.extensions

log = logging.getLogger("calendar_connector")


def get_connection(conn: psycopg2.extensions.connection) -> Optional[dict]:
    """Return the single calendar_connection row as a dict, or None if absent."""
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM calendar_connection ORDER BY id LIMIT 1")
        return cur.fetchone()


def upsert_connection(
    conn: psycopg2.extensions.connection,
    provider: str,
    account_email: Optional[str],
    status: str,
    granted_scopes: str,
) -> int:
    """Insert or update the calendar_connection row. Return the connection id.

    Atlas is system-scoped (one connection per instance). This upserts by treating
    the table as a singleton: update the existing row if one exists, insert otherwise.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM calendar_connection ORDER BY id LIMIT 1")
        existing = cur.fetchone()

        if existing:
            cur.execute(
                """
                UPDATE calendar_connection
                   SET provider       = %s,
                       account_email  = %s,
                       status         = %s,
                       granted_scopes = %s,
                       updated_at     = NOW(),
                       last_error     = NULL
                 WHERE id = %s
                RETURNING id
                """,
                (provider, account_email, status, granted_scopes, existing["id"]),
            )
            row = cur.fetchone()
            conn.commit()
            return row["id"]
        else:
            cur.execute(
                """
                INSERT INTO calendar_connection
                    (provider, account_email, status, granted_scopes)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (provider, account_email, status, granted_scopes),
            )
            row = cur.fetchone()
            conn.commit()
            return row["id"]


def update_connection_status(
    conn: psycopg2.extensions.connection,
    status: str,
    last_error: Optional[str],
) -> None:
    """Update status and last_error on the calendar_connection row. Update updated_at."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE calendar_connection
               SET status     = %s,
                   last_error = %s,
                   updated_at = NOW()
             WHERE id = (SELECT id FROM calendar_connection ORDER BY id LIMIT 1)
            """,
            (status, last_error),
        )
    conn.commit()


def record_success(conn: psycopg2.extensions.connection) -> None:
    """Update last_success_at and updated_at on the calendar_connection row."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE calendar_connection
               SET last_success_at = NOW(),
                   updated_at      = NOW()
             WHERE id = (SELECT id FROM calendar_connection ORDER BY id LIMIT 1)
            """
        )
    conn.commit()


def get_token(conn: psycopg2.extensions.connection) -> Optional[dict]:
    """Return the calendar_token row as a dict (including access_token, refresh_token,
    token_expiry), or None if absent.

    Internal use only — callers must never forward token values to API responses.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT t.*
              FROM calendar_token t
              JOIN calendar_connection c ON t.connection_id = c.id
             ORDER BY c.id
             LIMIT 1
            """
        )
        return cur.fetchone()


def upsert_token(
    conn: psycopg2.extensions.connection,
    connection_id: int,
    access_token: str,
    refresh_token: Optional[str],
    token_expiry: str,
    token_type: Optional[str],
    scope: Optional[str],
) -> None:
    """Insert or update the calendar_token row for the given connection_id."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO calendar_token
                (connection_id, access_token, refresh_token, token_expiry, token_type, scope)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (connection_id) DO UPDATE
               SET access_token  = EXCLUDED.access_token,
                   refresh_token = COALESCE(EXCLUDED.refresh_token, calendar_token.refresh_token),
                   token_expiry  = EXCLUDED.token_expiry,
                   token_type    = EXCLUDED.token_type,
                   scope         = EXCLUDED.scope,
                   updated_at    = NOW()
            """,
            (connection_id, access_token, refresh_token, token_expiry, token_type, scope),
        )
    conn.commit()


def create_oauth_state(
    conn: psycopg2.extensions.connection,
    nonce: str,
    expires_at: str,
) -> None:
    """Insert a new calendar_oauth_state row with the given nonce and expiry."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO calendar_oauth_state (nonce, expires_at) VALUES (%s, %s)",
            (nonce, expires_at),
        )
    conn.commit()


def consume_oauth_state(
    conn: psycopg2.extensions.connection,
    nonce: str,
) -> bool:
    """Delete the calendar_oauth_state row if it exists and has not expired.

    Returns True if the nonce was found and deleted (valid, one-time use).
    Returns False if not found or expired.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM calendar_oauth_state
             WHERE nonce = %s
               AND expires_at > NOW()
            RETURNING id
            """,
            (nonce,),
        )
        deleted = cur.fetchone()
    conn.commit()
    return deleted is not None
