"""
Sprint 08 backend tests — FoodTracker date-context fixes.

Covers copy_entry scenarios from 10_test_spec.md:
  - Copy with explicit logged_at uses caller date
  - Copy without body falls back to current date
  - Copy with invalid logged_at falls back gracefully
  - Copy nonexistent entry returns 404

UI scenarios are [UI — manual] and are not covered here.

Run inside the test container:
    docker exec atlas-food-tracker-test pytest tests/test_sprint08.py -v
"""

import json
import re

import pytest

# Source fixture entry defined in tests/fixtures.sql
_FIXTURE_ID = "00000000-0000-0000-0000-000000000001"
_NONEXISTENT_ID = "00000000-0000-0000-0000-000000000099"

# ISO-8601 datetime pattern: YYYY-MM-DDTHH:MM:SS (no timezone)
_ISO_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")


def test_copy_with_explicit_logged_at_uses_caller_date(client):
    """Copy with explicit logged_at uses caller date."""
    r = client.post(
        f"/api/food/entries/{_FIXTURE_ID}/copy",
        content=json.dumps({"logged_at": "2026-01-15T08:30:00"}),
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["logged_at"] == "2026-01-15T08:30:00"
    # Nutrition fields must match the source fixture
    assert body["dish_name"] == "chicken breast"
    assert body["kcal"] == 330
    assert float(body["protein_g"]) == pytest.approx(62.0, rel=1e-3)
    # Must be a new id (not the fixture id)
    assert body["id"] != _FIXTURE_ID


def test_copy_without_body_falls_back_to_current_date(client):
    """Copy without body falls back to current date."""
    r = client.post(f"/api/food/entries/{_FIXTURE_ID}/copy")
    assert r.status_code == 201
    body = r.json()
    # logged_at must be a valid ISO-8601 datetime string
    assert _ISO_PATTERN.match(body["logged_at"]), f"Unexpected logged_at: {body['logged_at']}"
    assert body["dish_name"] == "chicken breast"


def test_copy_with_invalid_logged_at_falls_back_gracefully(client):
    """Copy with invalid logged_at falls back gracefully (does not error)."""
    r = client.post(
        f"/api/food/entries/{_FIXTURE_ID}/copy",
        content=json.dumps({"logged_at": "not-a-date"}),
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 201
    body = r.json()
    # Must be a valid ISO-8601 datetime string (fallback to now)
    assert _ISO_PATTERN.match(body["logged_at"]), f"Unexpected logged_at: {body['logged_at']}"
    assert body["dish_name"] == "chicken breast"


def test_copy_nonexistent_entry_returns_404(client):
    """Copy nonexistent entry returns 404."""
    r = client.post(
        f"/api/food/entries/{_NONEXISTENT_ID}/copy",
        content=json.dumps({"logged_at": "2026-01-15T08:30:00"}),
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 404
    body = r.json()
    assert body["error"]["code"] == "NOT_FOUND"
