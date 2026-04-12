"""
Tests for POST /api/series/by-name/{label_name}/values (Chronos write by name).

Scenarios from Sprint02_ChronosAndUX/10_test_spec.md.
Fixtures defined in tests/fixtures.sql:
  fix-label-weight → 'Weight' (has series record)
  fix-label-steps  → 'Daily Steps' (no series record)
"""

import pytest


# ── Happy path — single entry ──────────────────────────────────────────────────

def test_happy_path_single_entry_inserted_by_name(client):
    """Happy path — single entry inserted by name."""
    r = client.post(
        "/api/series/by-name/Weight/values",
        json={"entries": [{"value": 72.3, "recorded_at": "2026-04-12T08:00:00Z"}]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body == {"inserted": 1}


# ── Happy path — multiple entries ─────────────────────────────────────────────

def test_happy_path_multiple_entries_inserted(client):
    """Happy path — multiple entries inserted in one call."""
    r = client.post(
        "/api/series/by-name/Weight/values",
        json={
            "entries": [
                {"value": 70.0, "recorded_at": "2026-04-10T08:00:00Z"},
                {"value": 71.5, "recorded_at": "2026-04-11T08:00:00Z"},
            ]
        },
    )
    assert r.status_code == 200
    assert r.json() == {"inserted": 2}


# ── Case-insensitive name match ────────────────────────────────────────────────

def test_case_insensitive_name_match(client):
    """Case-insensitive name match — 'weight' matches 'Weight'."""
    r = client.post(
        "/api/series/by-name/weight/values",
        json={"entries": [{"value": 73.0, "recorded_at": "2026-04-12T09:00:00Z"}]},
    )
    assert r.status_code == 200
    assert r.json() == {"inserted": 1}


# ── Series not found — label exists but no series record ──────────────────────

def test_series_not_found_label_exists_no_series_record(client):
    """Label 'Daily Steps' exists in labels.labels but has no series record."""
    r = client.post(
        "/api/series/by-name/Daily Steps/values",
        json={"entries": [{"value": 8000, "recorded_at": "2026-04-12T08:00:00Z"}]},
    )
    assert r.status_code == 404
    body = r.json()
    assert body["error"]["code"] == "SERIES_NOT_FOUND"


# ── Series not found — label does not exist ────────────────────────────────────

def test_series_not_found_label_does_not_exist(client):
    """No label named 'Nonexistent' exists at all."""
    r = client.post(
        "/api/series/by-name/Nonexistent/values",
        json={"entries": [{"value": 1.0, "recorded_at": "2026-04-12T08:00:00Z"}]},
    )
    assert r.status_code == 404
    body = r.json()
    assert body["error"]["code"] == "SERIES_NOT_FOUND"


# ── Invalid value — Pydantic rejects null ─────────────────────────────────────

def test_invalid_value_null_rejected(client):
    """null value is rejected by Pydantic validation (422 — missing/invalid field)."""
    r = client.post(
        "/api/series/by-name/Weight/values",
        json={"entries": [{"value": None, "recorded_at": "2026-04-12T08:00:00Z"}]},
    )
    assert r.status_code == 422


# ── Invalid timestamp rejected ─────────────────────────────────────────────────

def test_invalid_timestamp_rejected(client):
    """Non-ISO-8601 recorded_at returns 422 INVALID_TIMESTAMP."""
    r = client.post(
        "/api/series/by-name/Weight/values",
        json={"entries": [{"value": 72.0, "recorded_at": "not-a-date"}]},
    )
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "INVALID_TIMESTAMP"
