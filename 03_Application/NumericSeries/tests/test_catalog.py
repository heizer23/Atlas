"""
Tests for GET /api/measurement-definitions and POST /api/measurements/batch.

Scenarios from Sprint03_Chronos&UXpt2/10_test_spec.md.
Fixtures defined in tests/fixtures.sql:
  fix-label-weight  → 'weight'      (has series record, two measurements)
  fix-label-bodyfat → 'body_fat_pct' (has series record)
  fix-label-steps   → 'Daily Steps' (no series record; 'steps' is a valid catalog key)
"""

import json


# ── Catalog endpoint ───────────────────────────────────────────────────────────

def test_catalog_returns_all_definitions(client):
    """Catalog endpoint returns Dataset with all catalog entries."""
    r = client.get("/api/measurement-definitions")
    assert r.status_code == 200
    body = r.json()

    # Dataset structure
    assert "meta" in body
    assert body["meta"]["object_type"] == "measurement_definition"
    assert "rows" in body
    assert len(body["rows"]) >= 1

    # Each row has required fields
    row = body["rows"][0]
    assert "id" in row
    assert "key" in row
    assert "label" in row
    assert "unit" in row
    assert "value_type" in row
    assert "description" in row

    # Rows are ordered by label ASC
    labels = [r["label"] for r in body["rows"]]
    assert labels == sorted(labels, key=str.lower)

    # 'weight' entry is present
    keys = [r["key"] for r in body["rows"]]
    assert "weight" in keys


# ── Batch ingestion — happy path ───────────────────────────────────────────────

def test_batch_single_measurement(client):
    """Batch single measurement inserted. Fixture: fix-label-weight (has series)."""
    r = client.post(
        "/api/measurements/batch",
        json={
            "recorded_at": "2026-04-12T08:00:00Z",
            "measurements": [{"key": "weight", "value": 80.5}],
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body == {"inserted": 1}


def test_batch_multiple_measurements(client):
    """Batch two measurements inserted atomically."""
    r = client.post(
        "/api/measurements/batch",
        json={
            "recorded_at": "2026-04-12T08:00:00Z",
            "measurements": [
                {"key": "weight", "value": 80.5},
                {"key": "body_fat_pct", "value": 18.4},
            ],
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body == {"inserted": 2}


# ── Batch ingestion — error cases ─────────────────────────────────────────────

def test_batch_unknown_key(client):
    """Batch rejects unknown catalog key."""
    r = client.post(
        "/api/measurements/batch",
        json={
            "recorded_at": "2026-04-12T08:00:00Z",
            "measurements": [{"key": "unknown_metric", "value": 1.0}],
        },
    )
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "UNKNOWN_KEY"


def test_batch_missing_recorded_at(client):
    """Batch rejects request with no recorded_at field."""
    r = client.post(
        "/api/measurements/batch",
        json={
            "measurements": [{"key": "weight", "value": 80.5}],
        },
    )
    # Pydantic should reject this as a validation error (422)
    assert r.status_code == 422


def test_batch_invalid_value(client):
    """Batch rejects null value (422 INVALID_VALUE or Pydantic validation error)."""
    r = client.post(
        "/api/measurements/batch",
        json={
            "recorded_at": "2026-04-12T08:00:00Z",
            "measurements": [{"key": "weight", "value": None}],
        },
    )
    assert r.status_code == 422


def test_batch_atomicity(client):
    """Atomicity: first entry valid, second has unknown key — neither is inserted."""
    # Count existing measurements for weight before the test
    series_r = client.get("/api/series")
    assert series_r.status_code == 200
    weight_rows_before = next(
        (row for row in series_r.json()["rows"] if row.get("label_name") == "weight"),
        None,
    )
    before_count = 0
    if weight_rows_before:
        detail_r = client.get(f"/api/series/{weight_rows_before['id']}")
        if detail_r.status_code == 200:
            before_count = len(detail_r.json()["rows"])

    # Submit batch where second key is invalid
    r = client.post(
        "/api/measurements/batch",
        json={
            "recorded_at": "2026-04-12T08:00:00Z",
            "measurements": [
                {"key": "weight", "value": 80.5},
                {"key": "unknown_metric", "value": 1.0},
            ],
        },
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "UNKNOWN_KEY"

    # Verify no weight measurement was inserted
    if weight_rows_before:
        detail_r = client.get(f"/api/series/{weight_rows_before['id']}")
        if detail_r.status_code == 200:
            after_count = len(detail_r.json()["rows"])
            assert after_count == before_count, (
                f"Atomicity violated: expected {before_count} measurements, "
                f"got {after_count} after failed batch"
            )


def test_batch_series_not_found(client):
    """
    Batch rejects valid catalog key 'steps' that has no series row.
    Fixture fix-label-steps has label 'Daily Steps' (does not match catalog key 'steps'),
    so 'steps' key will not resolve to any series.
    """
    r = client.post(
        "/api/measurements/batch",
        json={
            "recorded_at": "2026-04-12T08:00:00Z",
            "measurements": [{"key": "steps", "value": 8000}],
        },
    )
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "SERIES_NOT_FOUND"


# ── Sparkline points format ────────────────────────────────────────────────────

def test_sparkline_points_format(client):
    """
    GET /api/series returns sparkline_points as JSON [{v, ts}] with integer ts.
    Fixture: fix-label-weight has two measurements at different timestamps.
    """
    r = client.get("/api/series")
    assert r.status_code == 200
    rows = r.json()["rows"]

    weight_row = next((row for row in rows if row.get("label_name") == "weight"), None)
    assert weight_row is not None, "Expected weight series in list"

    assert "sparkline_points" in weight_row, "sparkline_points field missing from list row"

    points = json.loads(weight_row["sparkline_points"])
    assert isinstance(points, list)
    assert len(points) == 2  # two fixture measurements

    for p in points:
        assert "v" in p and "ts" in p
        assert isinstance(p["v"], float)
        assert isinstance(p["ts"], int), f"ts should be int, got {type(p['ts'])}"

    # ts values should differ (different timestamps in fixtures)
    assert points[0]["ts"] != points[1]["ts"], "Expected different ts values for two measurements"

    # sparkline is ordered by recorded_at ASC (earlier first)
    assert points[0]["ts"] < points[1]["ts"]

    # min_value and max_value are present
    assert "min_value" in weight_row
    assert "max_value" in weight_row
    assert weight_row["min_value"] is not None
    assert weight_row["max_value"] is not None
