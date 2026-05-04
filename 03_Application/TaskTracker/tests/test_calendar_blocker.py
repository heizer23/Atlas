"""
Sprint10_CalendarBlocker — test suite.

Tests verify that task create/update fires the correct CalendarConnector call
(mocked via unittest.mock.patch), and that calendar errors never fail the task
operation. All tests run against the atlas_test database inside the Docker test
container.

Traceability:
  Each test function name maps to a scenario in Sprint10_CalendarBlocker/10_test_spec.md.
"""

from unittest.mock import MagicMock, patch

import pytest


# ── helpers ──────────────────────────────────────────────────────────────────

OPEN_ID      = "00000000-0000-0000-0000-000000000001"
SCHED_ID_FAR = "00000000-0000-0000-0000-000000000002"  # scheduled, 7 days future


def _make_ok_response(status_code: int = 201) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.text = ""
    return mock_resp


def _make_error_response(status_code: int) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.text = "CalendarConnector error"
    return mock_resp


def _patch_calendar_url(url: str = "http://fake-calendar:8000"):
    """Patch CALENDAR_CONNECTOR_URL at the module level."""
    import backend.routers.tasks as tasks_mod
    return patch.object(tasks_mod, "CALENDAR_CONNECTOR_URL", url)


# ── scenario: create scheduled task triggers calendar create ──────────────────

def test_create_scheduled_task_triggers_calendar_create(client):
    """POST /tasks with status=scheduled fires CalendarConnector POST."""
    import backend.routers.tasks as tasks_mod

    mock_client_instance = MagicMock()
    mock_client_instance.__enter__ = lambda s: s
    mock_client_instance.__exit__ = MagicMock(return_value=False)
    mock_client_instance.post.return_value = _make_ok_response(201)

    with _patch_calendar_url(), \
         patch.object(tasks_mod, "_calendar_client", return_value=mock_client_instance):

        resp = client.post("/api/tasks", json={
            "title": "Sprint Demo",
            "status": "scheduled",
            "scheduled_at": "2026-06-01",
            "priority": "medium",
        })

    assert resp.status_code == 200
    data = resp.json()
    task_id = data["rows"][0]["id"]

    mock_client_instance.post.assert_called_once()
    call_args = mock_client_instance.post.call_args
    assert call_args[0][0] == "/api/calendar/events"
    payload = call_args[1]["json"]
    assert payload["atlas_event_id"] == task_id
    assert payload["all_day"] is True
    assert payload["start_at"] == "2026-06-01"
    assert payload["end_at"] == "2026-06-02"
    assert payload["title"].startswith("[Atlas] ")


# ── scenario: create non-scheduled task does not trigger calendar call ────────

def test_create_non_scheduled_task_does_not_trigger_calendar_call(client):
    """POST /tasks with status=open does not call CalendarConnector."""
    import backend.routers.tasks as tasks_mod

    mock_client_instance = MagicMock()
    mock_client_instance.__enter__ = lambda s: s
    mock_client_instance.__exit__ = MagicMock(return_value=False)

    with _patch_calendar_url(), \
         patch.object(tasks_mod, "_calendar_client", return_value=mock_client_instance):

        resp = client.post("/api/tasks", json={
            "title": "Open task",
            "status": "open",
            "priority": "low",
        })

    assert resp.status_code == 200
    mock_client_instance.post.assert_not_called()
    mock_client_instance.patch.assert_not_called()
    mock_client_instance.delete.assert_not_called()


# ── scenario: create scheduled task when CalendarConnector URL empty ──────────

def test_create_scheduled_task_calendar_url_empty_skips_sync_silently(client):
    """POST /tasks with status=scheduled and empty CALENDAR_CONNECTOR_URL — task created, no HTTP call."""
    import backend.routers.tasks as tasks_mod

    with patch.object(tasks_mod, "CALENDAR_CONNECTOR_URL", ""):
        resp = client.post("/api/tasks", json={
            "title": "Quiet task",
            "status": "scheduled",
            "scheduled_at": "2026-06-01",
            "priority": "medium",
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["rows"][0]["status"] == "scheduled"


# ── scenario: patch task from open to scheduled triggers calendar create ──────

def test_patch_task_from_open_to_scheduled_triggers_calendar_create(client):
    """PATCH existing open task to scheduled — CalendarConnector POST is called."""
    import backend.routers.tasks as tasks_mod

    mock_client_instance = MagicMock()
    mock_client_instance.__enter__ = lambda s: s
    mock_client_instance.__exit__ = MagicMock(return_value=False)
    mock_client_instance.post.return_value = _make_ok_response(201)

    with _patch_calendar_url(), \
         patch.object(tasks_mod, "_calendar_client", return_value=mock_client_instance):

        resp = client.patch(f"/api/tasks/{OPEN_ID}", json={
            "status": "scheduled",
            "scheduled_at": "2026-06-10",
        })

    assert resp.status_code == 200
    mock_client_instance.post.assert_called_once()
    call_args = mock_client_instance.post.call_args
    payload = call_args[1]["json"]
    assert payload["atlas_event_id"] == OPEN_ID
    assert payload["start_at"] == "2026-06-10"
    assert payload["end_at"] == "2026-06-11"


# ── scenario: patch scheduled task with new scheduled_at triggers update ──────

def test_patch_scheduled_task_new_scheduled_at_triggers_calendar_update(client):
    """PATCH scheduled task with new scheduled_at — CalendarConnector PATCH is called."""
    import backend.routers.tasks as tasks_mod

    mock_client_instance = MagicMock()
    mock_client_instance.__enter__ = lambda s: s
    mock_client_instance.__exit__ = MagicMock(return_value=False)
    mock_client_instance.patch.return_value = _make_ok_response(200)

    with _patch_calendar_url(), \
         patch.object(tasks_mod, "_calendar_client", return_value=mock_client_instance):

        resp = client.patch(f"/api/tasks/{SCHED_ID_FAR}", json={
            "scheduled_at": "2026-06-15",
        })

    assert resp.status_code == 200
    mock_client_instance.patch.assert_called_once()
    call_args = mock_client_instance.patch.call_args
    assert f"/api/calendar/events/{SCHED_ID_FAR}" in call_args[0][0]
    payload = call_args[1]["json"]
    assert payload["start_at"] == "2026-06-15"
    assert payload["end_at"] == "2026-06-16"


# ── scenario: patch scheduled task with unrelated field — no calendar call ────

def test_patch_scheduled_task_unrelated_field_does_not_trigger_calendar_update(client):
    """PATCH scheduled task with only priority change — CalendarConnector is never called."""
    import backend.routers.tasks as tasks_mod

    mock_client_instance = MagicMock()
    mock_client_instance.__enter__ = lambda s: s
    mock_client_instance.__exit__ = MagicMock(return_value=False)

    with _patch_calendar_url(), \
         patch.object(tasks_mod, "_calendar_client", return_value=mock_client_instance):

        resp = client.patch(f"/api/tasks/{SCHED_ID_FAR}", json={
            "priority": "high",
        })

    assert resp.status_code == 200
    mock_client_instance.post.assert_not_called()
    mock_client_instance.patch.assert_not_called()
    mock_client_instance.delete.assert_not_called()


# ── scenario: patch task from scheduled to open triggers calendar delete ──────

def test_patch_task_from_scheduled_to_open_triggers_calendar_delete(client):
    """PATCH scheduled task to open — CalendarConnector DELETE is called."""
    import backend.routers.tasks as tasks_mod

    mock_client_instance = MagicMock()
    mock_client_instance.__enter__ = lambda s: s
    mock_client_instance.__exit__ = MagicMock(return_value=False)
    mock_client_instance.delete.return_value = _make_ok_response(200)

    with _patch_calendar_url(), \
         patch.object(tasks_mod, "_calendar_client", return_value=mock_client_instance):

        resp = client.patch(f"/api/tasks/{SCHED_ID_FAR}", json={
            "status": "open",
            "scheduled_at": None,
        })

    assert resp.status_code == 200
    mock_client_instance.delete.assert_called_once()
    call_url = mock_client_instance.delete.call_args[0][0]
    assert SCHED_ID_FAR in call_url


# ── scenario: calendar create error does not fail task creation ───────────────

def test_calendar_create_error_does_not_fail_task_creation(client):
    """CalendarConnector POST returns 503 — task still created successfully."""
    import backend.routers.tasks as tasks_mod

    mock_client_instance = MagicMock()
    mock_client_instance.__enter__ = lambda s: s
    mock_client_instance.__exit__ = MagicMock(return_value=False)
    mock_client_instance.post.return_value = _make_error_response(503)

    with _patch_calendar_url(), \
         patch.object(tasks_mod, "_calendar_client", return_value=mock_client_instance):

        resp = client.post("/api/tasks", json={
            "title": "Resilient task",
            "status": "scheduled",
            "scheduled_at": "2026-06-01",
            "priority": "medium",
        })

    assert resp.status_code == 200
    assert resp.json()["rows"][0]["title"] == "Resilient task"


# ── scenario: calendar network error does not fail task update ────────────────

def test_calendar_network_error_does_not_fail_task_update(client):
    """CalendarConnector unreachable (raises ConnectError) — task PATCH still returns 200."""
    import backend.routers.tasks as tasks_mod
    import httpx

    mock_client_instance = MagicMock()
    mock_client_instance.__enter__ = lambda s: s
    mock_client_instance.__exit__ = MagicMock(return_value=False)
    mock_client_instance.post.side_effect = httpx.ConnectError("connection refused")

    with _patch_calendar_url(), \
         patch.object(tasks_mod, "_calendar_client", return_value=mock_client_instance):

        resp = client.patch(f"/api/tasks/{OPEN_ID}", json={
            "status": "scheduled",
            "scheduled_at": "2026-06-10",
        })

    assert resp.status_code == 200
    assert resp.json()["rows"][0]["status"] == "scheduled"
