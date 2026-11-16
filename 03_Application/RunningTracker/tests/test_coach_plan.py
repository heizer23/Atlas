"""PLAN1 / OUT1: golden cases (shared with the Kotlin parser), overrides, outcome, rendering."""

import json
import os

import pytest

from backend.coach_plan import PlanRejected, apply_overrides, compute_outcome, first_targets, plan_summary, plan_total_s, validate_plan

with open(os.path.join(os.path.dirname(__file__), "fixtures", "coach_plan_golden.json")) as f:
    GOLDEN = json.load(f)


@pytest.mark.parametrize("case", GOLDEN["cases"], ids=lambda c: c["name"])
def test_golden_plan_cases(case):
    if case["expect"] == "ok":
        assert validate_plan(case["plan"], []).type == case["plan"]["type"]
    else:
        with pytest.raises(PlanRejected) as exc:
            validate_plan(case["plan"], [])
        assert exc.value.reason == case["expect"]


@pytest.mark.parametrize("case", GOLDEN["overrides"], ids=lambda c: c["name"])
def test_golden_override_cases(case):
    if case["expect"] != "ok":
        with pytest.raises(PlanRejected) as exc:
            apply_overrides(case["plan"], case["overrides"])
        assert exc.value.reason == case["expect"]
        return
    result = apply_overrides(case["plan"], case["overrides"]).to_json()
    for seg in result["segments"]:
        if seg["kind"] == "steady":
            assert {k: seg[k] for k in ("hr", "pace", "cadence")} == case["steady"]


def test_interval_frequency_rule_only_applies_when_recent_plan_is_interval():
    interval = next(c["plan"] for c in GOLDEN["cases"] if c["name"] == "valid_interval_6x")
    validate_plan(interval, ["easy_continuous", "recovery"])
    with pytest.raises(PlanRejected) as exc:
        validate_plan(interval, ["easy_continuous", "interval"])
    assert exc.value.reason == "plan_interval_frequency"


def test_plan_does_not_mutate_input_and_overrides_leave_original_untouched():
    plan = GOLDEN["cases"][0]["plan"]
    before = json.dumps(plan, sort_keys=True)
    apply_overrides(plan, {"hr": None, "target_distance_m": 5000})
    assert json.dumps(plan, sort_keys=True) == before


def test_summary_and_first_targets_omit_unknown_targets():
    plan = GOLDEN["cases"][0]["plan"]
    assert plan_total_s(plan) == 2400
    assert plan_summary(plan) == "Easy continuous - 40 min - HR 130-145 - pace 5:30-6:30 - cadence 165-175"
    plan2 = {**plan, "segments": [{"kind": "steady", "duration_s": 600, "hr": None, "pace": None, "cadence": None}]}
    assert plan_summary(plan2) == "Easy continuous - 10 min"
    assert first_targets(plan2)["hr_min"] is None


PLAN = {"segments": [
    {"kind": "warmup", "duration_s": 100, "hr": None, "pace": None, "cadence": None},
    {"kind": "steady", "duration_s": 400, "hr": {"min": 130, "max": 145}, "pace": None, "cadence": {"min": 165, "max": 175}},
]}


def test_outcome_in_range_fractions_use_active_time_and_ignore_untargeted_points():
    # hr points at wall t=50 (warm-up: ignored), 150 (in), 250 (out), 350 (in); a 100 s pause before t=300 shifts the last two
    hr = [[50, 120], [150, 140], [250, 160], [350, 140]]
    out = compute_outcome(PLAN, 480.0, [(200.0, 300.0)], hr, [[150, 300.0]], [], 140.0, 310.0, None)
    # active: 50 -> 50 (warmup, skipped), 150 -> 150 (in), 250 -> 200 (steady, 160 out), 350 -> 250 (in)
    assert out["in_range"]["hr"] == round(2 / 3, 2)
    assert out["in_range"]["pace"] is None       # the steady segment has no pace target
    assert out["in_range"]["cadence"] is None    # no cadence points
    assert out["planned_s"] == 500 and out["done_s"] == 480.0 and out["completed"] is True  # 480 >= 0.9 * 500


def test_outcome_not_completed_below_threshold_and_points_after_plan_are_ignored():
    out = compute_outcome(PLAN, 400.0, [], [[600, 140]], [], [{"t": 150, "spm": 170, "conf": 0.9}], None, None, None)
    assert out["completed"] is False
    assert out["in_range"]["hr"] is None and out["in_range"]["cadence"] == 1.0
