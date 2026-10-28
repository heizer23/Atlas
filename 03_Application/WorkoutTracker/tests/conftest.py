"""
Pytest fixtures for WorkoutTracker backend tests.

Tests run against the atlas_test database (never the production atlas database).
The workout schema is built from migrations/*.sql each session (all migrations are
idempotent) and the tables are truncated before every test.

Invocation (throwaway container on the Atlas network, repo mounted read-only):
    docker run --rm --network atlas-net --env-file 01_System/secrets.env \
        -e ATLAS_PG_HOST=atlas-postgres -e ATLAS_PG_DB=atlas_test \
        -v "$PWD":/repo:ro -w /repo/03_Application/WorkoutTracker python:3.11-slim \
        sh -c 'pip install -q fastapi psycopg2-binary httpx pytest && \
               PYTHONPATH=/repo/02_Platform/packages:. pytest tests -v -p no:cacheprovider'
"""

import glob
import os

import psycopg2
import psycopg2.extras
import pytest

_here = os.path.dirname(__file__)


def _build_url() -> str:
    if url := os.environ.get("DATABASE_URL"):
        return url
    return "postgresql://{user}:{password}@{host}:{port}/{db}".format(
        user=os.environ.get("ATLAS_PG_USER", "atlas"),
        password=os.environ.get("ATLAS_PG_PASSWORD", ""),
        host=os.environ.get("ATLAS_PG_HOST", "127.0.0.1"),
        port=os.environ.get("ATLAS_PG_PORT", "5432"),
        db=os.environ.get("ATLAS_PG_DB", "atlas_test"),
    )


@pytest.fixture(scope="session")
def db_conn():
    conn = psycopg2.connect(_build_url(), cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="session", autouse=True)
def setup_schema(db_conn):
    assert _build_url().rstrip("/").endswith("atlas_test"), "refusing to run against a non-test DB"
    with db_conn.cursor() as cur:
        for path in sorted(glob.glob(os.path.join(_here, "../migrations/*.sql"))):
            with open(path) as f:
                cur.execute(f.read())


@pytest.fixture(autouse=True)
def clean_tables(db_conn):
    with db_conn.cursor() as cur:
        cur.execute("truncate workout.workout_log, workout.workout_session restart identity")
    yield


@pytest.fixture(scope="session")
def app():
    import backend.database as db_module
    db_module.init_pool()
    from backend.main import app as _app
    return _app


@pytest.fixture
def client(app):
    from starlette.testclient import TestClient
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture
def seed(db_conn):
    """Insert one finished legacy-style session (no workout_session row) and return its id."""
    def _seed(workout_id, date, split, exercises):
        with db_conn.cursor() as cur:
            for i, (name, weight, reps, comment) in enumerate(exercises):
                reps = (list(reps) + [None] * 5)[:5]
                cur.execute(
                    """INSERT INTO workout.workout_log
                       (workout_id, workout_date, split, exercise, weight_kg,
                        set1_reps, set2_reps, set3_reps, set4_reps, set5_reps, comment, created_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, %s::date + %s * interval '1 minute')""",
                    (workout_id, date, split, name, weight, *reps, comment, date, i),
                )
        return workout_id
    return _seed
