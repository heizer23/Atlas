"""PROF1: measured profile (deterministic, absent not zero, domain-time windows) and inferred-update validation."""

from datetime import datetime, timedelta, timezone

from backend.coach_payload import RunFacts
from backend.coach_profile import compute_measured_profile, validate_profile_updates

T0 = datetime(2026, 3, 1, 7, 0, tzinfo=timezone.utc)


def facts(days: float, distance=5000.0, moving=1500.0, hr=145.0, cad=170.0, splits=None) -> RunFacts:
    return RunFacts(started_at=T0 + timedelta(days=days), run_kind="continuous", distance_m=distance, moving_s=moving,
                    avg_hr=hr, max_hr=170, avg_cadence_spm=cad, hrr60=None, hrr120=None, splits=splits or [],
                    pace_series=[], hr_series=[], cadence_series=[], pauses=[], plan_type=None, plan_outcome=None)


def by_key(rows):
    return {r["key"]: r for r in rows}


def test_measured_values_for_a_simple_window():
    window = [facts(10, cad=172), facts(5, cad=168), facts(0, distance=8000, moving=2400, cad=None, hr=150,
              splits=[{"km": 1, "duration_s": 280.0, "partial": False}, {"km": 2, "duration_s": 100.0, "partial": True}])]
    rows = by_key(compute_measured_profile(window))
    assert rows["natural_cadence_spm"]["value_num"] == 170           # median of 172 and 168
    assert rows["avg_step_length_m"]["value_num"] == 1.18            # mean of 5000/1500 m/s * 60 / cadence for the two runs with cadence
    assert rows["hr_at_median_pace_bpm"]["value_num"] == 147         # all three runs are 300 s/km; (145+145+150)/3
    assert rows["runs_per_week"]["value_num"] == 0.8                 # 3 runs / 4 weeks
    assert rows["km_per_week"]["value_num"] == 4.5                   # 18 km / 4 weeks
    assert rows["pr_fastest_1k_s"]["value_num"] == 280               # the partial 100 s split does not count
    assert rows["pr_longest_run_m"]["value_num"] == 8000


def test_missing_basis_means_absent_not_zero():
    rows = by_key(compute_measured_profile([facts(2, cad=None), facts(1, cad=None)]))
    assert "natural_cadence_spm" not in rows and "avg_step_length_m" not in rows
    assert "hr_at_median_pace_bpm" not in rows                       # fewer than three qualifying runs
    assert "pr_fastest_1k_s" not in rows                             # no splits
    assert all(r["value_num"] != 0 for r in rows.values())
    assert compute_measured_profile([]) == []


def test_weekly_window_uses_the_runs_own_dates():
    # the latest run is long ago in server time; only the 28 days before it count
    window = [facts(0), facts(-20), facts(-40)]
    rows = by_key(compute_measured_profile(window))
    assert rows["runs_per_week"]["value_num"] == 0.5                 # 2 of 3 runs inside 28 days


def test_inferred_updates_need_enough_runs_and_are_capped():
    updates = [{"key": "aerobic_endurance", "value": "Improving", "confidence": 0.99},
               {"key": "made_up", "value": "x", "confidence": 0.5},
               {"key": "fatigue_drift", "value": "", "confidence": 0.5},
               {"key": "aerobic_endurance", "value": "duplicate", "confidence": 0.1},
               {"key": "development_trend", "value": "Flat", "confidence": "high"}]
    assert validate_profile_updates(updates, 2) == []
    out = validate_profile_updates(updates, 3)
    assert out == [{"key": "aerobic_endurance", "value_text": "Improving", "confidence": 0.5}]   # cap 0.2 + 0.3
    assert validate_profile_updates(updates, 10)[0]["confidence"] == 0.9                          # cap 0.9
