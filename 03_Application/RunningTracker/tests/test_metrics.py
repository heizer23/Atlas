"""Algorithm A1: golden vectors (shared with the Kotlin RunMetricsTest) and recompute persistence."""

import json
import os
from datetime import datetime

import pytest

from backend.metrics import PauseRow, SampleRow, compute_metrics, recompute_and_store
from tests.conftest import RUN_COMPLETE

GOLDEN = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures", "metrics_golden.json")))
TOL = GOLDEN["tolerances"]


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _run(case):
    return compute_metrics(
        [SampleRow(l["seq"], _ts(l["timestamp"]), l) for l in case["locations"]],
        [SampleRow(h["seq"], _ts(h["timestamp"]), h) for h in case["heart_rates"]],
        [PauseRow(_ts(p["started_at"]), _ts(p["ended_at"])) for p in case["pauses"]],
        _ts(case["started_at"]),
    )


def _close(actual, expected, tol):
    if expected is None:
        assert actual is None
    else:
        assert actual is not None and abs(actual - expected) <= tol, (actual, expected)


@pytest.mark.parametrize("case", GOLDEN["cases"], ids=[c["name"] for c in GOLDEN["cases"]])
def test_metrics_follow_algorithm_a1_golden_vectors(case):
    m, e = _run(case), case["expected"]
    _close(m.server_distance_m, e["distance_m"], TOL["distance_m"])
    assert len(m.splits) == len(e["splits"])
    for got, want in zip(m.splits, e["splits"]):
        assert got["km"] == want["km"] and got["partial"] == want["partial"]
        _close(got["distance_m"], want["distance_m"], TOL["distance_m"])
        _close(got["duration_s"], want["duration_s"], TOL["duration_s"])
        _close(got["pace_s_per_km"], want["pace_s_per_km"], TOL["pace_s_per_km"])
        _close(got["avg_hr"], want["avg_hr"], TOL["hr"])
    _close(m.avg_hr, e["avg_hr"], TOL["hr"])
    assert m.max_hr == e["max_hr"]
    assert [p[0] for p in m.pace_series] == [p[0] for p in e["pace_series"]]
    for got, want in zip(m.pace_series, e["pace_series"]):
        _close(got[1], want[1], TOL["pace_s_per_km"])
    assert [p[0] for p in m.hr_series] == [p[0] for p in e["hr_series"]]
    for got, want in zip(m.hr_series, e["hr_series"]):
        _close(got[1], want[1], TOL["hr"])


def test_fixes_inside_pauses_add_nothing_and_first_fix_after_a_pause_adds_no_distance():
    case = next(c for c in GOLDEN["cases"] if c["name"] == "route_with_pause")
    with_pause = _run(case).server_distance_m
    without = _run({**case, "pauses": []}).server_distance_m
    # The athlete moved 240 m during the 60 s pause; without the pause rule that distance would be counted.
    assert without - with_pause > 200
    assert abs(with_pause - 952.0) <= 0.5


def test_metrics_recompute_is_stable(db_conn):
    def snapshot():
        with db_conn.cursor() as cur:
            cur.execute(
                "select algo_version, server_distance_m, avg_hr, max_hr, splits, pace_series, hr_series "
                "from runningtracker.run_metrics where run_id = %s", (RUN_COMPLETE,))
            metrics = cur.fetchone()
            cur.execute("select seq, stream, sample_ts, payload from runningtracker.run_samples where run_id = %s order by seq", (RUN_COMPLETE,))
            return metrics, cur.fetchall()

    from backend.database import get_db, init_pool
    import backend.database as db_module
    if db_module._pool is None:
        init_pool()
    with get_db() as conn:
        recompute_and_store(conn, RUN_COMPLETE)
        conn.commit()
    first_metrics, first_samples = snapshot()
    with get_db() as conn:
        recompute_and_store(conn, RUN_COMPLETE)
        conn.commit()
    second_metrics, second_samples = snapshot()
    assert first_metrics == second_metrics
    assert first_samples == second_samples  # raw samples are never touched
    assert len(first_samples) == 40
    assert first_metrics["algo_version"] == 1 and first_metrics["server_distance_m"] > 0
