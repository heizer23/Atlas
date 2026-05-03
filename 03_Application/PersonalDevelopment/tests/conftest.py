"""
Pytest fixtures for PersonalDevelopment tests.

Tests exercise the TaskTracker backend (which owns the data) against the
atlas_test database. PersonalDevelopment owns no schema — it only has an
extended tasktracker.tasks schema applied via Sprint01-Core/10_schema.sql.

Standard invocation:
    docker exec atlas-tasktracker-test pytest tests/ -v

The conftest uses the TaskTracker app directly (same process). The test DB
must have the tasktracker schema (including Sprint01-Core columns) applied.
"""

import os
import sys
import pytest
import psycopg2
import psycopg2.extras

# Resolve paths so imports work both locally (from repo root) and in the
# atlas-tasktracker-test Docker container (working dir = /app, PYTHONPATH=/platform_packages).
#
# In the container the layout is:
#   /app/backend/          ← TaskTracker backend
#   /app/tests/            ← this file (PersonalDevelopment tests, copied here)
#   /platform_packages/    ← platform packages (via ENV PYTHONPATH)
#
# Locally from repo root:
#   03_Application/TaskTracker/backend/
#   03_Application/PersonalDevelopment/tests/
#   02_Platform/packages/

_this_dir = os.path.dirname(os.path.abspath(__file__))

# Try in-container layout first: /app is the TaskTracker app root
_container_app_root = "/app"
_repo_root_candidate = os.path.abspath(os.path.join(_this_dir, "../../.."))

# Use container layout when /app/backend exists, else use repo-relative paths
if os.path.isdir(os.path.join(_container_app_root, "backend")):
    _app_root = _container_app_root
    _platform_packages = "/platform_packages"
else:
    _app_root = os.path.join(_repo_root_candidate, "03_Application", "TaskTracker")
    _platform_packages = os.path.join(_repo_root_candidate, "02_Platform", "packages")

for p in (_platform_packages, _app_root):
    if p not in sys.path:
        sys.path.insert(0, p)


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
    conn = psycopg2.connect(_build_url(), cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="session", autouse=True)
def setup_schema(db_conn):
    """Ensure the full tasktracker schema (including Sprint01-Core columns) exists."""
    # schema.sql is at the TaskTracker app root in both container and local layouts
    schema_path = os.path.join(_app_root, "schema.sql")
    if not os.path.exists(schema_path):
        # Fallback: schema.sql copied alongside backend in the container
        schema_path = "/app/schema.sql"
    with open(schema_path) as f:
        ddl = f.read()
    with db_conn.cursor() as cur:
        cur.execute(ddl)


@pytest.fixture(autouse=True)
def clean_tables(db_conn):
    """Truncate tasks table and reload fixtures before each test."""
    with db_conn.cursor() as cur:
        cur.execute("truncate tasktracker.tasks cascade")

    fixtures_path = os.path.join(os.path.dirname(__file__), "fixtures.sql")
    if os.path.exists(fixtures_path):
        with open(fixtures_path) as f:
            sql = f.read()
        if sql.strip():
            with db_conn.cursor() as cur:
                cur.execute(sql)
    yield


@pytest.fixture(scope="session")
def app():
    """TaskTracker FastAPI app configured against the test DB."""
    import backend.database as db_module
    db_module.DATABASE_URL = _build_url()

    from backend.main import app as _app
    db_module.init_pool()
    return _app


@pytest.fixture
def client(app):
    """Starlette TestClient — synchronous, no running server needed."""
    from starlette.testclient import TestClient
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
