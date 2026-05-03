"""
Pytest fixtures for Notifications backend tests.

Tests run INSIDE a Docker container against the atlas_test Postgres database.
FCM calls are mocked at the send_fcm_message level — no real Firebase credentials needed.

Standard invocation (from within the container):
    docker exec atlas-notifications-test pytest tests/ -v

The atlas_test database must exist on the Postgres instance. Create it once with:
    docker exec atlas-postgres psql -U atlas -c "CREATE DATABASE atlas_test;"

The notifications schema (including Sprint01 migration) is applied fresh each test session.
Each test gets clean tables (TRUNCATE before each test).
"""

import os
import sys
from unittest.mock import patch

import psycopg2
import psycopg2.extras
import pytest


def _build_url() -> str:
    if url := os.environ.get("DATABASE_URL"):
        return url
    return (
        "postgresql://{user}:{password}@{host}:{port}/{db}".format(
            user     = os.environ.get("ATLAS_PG_USER",     "atlas"),
            password = os.environ.get("ATLAS_PG_PASSWORD", ""),
            host     = os.environ.get("ATLAS_PG_HOST",     "127.0.0.1"),
            port     = os.environ.get("ATLAS_PG_PORT",     "5432"),
            db       = os.environ.get("ATLAS_PG_DB",       "atlas_test"),
        )
    )


@pytest.fixture(scope="session")
def db_conn():
    """Raw psycopg2 connection for schema setup and direct verification."""
    conn = psycopg2.connect(_build_url(), cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="session", autouse=True)
def setup_schema(db_conn):
    """Apply the base notifications schema and Sprint01 migration to atlas_test.

    Safe to re-run: uses IF NOT EXISTS / IF EXISTS guards.
    The migration ALTERs are idempotent on a fresh test DB (nullable columns
    can be set to nullable again without error).
    """
    base_schema_path = os.path.join(
        os.path.dirname(__file__), "../20_Data/schema.sql"
    )
    migration_path = os.path.join(
        os.path.dirname(__file__),
        "../Sprint01_Immediate_Notify/10_schema.sql",
    )
    with db_conn.cursor() as cur:
        with open(base_schema_path) as f:
            cur.execute(f.read())
        with open(migration_path) as f:
            cur.execute(f.read())


@pytest.fixture(autouse=True)
def clean_tables(db_conn):
    """Truncate notification and device tables before each test."""
    with db_conn.cursor() as cur:
        cur.execute("TRUNCATE notifications.notification")
        cur.execute("TRUNCATE notifications.device")
    yield


@pytest.fixture(scope="session")
def app():
    """FastAPI app with FCM and scheduler mocked.

    init_fcm() would require a real Firebase credential at startup.
    We patch it to a no-op so tests run without FCM infrastructure.
    The scheduler is also suppressed to avoid background threads in tests.
    """
    with (
        patch("backend.fcm_client.init_fcm", return_value=None),
        patch("backend.scheduler.start_scheduler", return_value=None),
        patch("backend.main.stop_scheduler", return_value=None),
    ):
        from backend.main import app as _app
        yield _app


@pytest.fixture
def client(app):
    """Starlette TestClient — synchronous, uses atlas_test Postgres pool."""
    from starlette.testclient import TestClient
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
