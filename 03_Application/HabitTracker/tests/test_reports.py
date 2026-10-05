"""
Tests for GET /reports.

Scenario -> test function mapping (10_test_spec.md):
  Reports — grid cell states cover all four cases
    -> test_grid_cell_states_cover_all_four_cases
  Reports — per-habit rate omits percentage when eligible is zero
    -> test_per_habit_rate_omits_percentage_when_eligible_is_zero
  Reports — period-level elapsed days never counts future dates
    -> test_elapsed_days_never_counts_future_dates
  Reports — empty habit set still returns a valid period_summary
    -> test_empty_habit_set_still_returns_valid_period_summary
  Reports — invalid period parameter is rejected
    -> test_invalid_period_parameter_is_rejected
"""

from datetime import timedelta

from backend.review_logic import berlin_today

BASE = "/api/habittracker"

WORKED_OUT_ID = "10000001-0000-0000-0000-000000000001"
NO_SWEETS_ID  = "10000002-0000-0000-0000-000000000002"
NO_VAPING_ID  = "10000003-0000-0000-0000-000000000003"
BP_ID         = "10000004-0000-0000-0000-000000000004"
ESSAYCARDS_ID = "10000005-0000-0000-0000-000000000005"

STARTER_IDS = [WORKED_OUT_ID, NO_SWEETS_ID, NO_VAPING_ID, BP_ID, ESSAYCARDS_ID]


def _confirm(client, date_str, checked_by_id=None, status="confirmed"):
    checked_by_id = checked_by_id or {}
    row = client.get(f"{BASE}/reviews/{date_str}").json()["rows"][0]
    results = [{"habit_id": h["habit_id"], "checked": checked_by_id.get(h["habit_id"], False)} for h in row["habits"]]
    r = client.put(f"{BASE}/reviews/{date_str}", json={"status": status, "habit_results": results})
    assert r.status_code == 200
    return r.json()["rows"][0]


def test_grid_cell_states_cover_all_four_cases(client):
    # ISO week containing 2026-01-01 (a Thursday) runs Mon 2025-12-29 .. Sun
    # 2026-01-04 — straddling every starter habit's active_from (2026-01-01),
    # which gives a clean not_active date for free alongside the other three.
    _confirm(client, "2026-01-01", checked_by_id={WORKED_OUT_ID: True})       # completed
    _confirm(client, "2026-01-02", checked_by_id={WORKED_OUT_ID: False})      # not_completed
    _confirm(client, "2026-01-03", checked_by_id={WORKED_OUT_ID: True}, status="draft")  # unreviewed

    r = client.get(f"{BASE}/reports?period=week&anchor_date=2026-01-01")
    assert r.status_code == 200
    body = r.json()
    worked_out_row = next(row for row in body["rows"] if row["habit_id"] == WORKED_OUT_ID)
    cells_by_date = {c["date"]: c["state"] for c in worked_out_row["cells"]}

    assert cells_by_date["2026-01-01"] == "completed"
    assert cells_by_date["2026-01-02"] == "not_completed"
    assert cells_by_date["2026-01-03"] == "unreviewed"
    assert cells_by_date["2025-12-30"] == "not_active"


def test_per_habit_rate_omits_percentage_when_eligible_is_zero(client):
    # An arbitrary week with no confirmed days at all for worked-out.
    r = client.get(f"{BASE}/reports?period=week&anchor_date=2026-03-02")
    assert r.status_code == 200
    worked_out_row = next(row for row in r.json()["rows"] if row["habit_id"] == WORKED_OUT_ID)
    assert worked_out_row["eligible_confirmed_days"] == 0
    assert worked_out_row["rate"] is None


def test_elapsed_days_never_counts_future_dates(client):
    today = berlin_today()
    monday = today - timedelta(days=today.isoweekday() - 1)
    expected_elapsed = (today - monday).days + 1

    r = client.get(f"{BASE}/reports?period=week&anchor_date={today.isoformat()}")
    assert r.status_code == 200
    summary = r.json()["period_summary"]
    assert summary["elapsed_days"] == expected_elapsed
    assert summary["elapsed_days"] <= 7


def test_empty_habit_set_still_returns_valid_period_summary(client):
    # A week entirely in June 2024 — before every fixture habit's active_from.
    r = client.get(f"{BASE}/reports?period=week&anchor_date=2024-06-03")
    assert r.status_code == 200
    body = r.json()
    assert body["rows"] == []
    summary = body["period_summary"]
    assert summary["confirmed_days"] == 0
    assert summary["elapsed_days"] == 7


def test_invalid_period_parameter_is_rejected(client):
    r = client.get(f"{BASE}/reports?period=day&anchor_date=2026-10-01")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
