"""
PreferenceStore — integration tests.

Test scenarios from Sprint01_Init/10_architecture.json deferrals.test_writer.

These tests require a live Postgres instance with the preferences schema initialized.
Set DATABASE_URL or ATLAS_PG_* environment variables before running.

Run: pytest tests/
"""

import json
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import init_pool, init_schema

client = TestClient(app)


@pytest.fixture(autouse=True, scope="module")
def setup_db():
    """Initialize pool and schema once per module."""
    init_pool()
    init_schema()
    yield


@pytest.fixture(autouse=True)
def clean_test_scope(setup_db):
    """Remove all test-scope preferences before each test."""
    from app.database import get_db
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM preferences.preferences WHERE scope LIKE 'test.%'")
        conn.commit()


# --- GET single ---

def test_get_existing_preference():
    client.put("/api/preferences/test.scope/mykey", json={"value": [1, 2, 3]})
    r = client.get("/api/preferences/test.scope/mykey")
    assert r.status_code == 200
    data = r.json()
    assert data["meta"]["total"] == 1
    assert len(data["rows"]) == 1
    assert data["rows"][0]["key"] == "mykey"
    assert data["rows"][0]["scope"] == "test.scope"
    assert "updated_at" in data["rows"][0]


def test_get_missing_preference_returns_404():
    r = client.get("/api/preferences/test.scope/nonexistent")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "PREFERENCE_NOT_FOUND"


# --- PUT ---

def test_put_creates_new_preference():
    r = client.put("/api/preferences/test.scope/newkey", json={"value": {"x": 1}})
    assert r.status_code == 200
    body = r.json()
    assert body["scope"] == "test.scope"
    assert body["key"] == "newkey"
    assert body["value"] == {"x": 1}
    assert "updated_at" in body


def test_put_overwrites_existing_preference():
    client.put("/api/preferences/test.scope/overwrite", json={"value": "first"})
    r = client.put("/api/preferences/test.scope/overwrite", json={"value": "second"})
    assert r.status_code == 200
    assert r.json()["value"] == "second"


def test_put_null_value_is_valid():
    r = client.put("/api/preferences/test.scope/nullkey", json={"value": None})
    assert r.status_code == 200
    assert r.json()["value"] is None


def test_put_missing_value_field_returns_422():
    r = client.put("/api/preferences/test.scope/novalue", json={})
    assert r.status_code == 422


# --- DELETE ---

def test_delete_existing_preference_returns_204():
    client.put("/api/preferences/test.scope/todelete", json={"value": 1})
    r = client.delete("/api/preferences/test.scope/todelete")
    assert r.status_code == 204
    # Confirm gone
    r2 = client.get("/api/preferences/test.scope/todelete")
    assert r2.status_code == 404


def test_delete_missing_preference_returns_204():
    r = client.delete("/api/preferences/test.scope/doesnotexist")
    assert r.status_code == 204


# --- GET by scope ---

def test_get_scope_returns_all_preferences():
    client.put("/api/preferences/test.multi/a", json={"value": 1})
    client.put("/api/preferences/test.multi/b", json={"value": 2})
    r = client.get("/api/preferences/test.multi")
    assert r.status_code == 200
    data = r.json()
    assert data["meta"]["total"] == 2
    keys = {row["key"] for row in data["rows"]}
    assert keys == {"a", "b"}


def test_get_empty_scope_returns_empty_dataset():
    r = client.get("/api/preferences/test.empty")
    assert r.status_code == 200
    data = r.json()
    assert data["meta"]["total"] == 0
    assert data["rows"] == []


# --- Validation ---

def test_empty_scope_returns_422():
    # FastAPI will 404 on empty path segment; test whitespace-only via query workaround
    # The real validation fires when scope resolves to whitespace-only at the path level.
    # This test exercises the router's _validate_scope_key via a direct call.
    from app.routers.preferences import _validate_scope_key
    result = _validate_scope_key("   ", "key")
    assert result is not None
    assert result.status_code == 422


def test_whitespace_only_key_returns_422():
    from app.routers.preferences import _validate_scope_key
    result = _validate_scope_key("scope", "   ")
    assert result is not None
    assert result.status_code == 422


# --- Health ---

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
