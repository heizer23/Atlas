"""Pure plan logic (PLAN1, OUT1): schema CoachPlanV1, validation, overrides, rendering, outcome.

No database, no clock, no network. The Kotlin CoachPlan (01_System/AtlasPhone running.coach) mirrors this shape;
parity is enforced by tests/fixtures/coach_plan_golden.json. Reason codes: plan_schema, plan_bounds,
plan_type_segments, plan_interval_frequency (never AI text).
"""

import copy
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from backend.config import (
    CAD_MAX_SPM, CAD_MIN_SPM, COACH_HR_BOUNDS, COACH_MAX_PLAN_S, COACH_MAX_SEGMENTS, COACH_MIN_PLAN_S,
    COACH_MIN_RANGE_CAD, COACH_MIN_RANGE_HR, COACH_MIN_RANGE_PACE, COACH_MIN_SEGMENT_S,
    COACH_OUTCOME_COMPLETED_FRACTION, COACH_PACE_BOUNDS_S_PER_KM, COACH_PLAN_SCHEMA_VERSION, COACH_PLAN_TYPES,
    COACH_SEGMENT_KINDS, COACH_TRIGGERS,
)


class PlanRejected(Exception):
    """Carries one of the four reason codes."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class CoachPlanV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int
    type: str
    title: str
    rationale: Optional[str] = None
    target_distance_m: Optional[float] = None
    segments: list[dict]
    triggers: list[str] = []

    def to_json(self) -> dict:
        return self.model_dump(mode="json")


_SEGMENT_KEYS = {"kind", "duration_s", "hr", "pace", "cadence"}
_TARGETS = {  # dimension -> (lo key, hi key, bounds, min width)
    "hr": ("min", "max", COACH_HR_BOUNDS, COACH_MIN_RANGE_HR),
    "pace": ("fast_s_per_km", "slow_s_per_km", COACH_PACE_BOUNDS_S_PER_KM, COACH_MIN_RANGE_PACE),
    "cadence": ("min", "max", (CAD_MIN_SPM, CAD_MAX_SPM), COACH_MIN_RANGE_CAD),
}


def _int(v: Any) -> Optional[int]:
    """int, or a float with an integral value (JSON from the AI may say 165.0); bool is never a number here."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v == int(v):
        return int(v)
    return None


def _check_target(dim: str, raw: Any) -> dict:
    lo_key, hi_key, bounds, min_width = _TARGETS[dim]
    if not isinstance(raw, dict) or set(raw) != {lo_key, hi_key}:
        raise PlanRejected("plan_schema")
    lo, hi = _int(raw[lo_key]), _int(raw[hi_key])
    if lo is None or hi is None:
        raise PlanRejected("plan_schema")
    if not (lo < hi and hi - lo >= min_width and bounds[0] <= lo and hi <= bounds[1]):
        raise PlanRejected("plan_bounds")
    return {lo_key: lo, hi_key: hi}


def validate_plan(raw: object, recent_plan_types: list[str]) -> CoachPlanV1:
    """PLAN1: parse + all bounds/type rules; raises PlanRejected."""
    if not isinstance(raw, dict):
        raise PlanRejected("plan_schema")
    try:
        plan = CoachPlanV1.model_validate(raw)
    except Exception:
        raise PlanRejected("plan_schema")
    if plan.schema_version != COACH_PLAN_SCHEMA_VERSION or plan.type not in COACH_PLAN_TYPES:
        raise PlanRejected("plan_schema")
    if not (1 <= len(plan.title) <= 80) or (plan.rationale is not None and len(plan.rationale) > 400):
        raise PlanRejected("plan_schema")
    if plan.target_distance_m is not None and not plan.target_distance_m > 0:
        raise PlanRejected("plan_bounds")
    if len(set(plan.triggers)) != len(plan.triggers) or any(t not in COACH_TRIGGERS for t in plan.triggers):
        raise PlanRejected("plan_schema")

    if not plan.segments:
        raise PlanRejected("plan_schema")
    if len(plan.segments) > COACH_MAX_SEGMENTS:
        raise PlanRejected("plan_bounds")
    clean: list[dict] = []
    for seg in plan.segments:
        if not isinstance(seg, dict) or not {"kind", "duration_s"} <= set(seg) or set(seg) - _SEGMENT_KEYS:
            raise PlanRejected("plan_schema")
        if seg["kind"] not in COACH_SEGMENT_KINDS:
            raise PlanRejected("plan_schema")
        duration = _int(seg["duration_s"])
        if duration is None:
            raise PlanRejected("plan_schema")
        if duration < COACH_MIN_SEGMENT_S:
            raise PlanRejected("plan_bounds")
        out: dict = {"kind": seg["kind"], "duration_s": duration}
        for dim in _TARGETS:
            out[dim] = _check_target(dim, seg[dim]) if seg.get(dim) is not None else None
        clean.append(out)
    total = sum(s["duration_s"] for s in clean)
    if not COACH_MIN_PLAN_S <= total <= COACH_MAX_PLAN_S:
        raise PlanRejected("plan_bounds")

    kinds = [s["kind"] for s in clean]
    if plan.type == "interval":
        if kinds.count("work") < 2 or kinds.count("recovery") < 1:
            raise PlanRejected("plan_type_segments")
    else:
        if any(k in ("work", "recovery") for k in kinds) or kinds.count("steady") != 1:
            raise PlanRejected("plan_type_segments")
    if plan.type == "hr_controlled" and any(s["hr"] is None for s in clean if s["kind"] == "steady"):
        raise PlanRejected("plan_type_segments")
    if plan.type == "interval" and "interval" in recent_plan_types:
        raise PlanRejected("plan_interval_frequency")

    plan.segments = clean
    return plan


def apply_overrides(plan: dict, overrides: dict) -> CoachPlanV1:
    """PlanOverrides semantics: omitted key unchanged, null clears, object sets; applied to every steady and work
    segment. Re-validated with the frequency rule off. Raises PlanRejected."""
    if set(overrides) - {"hr", "pace", "cadence", "target_distance_m"}:
        raise PlanRejected("plan_schema")
    out = copy.deepcopy(plan)
    for dim in _TARGETS:
        if dim in overrides:
            for seg in out["segments"]:
                if seg["kind"] in ("steady", "work"):
                    seg[dim] = overrides[dim]
    if "target_distance_m" in overrides:
        out["target_distance_m"] = overrides["target_distance_m"]
    return validate_plan(out, [])


def plan_total_s(plan: dict) -> int:
    return sum(int(s["duration_s"]) for s in plan["segments"])


_TYPE_LABEL = {"easy_continuous": "Easy continuous", "hr_controlled": "HR-controlled", "recovery": "Recovery",
               "endurance": "Endurance", "interval": "Interval"}


def first_targets(plan: dict) -> dict:
    """The four targets of the first steady/work segment (None = not coached)."""
    seg = next((s for s in plan["segments"] if s["kind"] in ("steady", "work")), None) or {}
    hr, pace, cad = seg.get("hr") or {}, seg.get("pace") or {}, seg.get("cadence") or {}
    return {"hr_min": hr.get("min"), "hr_max": hr.get("max"),
            "pace_fast_s_per_km": pace.get("fast_s_per_km"), "pace_slow_s_per_km": pace.get("slow_s_per_km"),
            "cad_min": cad.get("min"), "cad_max": cad.get("max")}


def _pace_text(s: int) -> str:
    return f"{s // 60}:{s % 60:02d}"


def plan_summary(plan: dict) -> str:
    """One line, e.g. 'Easy continuous - 40 min - HR 130-145 - cadence 165-175'; unknown targets omitted."""
    t = first_targets(plan)
    parts = [_TYPE_LABEL.get(plan["type"], plan["type"]), f"{round(plan_total_s(plan) / 60)} min"]
    if plan.get("target_distance_m"):
        parts.append(f"{plan['target_distance_m'] / 1000:.1f} km")
    if t["hr_min"] is not None:
        parts.append(f"HR {t['hr_min']}-{t['hr_max']}")
    if t["pace_fast_s_per_km"] is not None:
        parts.append(f"pace {_pace_text(t['pace_fast_s_per_km'])}-{_pace_text(t['pace_slow_s_per_km'])}")
    if t["cad_min"] is not None:
        parts.append(f"cadence {t['cad_min']}-{t['cad_max']}")
    return " - ".join(parts)


def _active_t(t: float, pauses: list[tuple[float, float]]) -> float:
    """Active time of a wall-clock offset: wall time minus the part of every pause before it."""
    return t - sum(max(0.0, min(t, e) - s) for s, e in pauses)


def _segment_at(plan: dict, active_t: float) -> Optional[dict]:
    start = 0
    for seg in plan["segments"]:
        if start <= active_t < start + seg["duration_s"]:
            return seg
        start += seg["duration_s"]
    return None


def _fraction(plan: dict, dim: str, points: list[tuple[float, float]], pauses: list[tuple[float, float]]) -> Optional[float]:
    lo_key, hi_key = _TARGETS[dim][:2]
    hit = total = 0
    for t, v in points:
        seg = _segment_at(plan, _active_t(t, pauses))
        target = seg.get(dim) if seg else None
        if not target:
            continue
        total += 1
        hit += target[lo_key] <= v <= target[hi_key]
    return round(hit / total, 2) if total else None


def compute_outcome(plan: dict, moving_s: float, pauses: list[tuple[float, float]], hr_series: list[list[float]],
                    pace_series: list[list[float]], cadence_series: list[dict], avg_hr: Optional[float],
                    avg_pace_s_per_km: Optional[float], avg_cadence_spm: Optional[float]) -> dict:
    """OUT1: in_range = fraction of series points inside the target range of the active-time segment at that point
    (null when no point had a target); the plan clock is active time (phone and server agree, OQ2)."""
    planned = plan_total_s(plan)
    return {
        "planned_s": planned,
        "done_s": round(moving_s, 1),
        "completed": moving_s >= COACH_OUTCOME_COMPLETED_FRACTION * planned,
        "in_range": {
            "hr": _fraction(plan, "hr", [(p[0], p[1]) for p in hr_series], pauses),
            "pace": _fraction(plan, "pace", [(p[0], p[1]) for p in pace_series], pauses),
            "cadence": _fraction(plan, "cadence", [(p["t"], p["spm"]) for p in cadence_series], pauses),
        },
        "avg_hr": avg_hr, "avg_pace_s_per_km": avg_pace_s_per_km, "avg_cadence_spm": avg_cadence_spm,
    }
