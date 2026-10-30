"""
Sprint11_TodayAndRecurrence — GET /api/tasks/agenda tests.

Scenario names match 10_test_spec.md ("Agenda — ...") for traceability.
Each test inserts its own rows (no dependency on fixtures.sql contents) and
asserts only on rows it created, identified by title.
"""

import uuid
from datetime import timedelta
from unittest.mock import patch

import httpx
import pytest


# ── helpers ───────────────────────────────────────────────────────────────────

@pytest.fixture
def today(db_conn):
    with db_conn.cursor() as cur:
        cur.execute("select current_date as d")
        return cur.fetchone()["d"]


def insert_task(db_conn, title, status="open", priority="medium", due_date=None,
                scheduled_at=None, task_type="normal", effort_hours=None) -> str:
    task_id = str(uuid.uuid4())
    with db_conn.cursor() as cur:
        cur.execute(
            """
            insert into tasktracker.tasks
                (id, title, status, priority, due_date, scheduled_at, task_type, effort_hours)
            values (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (task_id, title, status, priority, due_date, scheduled_at, task_type, effort_hours),
        )
    return task_id


def agenda_rows(client) -> list[dict]:
    r = client.get("/api/tasks/agenda")
    assert r.status_code == 200
    return r.json()["rows"]


def by_title(rows) -> dict:
    return {r["title"]: r for r in rows}


# ── scenarios ─────────────────────────────────────────────────────────────────

def test_agenda_overdue_task_bucketed(client, db_conn, today):
    insert_task(db_conn, "ag-overdue", due_date=today - timedelta(days=2))
    row = by_title(agenda_rows(client))["ag-overdue"]
    assert row["agenda_bucket"] == "overdue"
    assert row["agenda_date"] == (today - timedelta(days=2)).isoformat()


def test_agenda_due_today_bucketed(client, db_conn, today):
    insert_task(db_conn, "ag-today", due_date=today)
    row = by_title(agenda_rows(client))["ag-today"]
    assert row["agenda_bucket"] == "today"
    assert row["agenda_date"] == today.isoformat()


def test_agenda_upcoming_window_boundary(client, db_conn, today):
    insert_task(db_conn, "ag-p1", due_date=today + timedelta(days=1))
    insert_task(db_conn, "ag-p7", due_date=today + timedelta(days=7))
    insert_task(db_conn, "ag-p8", due_date=today + timedelta(days=8))
    rows = by_title(agenda_rows(client))
    assert rows["ag-p1"]["agenda_bucket"] == "upcoming"
    assert rows["ag-p7"]["agenda_bucket"] == "upcoming"
    assert "ag-p8" not in rows


def test_agenda_scheduled_status_uses_scheduled_at(client, db_conn, today):
    insert_task(db_conn, "ag-sched", status="scheduled",
                scheduled_at=today + timedelta(days=3), due_date=today + timedelta(days=6))
    matches = [r for r in agenda_rows(client) if r["title"] == "ag-sched"]
    assert len(matches) == 1
    assert matches[0]["agenda_date"] == (today + timedelta(days=3)).isoformat()


def test_agenda_non_scheduled_status_uses_due_date(client, db_conn, today):
    insert_task(db_conn, "ag-inprog", status="in_progress",
                due_date=today + timedelta(days=2), scheduled_at=today - timedelta(days=5))
    row = by_title(agenda_rows(client))["ag-inprog"]
    assert row["agenda_date"] == (today + timedelta(days=2)).isoformat()


def test_agenda_done_tasks_excluded(client, db_conn, today):
    insert_task(db_conn, "ag-done", status="done", due_date=today)
    assert "ag-done" not in by_title(agenda_rows(client))


def test_agenda_training_unit_tasks_excluded(client, db_conn, today):
    insert_task(db_conn, "ag-unit", task_type="training_unit", due_date=today)
    assert "ag-unit" not in by_title(agenda_rows(client))


def test_agenda_undated_tasks_excluded(client, db_conn):
    insert_task(db_conn, "ag-undated-open")
    insert_task(db_conn, "ag-undated-prog", status="in_progress")
    rows = by_title(agenda_rows(client))
    assert "ag-undated-open" not in rows
    assert "ag-undated-prog" not in rows


def test_agenda_ordering(client, db_conn, today):
    insert_task(db_conn, "ag-A", due_date=today + timedelta(days=2), priority="low")
    insert_task(db_conn, "ag-B", due_date=today - timedelta(days=3), priority="medium")
    insert_task(db_conn, "ag-C", due_date=today + timedelta(days=2), priority="high")
    insert_task(db_conn, "ag-D", due_date=today, priority="medium")
    titles = [r["title"] for r in agenda_rows(client) if r["title"].startswith("ag-")]
    assert titles == ["ag-B", "ag-D", "ag-C", "ag-A"]


def test_agenda_empty_result(client, db_conn):
    with db_conn.cursor() as cur:
        cur.execute("truncate tasktracker.tasks cascade")
    r = client.get("/api/tasks/agenda")
    assert r.status_code == 200
    data = r.json()
    assert data["rows"] == []
    assert data["meta"]["total"] == 0


def test_agenda_auto_promotion_runs_before_query_and_persists(client, db_conn, today):
    task_id = insert_task(db_conn, "ag-promote", status="scheduled",
                          scheduled_at=today, due_date=today + timedelta(days=4))
    row = by_title(agenda_rows(client))["ag-promote"]
    assert row["agenda_date"] == (today + timedelta(days=4)).isoformat()
    assert row["status"] == "in_progress"
    with db_conn.cursor() as cur:
        cur.execute("select status from tasktracker.tasks where id = %s", (task_id,))
        assert cur.fetchone()["status"] == "in_progress"


def test_agenda_labels_embedded_and_label_engine_failure_tolerated(client, db_conn, today):
    import backend.routers.tasks as tasks_mod
    task_id = insert_task(db_conn, "ag-labels", due_date=today)
    labels = {task_id: [{"id": "l1", "name": "home", "attached_at": "2026-01-01"}]}

    with patch.object(tasks_mod, "fetch_labels_for_tasks", return_value=labels):
        row = by_title(agenda_rows(client))["ag-labels"]
    assert row["labels"] == labels[task_id]

    with patch.object(tasks_mod, "fetch_labels_for_tasks", side_effect=httpx.ConnectError("down")):
        rows = agenda_rows(client)
    assert rows and all(r["labels"] == [] for r in rows)


def test_agenda_existing_views_unchanged(client, db_conn, today):
    insert_task(db_conn, "ag-view-open", status="open", due_date=today)
    insert_task(db_conn, "ag-view-sched", status="scheduled", scheduled_at=today + timedelta(days=20))
    insert_task(db_conn, "ag-view-done", status="done")
    expectations = {
        "/api/tasks?view=active": "ag-view-open",
        "/api/tasks?view=pending_board": "ag-view-open",
        "/api/tasks?view=scheduled": "ag-view-sched",
        "/api/tasks?status=done": "ag-view-done",
    }
    for url, title in expectations.items():
        r = client.get(url)
        assert r.status_code == 200, url
        rows = by_title(r.json()["rows"])
        assert title in rows, url
        row = rows[title]
        assert row["recurrence_freq"] is None
        assert row["recurrence_label"] is None
        assert row["recurrence_interval"] == 1
        assert row["recurrence_mode"] == "fixed"
        assert "agenda_bucket" not in row
