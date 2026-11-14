"""HR1 validity and HRR1 recovery metrics against tests/fixtures/recovery_golden.json (shared with the Kotlin tests)."""

import json
import os
from datetime import datetime, timedelta

import pytest

from backend.recovery import compute_recovery, valid_hr_points

GOLDEN = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures", "recovery_golden.json")))
T0 = datetime.fromisoformat(GOLDEN["run_finished_at"].replace("Z", "+00:00"))
TOL = GOLDEN["tolerance"]
IDS = [c["name"] for c in GOLDEN["cases"]]


def _points(case):
    return [(T0 + timedelta(seconds=t), float(b)) for t, b in case["points"]]


def _close(actual, expected):
    if expected is None:
        assert actual is None
    else:
        assert actual is not None and abs(actual - expected) <= TOL, (actual, expected)


@pytest.mark.parametrize("case", GOLDEN["cases"], ids=IDS)
def test_recovery_values_follow_hrr1_golden_vectors(case):
    e = case["expected"]
    out = compute_recovery(_points(case), T0, T0 + timedelta(seconds=case["training_end_s"]))
    assert len(valid_hr_points(_points(case))) == e["valid_count"]
    for key in ("hr_end", "hr_60", "hr_120", "hrr60", "hrr120"):
        _close(out[key], e[key])
    assert all(out[k] != 0 for k in ("hr_end", "hr_60", "hr_120", "hrr60", "hrr120"))  # null, never 0
    assert len(out["curve"]) == e["curve_len"]
    by_t = {t: v for t, v in out["curve"]}
    for t, v in e["curve_checks"]:
        _close(by_t.get(t), v)
    for t in e["curve_absent_t"]:
        assert t not in by_t  # gaps are absent, not zero-filled and not interpolated
    assert [t for t, _ in out["curve"]] == sorted(by_t)  # ascending by time


def test_validity_never_alters_values_and_removes_only_artifacts():
    case = next(c for c in GOLDEN["cases"] if c["name"] == "artifacts_ignored_step_kept")
    pts = _points(case)
    valid = valid_hr_points(pts)
    removed = {(t - T0).total_seconds() for t, _ in pts} - {(t - T0).total_seconds() for t, _ in valid}
    assert removed == {-1.0, 1.0, 58.0}
    assert all(p in pts for p in valid)  # same tuples, nothing rewritten
    assert (T0 + timedelta(seconds=90), 100.0) in valid  # genuine step change stays
