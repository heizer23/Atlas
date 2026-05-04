"""
Tests for Sprint09_ScheduledStatus — TaskTracker
Covers: view=scheduled, auto-promotion, validation rules, PATCH scheduled_at semantics.
Scenario names match 10_test_spec.md for traceability.

These tests run in the atlas-tasktracker-test container alongside PersonalDevelopment tests.
The conftest (from PersonalDevelopment) provides db_conn, client, and clean_tables fixtures.
Each test creates its own data on top of a clean (truncated) table — no dependency on
fixtures.sql contents.
"""

import uuid
import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_rows(response) -> list[dict]:
    data = response.json()
    return data.get("rows", [])


def insert_task(db_conn, task_id: str, title: str, status: str, priority: str = "medium",
                scheduled_at: str | None = None) -> None:
    """Insert a task directly into the DB for test setup."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            insert into tasktracker.tasks (id, title, status, priority, scheduled_at)
            values (%s, %s, %s, %s, %s)
            """,
            (task_id, title, status, priority, scheduled_at),
        )


# ── Scenario: Scheduled view returns scheduled tasks ordered by scheduled_at ASC ──

def test_scheduled_view_returns_scheduled_tasks_ordered_asc(client, db_conn):
    """view=scheduled returns only scheduled tasks, sorted by scheduled_at ASC."""
    id_a = str(uuid.uuid4())
    id_b = str(uuid.uuid4())
    # Task A: scheduled 14 days from now
    insert_task(db_conn, id_a, "task-A-later", "scheduled", scheduled_at="2099-02-01")
    # Task B: scheduled 7 days from now (earlier)
    insert_task(db_conn, id_b, "task-B-sooner", "scheduled", scheduled_at="2099-01-01")

    r = client.get("/api/tasks?view=scheduled")
    assert r.status_code == 200
    rows = get_rows(r)

    titles = [row["title"] for row in rows]
    # B (sooner) must come before A (later)
    assert "task-B-sooner" in titles
    assert "task-A-later" in titles
    assert titles.index("task-B-sooner") < titles.index("task-A-later"), \
        "Rows not ordered by scheduled_at ASC"

    statuses = {row["status"] for row in rows}
    assert statuses <= {"scheduled"}, f"Non-scheduled rows present: {statuses}"


# ── Scenario: Scheduled view returns empty Dataset when no scheduled tasks exist ──

def test_scheduled_view_empty_when_no_scheduled_tasks(client, db_conn):
    """view=scheduled returns empty Dataset when no scheduled tasks exist."""
    # Clean slate — conftest already truncated; no scheduled tasks inserted
    r = client.get("/api/tasks?view=scheduled")
    assert r.status_code == 200
    data = r.json()
    assert data["rows"] == []
    assert data["meta"]["total"] == 0


# ── Scenario: Auto-promotion promotes past-due scheduled task on active view fetch ──

def test_auto_promotion_promotes_past_due_task(client, db_conn):
    """A scheduled task with scheduled_at in the past is promoted to in_progress on view=active fetch."""
    task_id = str(uuid.uuid4())
    # scheduled_at = yesterday
    insert_task(db_conn, task_id, "past-due-task", "scheduled",
                scheduled_at="2000-01-01")

    # Fetch active view — triggers auto-promotion
    r = client.get("/api/tasks?view=active")
    assert r.status_code == 200

    # Verify the task is now in_progress
    with db_conn.cursor() as cur:
        cur.execute("select status from tasktracker.tasks where id = %s", (task_id,))
        row = cur.fetchone()
    assert row["status"] == "in_progress", f"Expected in_progress, got {row['status']}"


# ── Scenario: Auto-promotion does not promote future scheduled task on active view fetch ──

def test_auto_promotion_does_not_promote_future_task(client, db_conn):
    """A scheduled task with scheduled_at in the future is NOT promoted on view=active fetch."""
    task_id = str(uuid.uuid4())
    insert_task(db_conn, task_id, "future-task", "scheduled",
                scheduled_at="2099-12-31")

    client.get("/api/tasks?view=active")

    with db_conn.cursor() as cur:
        cur.execute("select status from tasktracker.tasks where id = %s", (task_id,))
        row = cur.fetchone()
    assert row["status"] == "scheduled", f"Expected scheduled, got {row['status']}"


# ── Scenario: Active view excludes future scheduled tasks ──

def test_active_view_excludes_future_scheduled_tasks(client, db_conn):
    """view=active response does not include future-scheduled tasks."""
    task_id = str(uuid.uuid4())
    insert_task(db_conn, task_id, "exclude-scheduled", "scheduled",
                scheduled_at="2099-12-31")

    r = client.get("/api/tasks?view=active")
    assert r.status_code == 200
    ids = {row["id"] for row in get_rows(r)}
    assert task_id not in ids, "Future scheduled task incorrectly appeared in active view"


# ── Scenario: Create task with status=scheduled and scheduled_at succeeds ──

def test_create_task_with_scheduled_status_and_scheduled_at(client):
    """POST with status=scheduled and a future scheduled_at creates the task successfully."""
    r = client.post("/api/tasks", json={
        "title": "Plan review",
        "status": "scheduled",
        "scheduled_at": "2099-01-01",
    })
    assert r.status_code == 200, r.text
    rows = get_rows(r)
    assert len(rows) == 1
    assert rows[0]["status"] == "scheduled"
    assert rows[0]["scheduled_at"] is not None


# ── Scenario: Create task with status=scheduled and missing scheduled_at returns 400 ──

def test_create_task_scheduled_without_scheduled_at_returns_400(client):
    """POST with status=scheduled and no scheduled_at returns 400 VALIDATION_ERROR."""
    r = client.post("/api/tasks", json={
        "title": "Plan review",
        "status": "scheduled",
    })
    assert r.status_code == 400, r.text
    data = r.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"


# ── Scenario: PATCH task to scheduled status with scheduled_at succeeds ──

def test_patch_task_to_scheduled_with_scheduled_at(client, db_conn):
    """PATCH sets status=scheduled with a valid scheduled_at on an open task."""
    task_id = str(uuid.uuid4())
    insert_task(db_conn, task_id, "open-task-to-schedule", "open")

    r = client.patch(
        f"/api/tasks/{task_id}",
        json={"status": "scheduled", "scheduled_at": "2099-06-01"},
    )
    assert r.status_code == 200, r.text
    rows = get_rows(r)
    assert rows[0]["status"] == "scheduled"
    assert rows[0]["scheduled_at"] is not None


# ── Scenario: PATCH clears scheduled_at when status changes away from scheduled (explicit null) ──

def test_patch_clears_scheduled_at_when_status_changes_away(client, db_conn):
    """PATCH with status=open and scheduled_at=null clears the scheduled_at field."""
    task_id = str(uuid.uuid4())
    insert_task(db_conn, task_id, "scheduled-to-clear", "scheduled",
                scheduled_at="2099-01-01")

    r = client.patch(
        f"/api/tasks/{task_id}",
        json={"status": "open", "scheduled_at": None},
    )
    assert r.status_code == 200, r.text
    rows = get_rows(r)
    assert rows[0]["status"] == "open"
    assert rows[0]["scheduled_at"] is None


# ── Scenario: Create task with scheduled_at provided but non-scheduled status is accepted ──

def test_create_task_with_scheduled_at_and_non_scheduled_status(client):
    """POST with status=open and a scheduled_at is accepted and stored."""
    r = client.post("/api/tasks", json={
        "title": "Note with future ref",
        "status": "open",
        "scheduled_at": "2099-03-15",
    })
    assert r.status_code == 200, r.text
    rows = get_rows(r)
    assert rows[0]["status"] == "open"
    assert rows[0]["scheduled_at"] is not None
