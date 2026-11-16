"""PAY1 / EGR1: the allow-list builder. Nothing outside PAYLOAD_V1_KEYS, nothing identifying, nulls not zeros."""

import json
import re
from datetime import datetime, timedelta, timezone

from backend import coach_store
from backend.coach_payload import PAYLOAD_V1_KEYS, RunFacts, build_payload, to_wire
from backend.config import COACH_MAX_PAYLOAD_BYTES
from backend.database import get_db
from tests.conftest import RUN_COACH_1

T0 = datetime(2026, 3, 12, 7, 0, tzinfo=timezone.utc)


def assert_keys_allowed(value, allowed, path="payload"):
    """Every key at every depth is declared in the allow-list."""
    if isinstance(value, dict):
        assert isinstance(allowed, dict), f"{path} is an object but the allow-list has a leaf"
        for k, v in value.items():
            assert k in allowed, f"{path}.{k} is not allow-listed"
            assert_keys_allowed(v, allowed[k], f"{path}.{k}")
    elif isinstance(value, list):
        if isinstance(allowed, list):
            for i, item in enumerate(value):
                assert_keys_allowed(item, allowed[0], f"{path}[{i}]")
    else:
        assert allowed is None or isinstance(allowed, (dict, list)), path


def facts(days_ago: float, **kw) -> RunFacts:
    base = dict(started_at=T0 - timedelta(days=days_ago), run_kind="continuous", distance_m=5004.0, moving_s=1500.4,
                avg_hr=145.4, max_hr=160, avg_cadence_spm=168.04, hrr60=None, hrr120=None, splits=[],
                pace_series=[[5, 310.2], [65, 300.0]], hr_series=[[5, 130.0], [65, 140.0]], cadence_series=[],
                pauses=[], plan_type=None, plan_outcome=None)
    base.update(kw)
    return RunFacts(**base)


def test_payload_from_fixtures_contains_only_allow_listed_fields_and_no_identifying_values(client, db_conn):
    with db_conn.cursor() as cur:   # a named route and recovery metrics on the analysed run
        cur.execute("insert into runningtracker.routes (id, name, geometry, reference_distance_m, is_loop, point_count, geometry_version) "
                    "values ('c4000000-0000-0000-0000-000000000001', 'SECRET-ROUTE', "
                    "'[[52.123456, 13.654321, 0], [52.133456, 13.654321, 1112]]'::jsonb, 1112, false, 2, 1)")
        cur.execute("update runningtracker.runs set route_id = 'c4000000-0000-0000-0000-000000000001' where id = %s", (RUN_COACH_1,))
        cur.execute("update runningtracker.run_metrics set recovery = %s::jsonb where run_id = %s",
                    ('{"hr_end": 152, "hr_60": 138, "hr_120": 126, "hrr60": 14, "hrr120": 26, "curve": []}', RUN_COACH_1))
    with get_db() as conn:
        current, history, profile, goal, previous = coach_store.load_run_bundle(conn, RUN_COACH_1)
    payload = build_payload(current, history, profile, goal, previous)
    assert_keys_allowed(payload, PAYLOAD_V1_KEYS)
    wire = to_wire(payload)
    assert json.loads(wire) == payload
    for marker in ("SECRET-COMMENT", "SECRET-CATEGORY", "SECRET-ROUTE", "52.123456", "13.654321", RUN_COACH_1):
        assert marker not in wire
    assert not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", wire)   # uuids
    assert not re.search(r"\d{4}-\d{2}-\d{2}", wire)                                               # absolute dates
    assert not re.search(r"\d{2}:\d{2}:\d{2}", wire)                                               # clock times
    cur = payload["current_run"]
    assert cur["days_before"] == 0 and cur["weekday"] == "Thursday"
    assert cur["hrr60"] == 14 and cur["avg_cadence_spm"] == 168.0
    assert all(h["days_before"] > 0 for h in payload["history"])
    assert payload["goal"] == "Run a relaxed half marathon"


def test_missing_values_are_null_never_zero():
    payload = build_payload(facts(0, avg_hr=None, max_hr=None, avg_cadence_spm=None, pace_series=[], hr_series=[]), [], [], None, None)
    cur = payload["current_run"]
    assert cur["avg_hr"] is None and cur["max_hr"] is None and cur["avg_cadence_spm"] is None
    assert cur["avg_step_length_m"] is None and cur["hrr60"] is None
    assert cur["first_half"] == {"avg_pace_s_per_km": None, "avg_hr": None}
    assert payload["goal"] is None and payload["previous_recommendation"] is None


def test_numbers_are_rounded():
    cur = build_payload(facts(0), [], [], None, None)["current_run"]
    assert cur["distance_m"] == 5000 and cur["moving_s"] == 1500 and cur["avg_hr"] == 145
    assert cur["avg_cadence_spm"] == 168.0 and cur["avg_pace_s_per_km"] == 300


def test_series_are_bucketed_with_nulls_for_gaps():
    s = build_payload(facts(0, hr_series=[[5, 130.0], [20, 140.0], [185, 150.0]]), [], [], None, None)["current_run"]["series"]
    assert s["step_s"] == 60 and s["hr"] == [135, None, None, 150]


def test_history_is_newest_first_and_oldest_dropped_when_the_document_is_too_large():
    history = [facts(d) for d in (1, 3, 2)]
    payload = build_payload(facts(0), history, [], None, None)
    assert [h["days_before"] for h in payload["history"]] == [1, 2, 3]
    big = [facts(d + 1, splits=[], pace_series=[]) for d in range(400)]
    payload = build_payload(facts(0), big, [], "x" * 400, None)
    assert len(to_wire(payload).encode()) <= COACH_MAX_PAYLOAD_BYTES
    assert 0 < len(payload["history"]) < 400
    assert payload["history"][0]["days_before"] == 1              # newest kept, oldest dropped
    assert payload["current_run"]["days_before"] == 0             # the analysed run is never dropped


def test_previous_recommendation_carries_outcome_only():
    prev = {"plan_type": "recovery", "planned_s": 1200, "status": "completed", "id": "secret-id",
            "outcome": {"completed": True, "in_range": {"hr": 0.8, "pace": None, "cadence": None}, "avg_hr": 140.2,
                        "avg_pace_s_per_km": 330.0, "avg_cadence_spm": 168.0, "done_s": 1200}}
    p = build_payload(facts(0), [], [], None, prev)
    assert_keys_allowed(p, PAYLOAD_V1_KEYS)
    assert "secret-id" not in to_wire(p) and p["previous_recommendation"]["outcome"]["in_range"]["hr"] == 0.8
