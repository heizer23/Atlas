"""CAD1 (backend/cadence.py) against the shared golden file, plus GB1 (ghost cadence by progress)."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.cadence import cadence_series, compute_cadence
from backend.ghost import build_progress
from tests.test_ghost import SQUARE, T0 as GT0, geom, run_fixes

T0 = datetime(2026, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
GOLDEN = json.loads((Path(__file__).parent / "fixtures" / "cadence_golden.json").read_text())
CASES = {c["name"]: c for c in GOLDEN["cases"]}
TOL = GOLDEN["tolerance"]


def ms(x):
    return T0 + timedelta(milliseconds=x)


def run_case(c):
    return cadence_series([ms(x) for x in c["steps_ms"]], [(ms(a), ms(b)) for a, b in c["pauses_ms"]], T0, ms(c["end_ms"]))


@pytest.mark.parametrize("name", list(CASES))
def test_golden_vector(name):
    c = CASES[name]
    got = run_case(c)
    assert len(got) == len(c["expected"]), name
    for (t, spm, conf), (et, espm, econf) in zip(got, c["expected"]):
        assert t == et and abs(spm - espm) <= TOL["spm"] and abs(conf - econf) <= TOL["conf"]


def test_steady_cadence_is_estimated():
    got = run_case(CASES["steady_170"])
    assert got[0][0] >= 5.0 and all(abs(spm - 170) <= 0.1 and conf >= 0.95 for _, spm, conf in got)
    assert [b[0] - a[0] for a, b in zip(got, got[1:])] == [5.0] * (len(got) - 1)
    res = compute_cadence([ms(x) for x in CASES["steady_170"]["steps_ms"]], [], T0, ms(120000))
    assert abs(res["avg_spm"] - 170) <= 0.1 and res["algo"] == 1


def test_single_missed_step_keeps_cadence_and_lowers_confidence():
    got = run_case(CASES["single_missed_step"])
    assert all(abs(spm - 170) <= 0.1 for _, spm, _ in got)
    assert min(c for _, _, c in got) < min(c for _, _, c in run_case(CASES["steady_170"]))


def test_two_missed_steps_are_not_corrected_gap_and_no_tripling():
    got = run_case(CASES["two_missed_steps"])
    assert all(abs(spm - 170) <= 0.1 for _, spm, _ in got)           # never ~57 or 510
    ts = [t for t, _, _ in got]
    assert 20.0 not in ts                                             # the interval at ~17.6 s is a gap, window clears


def test_stop_is_a_gap_not_zero():
    got = run_case(CASES["stop_then_run"])
    ts = [t for t, _, _ in got]
    assert 25.0 not in ts and all(spm > 0 for _, spm, _ in got)


def test_running_into_walking_invents_no_steps():
    got = run_case(CASES["run_into_walk"])
    assert all(spm in (170.0, 109.1) or 100 <= spm <= 230 for _, spm, _ in got) and all(spm > 0 for _, spm, _ in got)
    assert got[-1][1] == pytest.approx(109.1, abs=0.1)               # re-anchored to the walking rhythm


def test_irregular_and_sparse_give_no_cadence_but_object_exists():
    assert run_case(CASES["irregular_stumbling"]) == [] and run_case(CASES["sparse_three_intervals"]) == []
    res = compute_cadence([ms(x) for x in CASES["sparse_three_intervals"]["steps_ms"]], [], T0, ms(20000))
    assert res == {"avg_spm": None, "series": [], "algo": 1}


def test_steps_across_a_pause_are_not_joined():
    c = CASES["pause_in_middle"]
    got = run_case(c)
    ts = [t for t, _, _ in got]
    assert not any(30.0 <= t < 40.0 for t in ts) and any(t > 40 for t in ts)
    assert 40.0 not in ts and 45.0 in ts                              # warm-up after the pause


def test_duplicates_and_order_are_tolerated():
    c = CASES["duplicates_and_shuffled"]
    clean = sorted(set(c["steps_ms"]))
    assert run_case(c) == cadence_series([ms(x) for x in clean], [], T0, ms(c["end_ms"]))


def test_steps_after_end_are_excluded_and_no_steps_gives_none():
    c = CASES["steps_after_end"]
    assert max(t for t, _, _ in run_case(c)) <= 60.0
    assert compute_cadence([], [], T0, ms(30000)) is None
    assert compute_cadence([ms(90000)], [], T0, ms(30000)) is None   # only a step after the run end


# ---- GB1: ghost cadence by progress ----

def _series(cad):
    return [(GT0 + timedelta(seconds=t), spm) for t, spm in cad]


def test_cadence_by_progress_buckets_and_absent_when_no_cadence():
    g = geom(SQUARE)
    fixes = run_fixes(SQUARE)
    cad = [(float(t), 170.0 if t < 100 else 180.0) for t in range(0, 300, 2)]
    res = build_progress(g, fixes, [], [], GT0, _series(cad))
    buckets = res.cadence_by_progress
    assert buckets and [b[0] for b in buckets] == sorted(b[0] for b in buckets)
    assert all(b[0] % 20.0 == 0 for b in buckets)
    assert buckets[0][1] == 170.0 and buckets[-1][1] == 180.0
    assert build_progress(g, fixes, [], [], GT0).cadence_by_progress is None
    assert build_progress(g, fixes, [], [], GT0, []).cadence_by_progress is None


def test_cadence_by_progress_has_gap_where_series_has_gap():
    g = geom(SQUARE)
    cad = [(float(t), 170.0) for t in range(0, 300, 2) if not 80 <= t < 120]   # 4 m/s: 320..480 m uncovered
    res = build_progress(g, run_fixes(SQUARE), [], [], GT0, _series(cad))
    starts = [b[0] for b in res.cadence_by_progress]
    assert 400.0 not in starts and 0.0 in starts


def test_cadence_by_progress_ignores_points_inside_pauses():
    g = geom(SQUARE)
    pause = (GT0 + timedelta(seconds=50), GT0 + timedelta(seconds=60))
    cad = [(float(t), 170.0) for t in range(0, 300, 2)]
    res = build_progress(g, run_fixes(SQUARE), [], [pause], GT0, _series(cad))
    assert res.cadence_by_progress
