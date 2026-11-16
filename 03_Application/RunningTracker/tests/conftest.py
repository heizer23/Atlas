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
RUN_RECOVERY = "c1000000-0000-0000-0000-000000000005"          # complete, run_finished_at set, recovery stored
RUN_RECOVERY_NOHR = "c1000000-0000-0000-0000-000000000006"     # complete, run_finished_at set, no heart rate
RUN_RECOVERY_UPLOAD = "c1000000-0000-0000-0000-000000000007"   # uploading, recovery-phase HR already stored
RUN_CADENCE = "c1000000-0000-0000-0000-000000000008"           # complete, steps + stored cadence object
RUN_CADENCE_EMPTY = "c1000000-0000-0000-0000-000000000009"     # complete, 3 unusable steps, empty cadence series
RUN_CADENCE_UPLOAD = "c1000000-0000-0000-0000-00000000000a"    # uploading, steps incl. after run end / inside a pause
NEW_RUN = "a1000000-0000-0000-0000-000000000001"


def auth(token: str = TOKEN_1) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _build_url() -> str:
    """Refuse any destination other than atlas_test: fixtures TRUNCATE tables."""
    url = _build_url_unchecked()
    db = url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
    if db != "atlas_test":
        raise RuntimeError(f"SAFETY ABORT: test database is '{db}', not 'atlas_test'.")
    return url


def _build_url_unchecked() -> str:
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
            "runningtracker.pairing_failures, runningtracker.coach_plans, runningtracker.coach_analyses, "
            "runningtracker.coach_ai_calls, runningtracker.coach_profile_items, runningtracker.coach_settings cascade"
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


# ── Ghost Coach: fake provider (tests never perform a network call; the test container has no key) ─────────────────

FAKE_KEY = "sk-test-KEY-0123456789"
RUN_COACH_1 = "c2000000-0000-0000-0000-000000000001"   # newest coach fixture run (route + marker strings)
RUN_COACH_2 = "c2000000-0000-0000-0000-000000000002"
RUN_COACH_3 = "c2000000-0000-0000-0000-000000000003"
RUN_COACH_4 = "c2000000-0000-0000-0000-000000000004"
PLAN_RECOMMENDED = "c3000000-0000-0000-0000-000000000001"
PLAN_ACCEPTED = "c3000000-0000-0000-0000-000000000002"
PLAN_ACCEPTED_LINKED = "c3000000-0000-0000-0000-000000000003"
PLAN_DISREGARDED = "c3000000-0000-0000-0000-000000000004"
PLAN_INTERVAL = "c3000000-0000-0000-0000-000000000005"

VALID_PLAN = {
    "schema_version": 1, "type": "easy_continuous", "title": "Easy 30", "rationale": "Relaxed.", "target_distance_m": None,
    "segments": [{"kind": "steady", "duration_s": 1800, "hr": {"min": 130, "max": 145}, "pace": None, "cadence": None}],
    "triggers": [],
}


def ai_answer(**over) -> dict:
    body = {"assessment": "Solid steady run.", "previous_recommendation_effect": None, "profile_updates": [],
            "next_session": VALID_PLAN}
    body.update(over)
    return body


class FakeProvider:
    """httpx.MockTransport that records every request. `answer` is a dict (sent as the provider's text block),
    a str (sent verbatim) or a callable(request) -> httpx.Response."""

    def __init__(self):
        import httpx
        self.requests: list = []
        self.answer = ai_answer()
        self.transport = httpx.MockTransport(self._handle)

    def _handle(self, request):
        import json
        import httpx
        self.requests.append(request)
        if callable(self.answer):
            return self.answer(request)
        text = self.answer if isinstance(self.answer, str) else json.dumps(self.answer)
        return httpx.Response(200, json={"content": [{"type": "text", "text": text}]})

    def user_content(self, i: int = 0) -> str:
        import json
        return json.loads(self.requests[i].content)["messages"][0]["content"]


@pytest.fixture
def provider(monkeypatch, client):
    """Configured fake provider (key + model in the environment, transport seam installed)."""
    from backend.routers import coach as coach_router
    fake = FakeProvider()
    monkeypatch.setenv("RUNNINGTRACKER_COACH_API_KEY", FAKE_KEY)
    monkeypatch.setenv("RUNNINGTRACKER_COACH_MODEL", "fake-model")
    monkeypatch.delenv("RUNNINGTRACKER_COACH_API_URL", raising=False)
    monkeypatch.setattr(coach_router, "_transport", fake.transport)
    return fake
