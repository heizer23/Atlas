"""
Pytest fixtures for EssayCards backend tests.

Tests run INSIDE the running Docker container against the atlas_test database.
Production data (atlas database) is never touched.

Standard invocation (from anywhere):
    docker exec atlas-essaycards-test pytest tests/ -v

The atlas_test database must exist on the Postgres instance. Create it once with:
    docker exec atlas-postgres psql -U atlas -c "CREATE DATABASE atlas_test;"

The essaycards schema is created fresh each test session and never dropped.
Each test gets a clean table (truncated before the test, not after), reloaded
from tests/fixtures.sql.
"""

import os
import sys

import psycopg2
import psycopg2.extras
import pytest

# Ensure platform_packages are importable when running from repo root
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
_platform_packages = os.path.join(_repo_root, "02_Platform", "packages")
_app_root = os.path.join(_repo_root, "03_Application", "EssayCards")
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
    """Raw psycopg2 connection for schema setup/teardown, fixtures, and direct
    ingest() calls in test_ingest.py."""
    conn = psycopg2.connect(_build_url(), cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="session", autouse=True)
def setup_schema(db_conn):
    """Ensure essaycards schema and tables exist. No teardown — atlas_test is persistent."""
    schema_path = os.path.join(os.path.dirname(__file__), "../schema.sql")
    with open(schema_path) as f:
        ddl = f.read()
    with db_conn.cursor() as cur:
        cur.execute(ddl)


@pytest.fixture(autouse=True)
def clean_tables(db_conn):
    """Truncate tables then reload fixtures before each test.
    Every test starts from the exact same known state defined in fixtures.sql.
    """
    with db_conn.cursor() as cur:
        cur.execute("truncate essaycards.essays cascade")

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
    """FastAPI app with pool initialised against the test DB."""
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
