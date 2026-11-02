"""
Pytest fixtures for Kitchen backend tests.

Run INSIDE atlas-kitchen-test against the atlas_test database (never production).

Kitchen books stock through StorageTracker's HTTP API, so the tests need a live
StorageTracker on atlas_test. Start it once (idempotent) in the storagetracker test container:

    docker exec -d atlas-storagetracker-test uvicorn backend.main:app --host 0.0.0.0 --port 8000

Kitchen tests reach it at STORAGETRACKER_URL (default http://atlas-storagetracker-test:8000);
the whole suite is skipped if it is not reachable.
Each test starts with empty kitchen plans and empty StorageTracker items; recipes are re-seeded.
"""

import os
import sys

import httpx
import psycopg2
import psycopg2.extras
import pytest

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
for p in (os.path.join(_repo_root, "02_Platform", "packages"), os.path.join(_repo_root, "03_Application", "Kitchen")):
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault("STORAGETRACKER_URL", "http://atlas-storagetracker-test:8000")


def _build_url() -> str:
    return "postgresql://{user}:{password}@{host}:{port}/{db}".format(
        user=os.environ.get("ATLAS_PG_USER", "atlas"), password=os.environ.get("ATLAS_PG_PASSWORD", ""),
        host=os.environ.get("ATLAS_PG_HOST", "127.0.0.1"), port=os.environ.get("ATLAS_PG_PORT", "5432"),
        db=os.environ.get("ATLAS_PG_DB", "atlas_test"))


@pytest.fixture(scope="session")
def db_conn():
    conn = psycopg2.connect(_build_url(), cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="session", autouse=True)
def require_storagetracker():
    try:
        httpx.get(os.environ["STORAGETRACKER_URL"] + "/api/items", timeout=3).raise_for_status()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"StorageTracker test instance not reachable: {exc}", allow_module_level=True)


@pytest.fixture(scope="session", autouse=True)
def setup_schema(db_conn):
    with db_conn.cursor() as cur:
        with open(os.path.join(os.path.dirname(__file__), "../schema.sql")) as f:
            cur.execute(f.read())


@pytest.fixture(autouse=True)
def clean(db_conn):
    with db_conn.cursor() as cur:
        cur.execute("truncate kitchen.plans, kitchen.recipes cascade")
        cur.execute("truncate storagetracker.items cascade")
    from backend.seed import migrate_legacy_ingredients, seed_recipes
    import backend.database as dbm
    if dbm._pool is None:
        dbm.DATABASE_URL = _build_url()
        dbm.init_pool()
    seed_recipes()
    migrate_legacy_ingredients()
    yield


@pytest.fixture(scope="session")
def app():
    import backend.database as dbm
    dbm.DATABASE_URL = _build_url()
    from backend.main import app as _app
    dbm.init_pool()
    return _app


@pytest.fixture
def client(app):
    from starlette.testclient import TestClient
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
