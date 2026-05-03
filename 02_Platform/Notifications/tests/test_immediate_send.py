"""
Integration tests for POST /api/notifications/send (Sprint01_Immediate_Notify).

Scenarios from 10_test_spec.md:
  1. Happy path: immediate send succeeds
  2. Happy path: explicit source field
  3. Error: no default device registered
  4. Error: FCM dispatch fails
  5. Validation: missing required fields

FCM is mocked at send_fcm_message to avoid real Firebase calls.
Tests hit the atlas_test Postgres database via the live service pool.
"""

from unittest.mock import patch

import psycopg2.extras
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_device(db_conn, token: str = "fake-fcm-token-abc123") -> None:
    """Insert a default device row so the endpoint can resolve the token."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO notifications.device (device_id, fcm_token, updated_at)
            VALUES ('default', %s, NOW())
            ON CONFLICT (device_id) DO UPDATE
                SET fcm_token = EXCLUDED.fcm_token, updated_at = NOW()
            """,
            (token,),
        )


def _fetch_notification(db_conn, notification_id: str) -> dict | None:
    """Fetch a notification row by id from the test database."""
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM notifications.notification WHERE id = %s",
            (notification_id,),
        )
        return cur.fetchone()


# ---------------------------------------------------------------------------
# Scenario 1: Happy path — immediate send succeeds
# ---------------------------------------------------------------------------

def test_immediate_send_happy_path(client, db_conn):
    """POST /api/notifications/send returns 200 with correct response shape
    and persists an audit record with status=dispatched."""
    _seed_device(db_conn)

    with patch("backend.service.send_fcm_message", return_value="projects/x/messages/fake-id"):
        resp = client.post(
            "/api/notifications/send",
            json={"title": "Decision needed", "body": "Waiting on your input."},
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Response shape
    assert "id" in data
    assert data["title"] == "Decision needed"
    assert data["body"] == "Waiting on your input."
    assert "dispatched_at" in data
    assert "fcm_token" not in data

    # Audit record in Postgres
    row = _fetch_notification(db_conn, data["id"])
    assert row is not None, "No notification row written to Postgres"
    assert row["status"] == "dispatched"
    assert row["source"] == "claude"  # default source
    assert row["fire_at"] is None
    assert row["label"] == ""
    assert row["deep_link"] == ""


# ---------------------------------------------------------------------------
# Scenario 2: Happy path — explicit source field
# ---------------------------------------------------------------------------

def test_immediate_send_explicit_source(client, db_conn):
    """POST /api/notifications/send with explicit source stores it in the record."""
    _seed_device(db_conn)

    with patch("backend.service.send_fcm_message", return_value="projects/x/messages/fake-id"):
        resp = client.post(
            "/api/notifications/send",
            json={"title": "Alert", "body": "Check this.", "source": "atlas_shell"},
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    row = _fetch_notification(db_conn, data["id"])
    assert row is not None
    assert row["source"] == "atlas_shell"


# ---------------------------------------------------------------------------
# Scenario 3: Error — no default device registered
# ---------------------------------------------------------------------------

def test_immediate_send_no_device(client, db_conn):
    """POST /api/notifications/send returns 503 with NO_DEFAULT_DEVICE
    when no device row exists for device_id='default'."""
    # clean_tables fixture already emptied notifications.device

    resp = client.post(
        "/api/notifications/send",
        json={"title": "Hi", "body": "There"},
    )

    assert resp.status_code == 503, resp.text
    body = resp.json()
    assert body["error"]["code"] == "NO_DEFAULT_DEVICE"

    # No notification row should have been written
    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM notifications.notification")
        row = cur.fetchone()
    assert row["n"] == 0


# ---------------------------------------------------------------------------
# Scenario 4: Error — FCM dispatch fails
# ---------------------------------------------------------------------------

def test_immediate_send_fcm_failure(client, db_conn):
    """POST /api/notifications/send returns 502 with FCM_DISPATCH_FAILED
    when send_fcm_message raises. No notification row is written."""
    _seed_device(db_conn)

    with patch(
        "backend.service.send_fcm_message",
        side_effect=Exception("FCM connection timeout"),
    ):
        resp = client.post(
            "/api/notifications/send",
            json={"title": "Hi", "body": "There"},
        )

    assert resp.status_code == 502, resp.text
    body = resp.json()
    assert body["error"]["code"] == "FCM_DISPATCH_FAILED"

    # No notification row should have been written
    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM notifications.notification")
        row = cur.fetchone()
    assert row["n"] == 0


# ---------------------------------------------------------------------------
# Scenario 5: Validation — missing required fields
# ---------------------------------------------------------------------------

def test_immediate_send_missing_body_field(client, db_conn):
    """POST /api/notifications/send with missing 'body' returns 422.
    No FCM call is made and no notification row is written."""
    _seed_device(db_conn)

    with patch("backend.service.send_fcm_message") as mock_fcm:
        resp = client.post(
            "/api/notifications/send",
            json={"title": "Hi"},  # body is missing
        )
        mock_fcm.assert_not_called()

    assert resp.status_code == 422, resp.text

    # No notification row should have been written
    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM notifications.notification")
        row = cur.fetchone()
    assert row["n"] == 0
