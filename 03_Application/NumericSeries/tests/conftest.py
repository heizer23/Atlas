"""
Pytest fixtures for NumericSeries backend tests.

Tests run INSIDE the running Docker container against the atlas_test database.
Production data (atlas database) is never touched.

Standard invocation:
    docker exec atlas-numeric-series pytest tests/ -v

The atlas_test database must exist on the Postgres instance:
    docker exec atlas-postgres psql -U atlas -c "CREATE DATABASE atlas_test;"

The numeric_series schema is created idempotently each session.
Each test starts from the same fixture state (tables truncated and reloaded).
"""

import os
import sys
import pytest
import psycopg2
import psycopg2.extras

# Ensure platform_packages are importable
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
_platform_packages = os.path.join(_repo_root, "02_Platform", "packages")
_app_root = os.path.join(_repo_root, "03_Application", "NumericSeries")
for p in (_platform_packages, _app_root):
    if p not in sys.path:
        sys.path.insert(0, p)


def _build_url() -> str:
    if url := os.environ.get("DATABASE_URL"):
        db_from_url = url.rstrip("/").rsplit("/", 1)[-1]
        if db_from_url != "atlas_test":
            raise RuntimeError(
                f"SAFETY ABORT: DATABASE_URL points to '{db_from_url}', not 'atlas_test'. "
                "Tests must never run against production data."
            )
        return url
    db = os.environ.get("ATLAS_PG_DB", "atlas_test")
    if db != "atlas_test":
        raise RuntimeError(
            f"SAFETY ABORT: ATLAS_PG_DB='{db}' — tests must run against 'atlas_test' only. "
            "Use the test container: docker exec atlas-numeric-series-test pytest tests/ -v"
        )
    return (
        "postgresql://{user}:{password}@{host}:{port}/{db}".format(
            user=os.environ.get("ATLAS_PG_USER", "atlas"),
            password=os.environ.get("ATLAS_PG_PASSWORD", ""),
            host=os.environ.get("ATLAS_PG_HOST", "127.0.0.1"),
            port=os.environ.get("ATLAS_PG_PORT", "5432"),
            db=db,
        )
    )


@pytest.fixture(scope="session")
def db_conn():
    """Raw psycopg2 connection for schema setup and fixture loading."""
    conn = psycopg2.connect(_build_url(), cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="session", autouse=True)
def setup_schema(db_conn):
    """Ensure numeric_series schema and tables exist (idempotent)."""
    schema_path = os.path.join(os.path.dirname(__file__), "../Sprint01/20_Data/schema.sql")
    with open(schema_path) as f:
        ddl = f.read()
    with db_conn.cursor() as cur:
        cur.execute(ddl)


@pytest.fixture(autouse=True)
def clean_tables(db_conn):
    """Truncate tables and reload fixtures before each test."""
    with db_conn.cursor() as cur:
        cur.execute("TRUNCATE numeric_series.measurements CASCADE")
        cur.execute("TRUNCATE numeric_series.series CASCADE")
        # Also clean any test labels we inserted (safe: these are fix- prefixed)
        cur.execute("DELETE FROM labels.labels WHERE id LIKE 'fix-%'")

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
    """FastAPI app initialised against the test DB.

    database.py reads ATLAS_PG_* from the environment at pool init time.
    When ATLAS_PG_DB=atlas_test is already set in the container (by docker exec -e),
    this is a no-op. If running locally without that env var, we set it here.
    """
    os.environ.setdefault("ATLAS_PG_DB", "atlas_test")

    from backend.main import app as _app
    import backend.database as db_module
    db_module.init_pool()
    return _app


@pytest.fixture
def client(app):
    """Starlette TestClient — synchronous, no running server needed."""
    from starlette.testclient import TestClient
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
