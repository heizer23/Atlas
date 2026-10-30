"""
Sprint11_TodayAndRecurrence — recurring task tests.

Scenario names match 10_test_spec.md ("Recurrence — ...") for traceability.
Date arithmetic scenarios call the pure function with explicit dates; API scenarios
use dates relative to the database current_date. Each test creates its own rows.
"""

import uuid
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from backend.recurrence import compute_next_date, format_recurrence_label


# ── helpers ───────────────────────────────────────────────────────────────────

@pytest.fixture
def today(db_conn):
    with db_conn.cursor() as cur:
        cur.execute("select current_date as d")
        return cur.fetchone()["d"]


@pytest.fixture(autouse=True)
def quiet_label_engine():
    """Default: LabelEngine returns no labels (deterministic, no network)."""
    import backend.routers.tasks as tasks_mod
    inst = MagicMock()
    inst.__enter__ = lambda s: s
    inst.__exit__ = MagicMock(return_value=False)
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"labels": []}
    inst.get.return_value = resp
    with patch.object(tasks_mod, "_label_client", return_value=inst):
        yield inst


def insert_task(db_conn, title, status="open", priority="medium", due_date=None,
                scheduled_at=None, freq=None, interval=1, mode="fixed",
                description=None, effort_hours=None, parent_task_id=None,
                task_type="normal") -> str:
    task_id = str(uuid.uuid4())
    with db_conn.cursor() as cur:
        cur.execute(
            """
            insert into tasktracker.tasks
                (id, title, description, status, priority, due_date, scheduled_at,
                 effort_hours, parent_task_id, task_type,
                 recurrence_freq, recurrence_interval, recurrence_mode)
            values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (task_id, title, description, status, priority, due_date, scheduled_at,
             effort_hours, parent_task_id, task_type, freq, interval, mode),
        )
    return task_id


def get_row(db_conn, task_id) -> dict:
    with db_conn.cursor() as cur:
        cur.execute("select * from tasktracker.tasks where id = %s", (task_id,))
        return cur.fetchone()


def rows_with_title(db_conn, title) -> list[dict]:
    with db_conn.cursor() as cur:
        cur.execute("select * from tasktracker.tasks where title = %s", (title,))
        return cur.fetchall()


def successor_of(db_conn, task_id) -> dict:
    src = get_row(db_conn, task_id)
    assert src["recurrence_next_id"] is not None, "no successor pointer"
    return get_row(db_conn, src["recurrence_next_id"])


def done(client, task_id, **extra):
    return client.patch(f"/api/tasks/{task_id}", json={"status": "done", **extra})


def mock_calendar_client():
    inst = MagicMock()
    inst.__enter__ = lambda s: s
    inst.__exit__ = MagicMock(return_value=False)
    ok = MagicMock(status_code=201, text="")
    inst.post.return_value = ok
    inst.delete.return_value = MagicMock(status_code=200, text="")
    return inst


# ── create ────────────────────────────────────────────────────────────────────

def test_recurrence_create_with_valid_recurrence(client, today):
    r = client.post("/api/tasks", json={
        "title": "rec-create", "due_date": (today + timedelta(days=1)).isoformat(),
        "recurrence_freq": "weekly", "recurrence_interval": 2,
    })
    assert r.status_code == 200
    row = r.json()["rows"][0]
    assert row["recurrence_freq"] == "weekly"
    assert row["recurrence_interval"] == 2
    assert row["recurrence_mode"] == "fixed"
    assert row["recurrence_next_id"] is None
    assert row["recurrence_label"] == "Every 2 weeks"


def test_recurrence_label_formats(client, today):
    due = today.isoformat()
    cases = [
        ({"recurrence_freq": "daily"}, "Daily"),
        ({"recurrence_freq": "monthly"}, "Monthly"),
        ({"recurrence_freq": "daily", "recurrence_mode": "after_completion"}, "Daily, after completion"),
        ({"recurrence_freq": "weekly", "recurrence_interval": 3, "recurrence_mode": "after_completion"},
         "Every 3 weeks, after completion"),
        ({}, None),
    ]
    for extra, expected in cases:
        r = client.post("/api/tasks", json={"title": "rec-label", "due_date": due, **extra})
        assert r.status_code == 200, extra
        assert r.json()["rows"][0]["recurrence_label"] == expected
    # pure function agrees
    assert format_recurrence_label(None, 1, "fixed") is None


def test_recurrence_create_validation_errors(client, db_conn, today):
    due = today.isoformat()
    bad_bodies = [
        {"recurrence_freq": "yearly", "due_date": due},
        {"recurrence_freq": "weekly", "recurrence_interval": 0, "due_date": due},
        {"recurrence_freq": "weekly", "recurrence_mode": "sometimes", "due_date": due},
        {"recurrence_freq": "weekly", "task_type": "training_unit", "due_date": due},
        {"recurrence_freq": "weekly", "recurrence_mode": "fixed"},
    ]
    for body in bad_bodies:
        r = client.post("/api/tasks", json={"title": "rec-bad", **body})
        assert r.status_code == 400, body
        assert r.json()["error"]["code"] == "VALIDATION_ERROR", body
    assert rows_with_title(db_conn, "rec-bad") == []


def test_recurrence_create_explicit_null_interval_or_mode_rejected(client, db_conn):
    """Design review note 4: POST null interval/mode is rejected before any insert."""
    for body in ({"recurrence_interval": None}, {"recurrence_mode": None}):
        r = client.post("/api/tasks", json={"title": "rec-null", "recurrence_freq": "daily", **body})
        assert r.status_code in (400, 422), body
        assert "error" in r.json()
    assert rows_with_title(db_conn, "rec-null") == []


def test_recurrence_after_completion_without_dates_allowed(client):
    r = client.post("/api/tasks", json={
        "title": "rec-nodate", "recurrence_freq": "daily", "recurrence_mode": "after_completion",
    })
    assert r.status_code == 200


# ── patch semantics ───────────────────────────────────────────────────────────

def test_recurrence_patch_null_clears_recurrence(client, db_conn):
    tid = insert_task(db_conn, "rec-clear", freq="monthly", interval=3, mode="after_completion")
    r = client.patch(f"/api/tasks/{tid}", json={"recurrence_freq": None})
    assert r.status_code == 200
    row = r.json()["rows"][0]
    assert row["recurrence_freq"] is None
    assert row["recurrence_interval"] == 1
    assert row["recurrence_mode"] == "fixed"
    assert row["recurrence_label"] is None


def test_recurrence_patch_omit_leaves_recurrence_unchanged(client, db_conn, today):
    tid = insert_task(db_conn, "rec-omit", due_date=today, freq="weekly", interval=2)
    r = client.patch(f"/api/tasks/{tid}", json={"title": "rec-omit-renamed"})
    assert r.status_code == 200
    row = get_row(db_conn, tid)
    assert (row["recurrence_freq"], row["recurrence_interval"], row["recurrence_mode"]) == ("weekly", 2, "fixed")


def test_recurrence_patch_explicit_null_on_interval_or_mode_rejected(client, db_conn, today):
    tid = insert_task(db_conn, "rec-nullfield", due_date=today, freq="weekly", interval=2)
    for body in ({"recurrence_interval": None}, {"recurrence_mode": None}):
        r = client.patch(f"/api/tasks/{tid}", json=body)
        assert r.status_code == 400, body
        assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    row = get_row(db_conn, tid)
    assert (row["recurrence_interval"], row["recurrence_mode"]) == (2, "fixed")


def test_recurrence_patch_clearing_only_date_of_fixed_task_rejected(client, db_conn, today):
    tid = insert_task(db_conn, "rec-cleardate", due_date=today, freq="daily")
    r = client.patch(f"/api/tasks/{tid}", json={"due_date": None})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert get_row(db_conn, tid)["due_date"] == today


def test_recurrence_due_date_explicit_null_clears_on_normal_task(client, db_conn, today):
    tid = insert_task(db_conn, "rec-nulldue", due_date=today + timedelta(days=2))
    r = client.patch(f"/api/tasks/{tid}", json={"due_date": None})
    assert r.status_code == 200
    assert r.json()["rows"][0]["due_date"] is None
    titles = [x["title"] for x in client.get("/api/tasks/agenda").json()["rows"]]
    assert "rec-nulldue" not in titles


# ── date arithmetic (pure) ────────────────────────────────────────────────────

def test_recurrence_month_end_clamp_date_arithmetic():
    assert compute_next_date(date(2027, 1, 31), "monthly", 1, "fixed", date(2027, 1, 30)) == date(2027, 2, 28)
    assert compute_next_date(date(2028, 1, 31), "monthly", 1, "fixed", date(2028, 1, 30)) == date(2028, 2, 29)


def test_recurrence_long_overdue_catch_up_date_arithmetic():
    assert compute_next_date(date(2027, 1, 31), "monthly", 1, "fixed", date(2027, 4, 15)) == date(2027, 4, 30)


# ── spawn via API ─────────────────────────────────────────────────────────────

def test_recurrence_daily_fixed_spawns_next_day(client, db_conn, today):
    tid = insert_task(db_conn, "rec-daily", due_date=today, freq="daily")
    r = done(client, tid)
    assert r.status_code == 200
    assert r.json()["rows"][0]["recurrence_next_date"] == (today + timedelta(days=1)).isoformat()
    rows = rows_with_title(db_conn, "rec-daily")
    assert len(rows) == 2
    succ = successor_of(db_conn, tid)
    assert succ["due_date"] == today + timedelta(days=1)
    assert succ["status"] == "open"
    assert str(succ["id"]) == str(get_row(db_conn, tid)["recurrence_next_id"])


def test_recurrence_weekly_fixed_with_interval(client, db_conn, today):
    tid = insert_task(db_conn, "rec-weekly2", due_date=today + timedelta(days=1), freq="weekly", interval=2)
    done(client, tid)
    assert successor_of(db_conn, tid)["due_date"] == today + timedelta(days=15)


def test_recurrence_monthly_fixed(client, db_conn, today):
    from backend.recurrence import add_months
    anchor = today + timedelta(days=5)
    tid = insert_task(db_conn, "rec-monthly", due_date=anchor, freq="monthly")
    done(client, tid)
    assert successor_of(db_conn, tid)["due_date"] == add_months(anchor, 1)


def test_recurrence_long_overdue_catch_up_through_api(client, db_conn, today):
    tid = insert_task(db_conn, "rec-catchup", due_date=today - timedelta(days=30), freq="daily")
    done(client, tid)
    assert len(rows_with_title(db_conn, "rec-catchup")) == 2
    assert successor_of(db_conn, tid)["due_date"] == today + timedelta(days=1)


def test_recurrence_fixed_result_equal_to_today_is_pushed_forward(client, db_conn, today):
    tid = insert_task(db_conn, "rec-pushfwd", due_date=today - timedelta(days=7), freq="weekly")
    done(client, tid)
    assert successor_of(db_conn, tid)["due_date"] == today + timedelta(days=7)


def test_recurrence_after_completion_uses_completion_date(client, db_conn, today):
    tid = insert_task(db_conn, "rec-aftercomp", due_date=today - timedelta(days=10),
                      freq="weekly", mode="after_completion")
    done(client, tid)
    assert successor_of(db_conn, tid)["due_date"] == today + timedelta(days=7)


def test_recurrence_after_completion_with_no_dates(client, db_conn, today):
    tid = insert_task(db_conn, "rec-nodates", freq="daily", mode="after_completion")
    done(client, tid)
    assert successor_of(db_conn, tid)["due_date"] == today + timedelta(days=1)


def test_recurrence_every_freq_and_mode_combination_yields_exactly_one_successor(client, db_conn, today):
    for freq in ("daily", "weekly", "monthly"):
        for mode in ("fixed", "after_completion"):
            title = f"rec-combo-{freq}-{mode}"
            tid = insert_task(db_conn, title, due_date=today - timedelta(days=3), freq=freq, mode=mode)
            assert done(client, tid).status_code == 200
            rows = rows_with_title(db_conn, title)
            assert len(rows) == 2, title
            succ = successor_of(db_conn, tid)
            assert succ["status"] == "open"
            assert succ["due_date"] > today
            assert (succ["recurrence_freq"], succ["recurrence_interval"], succ["recurrence_mode"]) == (freq, 1, mode)


def test_recurrence_successor_copies_content_and_resets_completion_fields(client, db_conn, today):
    parent = insert_task(db_conn, "rec-parent")
    tid = insert_task(db_conn, "rec-copy", description="desc", priority="high", effort_hours=2.5,
                      due_date=today, freq="weekly", interval=2, mode="fixed", parent_task_id=parent)
    done(client, tid, actual_duration_minutes=40)
    assert get_row(db_conn, tid)["actual_duration_minutes"] == 40
    succ = successor_of(db_conn, tid)
    assert succ["title"] == "rec-copy"
    assert succ["description"] == "desc"
    assert succ["priority"] == "high"
    assert succ["effort_hours"] == 2.5
    assert str(succ["parent_task_id"]) == parent
    assert (succ["recurrence_freq"], succ["recurrence_interval"], succ["recurrence_mode"]) == ("weekly", 2, "fixed")
    assert succ["status"] == "open"
    assert succ["completed_at"] is None
    assert succ["actual_duration_minutes"] is None
    assert succ["recurrence_next_id"] is None


def test_recurrence_labels_copied_to_successor(client, db_conn, today, quiet_label_engine):
    tid = insert_task(db_conn, "rec-labels", due_date=today, freq="daily")
    get_resp = MagicMock(status_code=200)
    get_resp.json.return_value = {"labels": [
        {"label_id": "l1", "label_name": "home", "attached_at": "2026-01-01"},
        {"label_id": "l2", "label_name": "chores", "attached_at": "2026-01-01"},
    ]}
    quiet_label_engine.get.return_value = get_resp
    quiet_label_engine.post.return_value = MagicMock(status_code=201)
    done(client, tid)
    succ_id = str(successor_of(db_conn, tid)["id"])
    calls = quiet_label_engine.post.call_args_list
    assert len(calls) == 2
    names = set()
    for c in calls:
        assert c[0][0] == f"/api/objects/{succ_id}/labels"
        assert c[1]["json"]["object_type"] == "task"
        names.add(c[1]["json"]["label_name"])
    assert names == {"home", "chores"}


def test_recurrence_label_copy_failure_does_not_fail_completion(client, db_conn, today, quiet_label_engine):
    import httpx
    tid = insert_task(db_conn, "rec-labelfail", due_date=today, freq="daily")
    quiet_label_engine.get.side_effect = httpx.ConnectError("down")
    r = done(client, tid)
    assert r.status_code == 200
    assert get_row(db_conn, tid)["status"] == "done"
    assert len(rows_with_title(db_conn, "rec-labelfail")) == 2


def test_recurrence_undo_and_redo_spawn_no_duplicate(client, db_conn, today):
    tid = insert_task(db_conn, "rec-redo", due_date=today, freq="daily")
    done(client, tid)
    pointer = get_row(db_conn, tid)["recurrence_next_id"]
    assert client.patch(f"/api/tasks/{tid}", json={"status": "open"}).status_code == 200
    assert done(client, tid).status_code == 200
    assert len(rows_with_title(db_conn, "rec-redo")) == 2
    assert get_row(db_conn, tid)["recurrence_next_id"] == pointer


def test_recurrence_repeated_done_does_not_respawn(client, db_conn, today):
    tid = insert_task(db_conn, "rec-twice", due_date=today, freq="daily")
    done(client, tid)
    r = done(client, tid)
    assert r.status_code == 200
    assert r.json()["rows"][0]["recurrence_next_date"] is None
    assert len(rows_with_title(db_conn, "rec-twice")) == 2


def test_recurrence_non_recurring_completion_spawns_nothing(client, db_conn, today):
    tid = insert_task(db_conn, "rec-plain", due_date=today)
    r = done(client, tid)
    assert r.json()["rows"][0]["recurrence_next_date"] is None
    assert len(rows_with_title(db_conn, "rec-plain")) == 1


def test_recurrence_clearing_recurrence_while_completing_spawns_nothing(client, db_conn, today):
    tid = insert_task(db_conn, "rec-clearcomplete", due_date=today, freq="daily")
    r = done(client, tid, recurrence_freq=None)
    assert r.status_code == 200
    assert len(rows_with_title(db_conn, "rec-clearcomplete")) == 1
    assert get_row(db_conn, tid)["recurrence_freq"] is None


# ── scheduled / calendar ──────────────────────────────────────────────────────

def test_recurrence_scheduled_recurring_task_spawns_scheduled_successor_with_blocker(client, db_conn, today):
    import backend.routers.tasks as tasks_mod
    tid = insert_task(db_conn, "rec-sched", status="scheduled", freq="weekly",
                      scheduled_at=today + timedelta(days=2), due_date=today + timedelta(days=4))
    cal = mock_calendar_client()
    with patch.object(tasks_mod, "CALENDAR_CONNECTOR_URL", "http://fake-calendar:8000"), \
         patch.object(tasks_mod, "_calendar_client", return_value=cal):
        r = done(client, tid)
    assert r.status_code == 200
    succ = successor_of(db_conn, tid)
    assert succ["status"] == "scheduled"
    assert succ["scheduled_at"] == today + timedelta(days=9)
    assert succ["due_date"] == today + timedelta(days=11)
    cal.delete.assert_called_once_with(f"/api/calendar/events/{tid}")
    cal.post.assert_called_once()
    payload = cal.post.call_args[1]["json"]
    assert payload["atlas_event_id"] == str(succ["id"])
    assert payload["title"].startswith("[Atlas] ")
    assert payload["start_at"] == (today + timedelta(days=9)).isoformat()
    assert payload["all_day"] is True


def test_recurrence_scheduled_task_completed_through_edit_form_payload(client, db_conn, today):
    tid = insert_task(db_conn, "rec-editform", status="scheduled", freq="weekly",
                      scheduled_at=today + timedelta(days=1))
    r = client.patch(f"/api/tasks/{tid}", json={
        "status": "done", "scheduled_at": None, "due_date": None,
        "recurrence_freq": "weekly", "recurrence_interval": 1, "recurrence_mode": "fixed",
    })
    assert r.status_code == 200
    succ = successor_of(db_conn, tid)
    assert succ["status"] == "scheduled"
    assert succ["scheduled_at"] == today + timedelta(days=8)


def test_recurrence_calendar_failure_does_not_fail_completion(client, db_conn, today):
    import backend.routers.tasks as tasks_mod
    tid = insert_task(db_conn, "rec-calfail", status="scheduled", freq="weekly",
                      scheduled_at=today + timedelta(days=2))
    cal = mock_calendar_client()
    cal.post.return_value = MagicMock(status_code=500, text="boom")
    cal.delete.return_value = MagicMock(status_code=500, text="boom")
    with patch.object(tasks_mod, "CALENDAR_CONNECTOR_URL", "http://fake-calendar:8000"), \
         patch.object(tasks_mod, "_calendar_client", return_value=cal):
        r = done(client, tid)
    assert r.status_code == 200
    assert len(rows_with_title(db_conn, "rec-calfail")) == 2


# ── atomicity, delete, agenda interplay ──────────────────────────────────────

def test_recurrence_spawn_is_atomic(app, db_conn, today):
    import backend.routers.tasks as tasks_mod
    from starlette.testclient import TestClient
    tid = insert_task(db_conn, "rec-atomic", due_date=today, freq="daily")
    with patch.object(tasks_mod, "compute_next_date", side_effect=RuntimeError("forced")):
        with TestClient(app, raise_server_exceptions=False) as c:
            r = done(c, tid)
    assert r.status_code >= 500
    row = get_row(db_conn, tid)
    assert row["status"] != "done"
    assert row["recurrence_next_id"] is None
    assert len(rows_with_title(db_conn, "rec-atomic")) == 1


def test_recurrence_deleting_the_successor_clears_the_pointer(client, db_conn, today):
    tid = insert_task(db_conn, "rec-delsucc", due_date=today, freq="daily")
    done(client, tid)
    succ_id = str(successor_of(db_conn, tid)["id"])
    assert client.delete(f"/api/tasks/{succ_id}").status_code == 200
    assert get_row(db_conn, tid)["recurrence_next_id"] is None


def test_recurrence_successor_appears_in_the_agenda_when_due_soon(client, db_conn, today):
    tid = insert_task(db_conn, "rec-agenda", due_date=today, freq="daily")
    done(client, tid)
    rows = [r for r in client.get("/api/tasks/agenda").json()["rows"] if r["title"] == "rec-agenda"]
    assert len(rows) == 1
    assert rows[0]["id"] != tid
    assert rows[0]["agenda_bucket"] == "upcoming"
    assert rows[0]["agenda_date"] == (today + timedelta(days=1)).isoformat()
