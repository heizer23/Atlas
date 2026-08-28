"""
Calendar — pytest test functions.

Traceability: each function name maps to a scenario in 10_test_spec.md.
Tests run against the atlas_test database with fixtures loaded by conftest.
"""

# ── Fixture IDs (stable references to fixtures.sql) ───────────────────────────
MORNING_ID   = "f0000001-0000-0000-0000-000000000000"
TASK_LNK_ID  = "f0000002-0000-0000-0000-000000000000"
PERSONAL_ID  = "f0000003-0000-0000-0000-000000000000"
MISSING_ID   = "00000000-0000-0000-0000-000000000000"


# ── List events ───────────────────────────────────────────────────────────────

def test_list_events_returns_dataset(client):
    """Scenario: List events returns Dataset."""
    r = client.get("/api/cal/events")
    assert r.status_code == 200
    body = r.json()
    assert body["meta"]["object_type"] == "calendar_event"
    assert isinstance(body["rows"], list)
    assert body["meta"]["total"] >= 1
    row = body["rows"][0]
    for field in ("id", "title", "start_at", "end_at", "event_type"):
        assert field in row


def test_list_events_empty(client, db_conn):
    """Scenario: List events when no events exist returns empty Dataset."""
    with db_conn.cursor() as cur:
        cur.execute("TRUNCATE calendar_events")

    r = client.get("/api/cal/events")
    assert r.status_code == 200
    body = r.json()
    assert body["rows"] == []
    assert body["meta"]["total"] == 0


def test_list_events_with_date_window_filter(client):
    """Scenario: List events with date window filter."""
    # Fixtures are all in January 2026; filter to first 6 days — only Morning (Jan 5)
    r = client.get("/api/cal/events?start=2026-01-05T00:00:00Z&end=2026-01-06T00:00:00Z")
    assert r.status_code == 200
    body = r.json()
    ids = [row["id"] for row in body["rows"]]
    assert MORNING_ID in ids
    # Task linked block (Jan 6 14:00) and Personal block (Jan 7) must not appear
    assert TASK_LNK_ID not in ids
    assert PERSONAL_ID not in ids


# ── Create ────────────────────────────────────────────────────────────────────

def test_create_standalone_event(client):
    """Scenario: Create standalone calendar block."""
    payload = {
        "title": "Standup",
        "start_at": "2026-05-10T09:00:00Z",
        "end_at": "2026-05-10T09:30:00Z",
        "event_type": "personal_block",
    }
    r = client.post("/api/cal/events", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert len(body["rows"]) == 1
    row = body["rows"][0]
    assert row["title"] == "Standup"
    assert row["event_type"] == "personal_block"
    assert row["id"]  # non-empty
    assert row["source_object_id"] is None


def test_create_task_linked_event(client):
    """Scenario: Create calendar block linked to a task."""
    payload = {
        "title": "Work on Sprint",
        "start_at": "2026-05-10T10:00:00Z",
        "end_at": "2026-05-10T11:00:00Z",
        "event_type": "task_block",
        "source_object_type": "task",
        "source_object_id": "task-abc-123",
    }
    r = client.post("/api/cal/events", json=payload)
    assert r.status_code == 200
    body = r.json()
    row = body["rows"][0]
    assert row["source_object_type"] == "task"
    assert row["source_object_id"] == "task-abc-123"


def test_create_event_start_after_end_rejected(client):
    """Scenario: Create event where start_at >= end_at is rejected."""
    payload = {
        "title": "Bad",
        "start_at": "2026-05-10T11:00:00Z",
        "end_at": "2026-05-10T09:00:00Z",
        "event_type": "personal_block",
    }
    r = client.post("/api/cal/events", json=payload)
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "CALENDAR_VALIDATION_ERROR"


# ── PATCH ─────────────────────────────────────────────────────────────────────

def test_patch_event_updates_times(client):
    """Scenario: PATCH updates start_at and end_at."""
    r = client.patch(
        f"/api/cal/events/{MORNING_ID}",
        json={"start_at": "2026-05-10T08:00:00Z", "end_at": "2026-05-10T09:00:00Z"},
    )
    assert r.status_code == 200
    body = r.json()
    row = body["rows"][0]
    assert "2026-05-10" in row["start_at"]
    assert "2026-05-10" in row["end_at"]
    # Title should be unchanged
    assert row["title"] == "Morning Focus Block"


def test_patch_event_omit_preserves_fields(client):
    """Scenario: PATCH with omitted fields leaves them unchanged."""
    r = client.patch(
        f"/api/cal/events/{TASK_LNK_ID}",
        json={"title": "Renamed"},
    )
    assert r.status_code == 200
    body = r.json()
    row = body["rows"][0]
    assert row["title"] == "Renamed"
    # Notes should be preserved from fixture
    assert row["notes"] == "Working on sprint"


def test_patch_event_null_clears_notes(client):
    """Scenario: PATCH with explicit null clears notes."""
    r = client.patch(
        f"/api/cal/events/{TASK_LNK_ID}",
        json={"notes": None},
    )
    assert r.status_code == 200
    body = r.json()
    row = body["rows"][0]
    assert row["notes"] is None


# ── DELETE ────────────────────────────────────────────────────────────────────

def test_delete_event_success(client):
    """Scenario: Delete event returns empty Dataset."""
    r = client.delete(f"/api/cal/events/{PERSONAL_ID}")
    assert r.status_code == 200
    body = r.json()
    assert body["rows"] == []
    assert body["meta"]["total"] == 0

    # Subsequent list must not contain the deleted event
    r2 = client.get("/api/cal/events")
    ids = [row["id"] for row in r2.json()["rows"]]
    assert PERSONAL_ID not in ids


def test_delete_event_not_found(client):
    """Scenario: Delete non-existent event returns 404."""
    r = client.delete(f"/api/cal/events/{MISSING_ID}")
    assert r.status_code == 404
    body = r.json()
    assert body["error"]["code"] == "CALENDAR_EVENT_NOT_FOUND"


def test_delete_does_not_affect_task(client):
    """Scenario: Delete task-linked event completes cleanly (no cascade to task)."""
    r = client.delete(f"/api/cal/events/{TASK_LNK_ID}")
    # Must succeed — no FK constraint violation, no cascade error
    assert r.status_code == 200
    body = r.json()
    assert body["rows"] == []
