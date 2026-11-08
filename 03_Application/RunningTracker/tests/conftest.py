"""
Pytest fixtures for RunningTracker backend tests.

Tests run INSIDE the atlas-runningtracker-test container against the atlas_test database:
    docker exec atlas-runningtracker-test pytest tests/ -v
(or: make -C 01_System test-run COMPONENT=runningtracker). Production data (atlas database) is never touched.
Each test starts from the exact state defined in fixtures.sql.
"""

import os
import sys

import psycopg2
import psycopg2.extras
import pytest

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
_platform_packages = os.path.join(_repo_root, "02_Platform", "packages")
_app_root = os.path.join(_repo_root, "03_Application", "RunningTracker")
for p in (_platform_packages, _app_root):
    if p not in sys.path:
        sys.path.insert(0, p)

TOKEN_1 = "fix-token-1"   # active device fix-device-1
TOKEN_2 = "fix-token-2"   # revoked device fix-device-2
TOKEN_3 = "fix-token-3"   # active device fix-device-3

DEVICE_1 = "d1000000-0000-0000-0000-000000000001"
DEVICE_2 = "d1000000-0000-0000-0000-000000000002"
DEVICE_3 = "d1000000-0000-0000-0000-000000000003"
PREPARED_FRESH = "e1000000-0000-0000-0000-0000000000f1"
PREPARED_EXPIRED = "e1000000-0000-0000-0000-0000000000f2"
RUN_COMPLETE = "c1000000-0000-0000-0000-000000000001"
RUN_GAP = "c1000000-0000-0000-0000-000000000002"
RUN_REVOKED_UPLOADING = "c1000000-0000-0000-0000-000000000003"
RUN_REVOKED_COMPLETE = "c1000000-0000-0000-0000-000000000004"
NEW_RUN = "a1000000-0000-0000-0000-000000000001"


def auth(token: str = TOKEN_1) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _build_url() -> str:
    if url := os.environ.get("DATABASE_URL"):
        return url
    return "postgresql://{user}:{password}@{host}:{port}/{db}".format(
        user=os.environ.get("ATLAS_PG_USER", "atlas"),
        password=os.environ.get("ATLAS_PG_PASSWORD", ""),
        host=os.environ.get("ATLAS_PG_HOST", "127.0.0.1"),
        port=os.environ.get("ATLAS_PG_PORT", "5432"),
        db=os.environ.get("ATLAS_PG_DB", "atlas_test"),  # never the production database by default
    )


@pytest.fixture(scope="session")
def db_conn():
    """Raw psycopg2 connection for schema setup and verification."""
    conn = psycopg2.connect(_build_url(), cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="session", autouse=True)
def setup_schema(db_conn):
    """Ensure the runningtracker schema exists. No teardown: atlas_test is persistent."""
    with open(os.path.join(os.path.dirname(__file__), "../schema.sql")) as f:
        ddl = f.read()
    with db_conn.cursor() as cur:
        cur.execute(ddl)


@pytest.fixture(autouse=True)
def clean_tables(db_conn):
    """Truncate every table, then reload fixtures.sql, before each test."""
    with db_conn.cursor() as cur:
        cur.execute(
            "truncate runningtracker.run_route_progress, runningtracker.routes, runningtracker.runs, runningtracker.devices, runningtracker.pairing_codes, "
            "runningtracker.pairing_failures cascade"
        )
        with open(os.path.join(os.path.dirname(__file__), "fixtures.sql")) as f:
            cur.execute(f.read())
    yield


@pytest.fixture(scope="session")
def app():
    import backend.database as db_module
    db_module.DATABASE_URL = _build_url()
    from backend.main import app as _app
    db_module.init_pool()
    return _app


@pytest.fixture
def client(app):
    from starlette.testclient import TestClient
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
