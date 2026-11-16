"""Allow-list payload builder (PAY1, EGR1). The ONLY code that shapes what is sent to the AI provider.

Everything is built from explicit RunFacts fields: no database row, id, title, comment, category, route or
GPS value can reach the document, and absolute dates/times are reduced to relative days and a weekday.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from backend.coach_plan import _active_t
from backend.config import (
    COACH_MAX_PAYLOAD_BYTES, COACH_PAYLOAD_VERSION, COACH_PLAN_SCHEMA_VERSION, COACH_SERIES_STEP_S,
)

# Allowed keys at every depth. None = scalar leaf (or list of scalars), dict = nested object, [dict] = list of objects.
_IN_RANGE = {"hr": None, "pace": None, "cadence": None}
_RUN = {
    "days_before": None, "weekday": None, "run_kind": None, "distance_m": None, "moving_s": None,
    "avg_pace_s_per_km": None, "avg_hr": None, "max_hr": None, "avg_cadence_spm": None, "avg_step_length_m": None,
    "hrr60": None, "hrr120": None,
    "followed_plan": {"plan_type": None, "completed": None, "in_range": _IN_RANGE},
}
_HALF = {"avg_pace_s_per_km": None, "avg_hr": None}
PAYLOAD_V1_KEYS: dict = {
    "payload_version": None, "plan_schema_version": None, "goal": None,
    "profile": [{"key": None, "basis": None, "value_text": None, "value_num": None, "unit": None, "confidence": None}],
    "current_run": {
        **_RUN,
        "splits": [{"km": None, "duration_s": None, "pace_s_per_km": None, "avg_hr": None}],
        "first_half": _HALF, "second_half": _HALF,
        "series": {"step_s": None, "pace": None, "hr": None, "cadence": None},
    },
    "history": [_RUN],
    "previous_recommendation": {
        "plan_type": None, "planned_s": None, "status": None,
        "outcome": {"completed": None, "in_range": _IN_RANGE, "avg_hr": None, "avg_pace_s_per_km": None,
                    "avg_cadence_spm": None},
    },
}


@dataclass
class RunFacts:
    """Domain-time facts of one complete run. started_at only derives days_before/weekday/windows; never emitted."""
    started_at: datetime
    run_kind: str
    distance_m: float
    moving_s: float
    avg_hr: Optional[float]
    max_hr: Optional[int]
    avg_cadence_spm: Optional[float]
    hrr60: Optional[float]
    hrr120: Optional[float]
    splits: list[dict]
    pace_series: list[list[float]]
    hr_series: list[list[float]]
    cadence_series: list[dict]
    pauses: list[tuple[float, float]]
    plan_type: Optional[str]
    plan_outcome: Optional[dict]


def _r(v: Optional[float], digits: int = 0) -> Optional[float]:
    if v is None:
        return None
    return int(round(v)) if digits == 0 else round(v, digits)


def avg_pace(f: RunFacts) -> Optional[float]:
    return f.moving_s / (f.distance_m / 1000.0) if f.distance_m and f.distance_m > 0 and f.moving_s else None


def avg_step_length(f: RunFacts) -> Optional[float]:
    """Average speed (m/s) x 60 / cadence (spm)."""
    if not (f.avg_cadence_spm and f.moving_s and f.moving_s > 0 and f.distance_m):
        return None
    return f.distance_m / f.moving_s * 60.0 / f.avg_cadence_spm


def _in_range(o: Optional[dict]) -> dict:
    src = (o or {}).get("in_range") or {}
    return {k: src.get(k) for k in _IN_RANGE}


def _run(f: RunFacts, ref: datetime) -> dict:
    followed = None
    if f.plan_type and f.plan_outcome:
        followed = {"plan_type": f.plan_type, "completed": f.plan_outcome.get("completed"),
                    "in_range": _in_range(f.plan_outcome)}
    return {
        "days_before": max(0, (ref - f.started_at).days),
        "weekday": f.started_at.strftime("%A"),
        "run_kind": f.run_kind,
        "distance_m": _r(round(f.distance_m / 10.0) * 10),
        "moving_s": _r(f.moving_s),
        "avg_pace_s_per_km": _r(avg_pace(f)),
        "avg_hr": _r(f.avg_hr), "max_hr": f.max_hr,
        "avg_cadence_spm": _r(f.avg_cadence_spm, 1),
        "avg_step_length_m": _r(avg_step_length(f), 2),
        "hrr60": _r(f.hrr60), "hrr120": _r(f.hrr120),
        "followed_plan": followed,
    }


def _mean(vals: list[float]) -> Optional[float]:
    return sum(vals) / len(vals) if vals else None


def _bucketed(points: list[tuple[float, float]], n: int, digits: int) -> list[Optional[float]]:
    buckets: list[list[float]] = [[] for _ in range(n)]
    for t, v in points:
        i = int(t // COACH_SERIES_STEP_S)
        if 0 <= i < n:
            buckets[i].append(v)
    return [_r(_mean(b), digits) for b in buckets]


def _current(f: RunFacts) -> dict:
    out = _run(f, f.started_at)
    out["splits"] = [{"km": s["km"], "duration_s": _r(s["duration_s"]), "pace_s_per_km": _r(s["pace_s_per_km"]),
                      "avg_hr": _r(s.get("avg_hr"))} for s in f.splits if not s.get("partial")]
    half = f.moving_s / 2.0
    pace = [(t, v) for t, v in f.pace_series]
    hr = [(t, v) for t, v in f.hr_series]

    def part(points: list[tuple[float, float]], first: bool) -> list[float]:
        return [v for t, v in points if (_active_t(t, f.pauses) < half) == first]

    for name, first in (("first_half", True), ("second_half", False)):
        out[name] = {"avg_pace_s_per_km": _r(_mean(part(pace, first))), "avg_hr": _r(_mean(part(hr, first)))}
    cad = [(p["t"], p["spm"]) for p in f.cadence_series]
    last_t = max([t for t, _ in pace + hr + cad] + [0.0])
    n = int(last_t // COACH_SERIES_STEP_S) + 1
    out["series"] = {"step_s": COACH_SERIES_STEP_S, "pace": _bucketed(pace, n, 0), "hr": _bucketed(hr, n, 0),
                     "cadence": _bucketed(cad, n, 1)}
    return out


def to_wire(payload: dict) -> str:
    """Compact JSON (sorted keys, no spaces) = the exact user-message content."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build_payload(current: RunFacts, history: list[RunFacts], profile: list[dict], goal_text: Optional[str],
                  previous_plan: Optional[dict]) -> dict:
    """PAY1. history = earlier complete runs, newest first; the oldest are dropped until the document fits."""
    prev = None
    if previous_plan:
        o = previous_plan.get("outcome")
        prev = {
            "plan_type": previous_plan.get("plan_type"), "planned_s": previous_plan.get("planned_s"),
            "status": previous_plan.get("status"),
            "outcome": None if not o else {
                "completed": o.get("completed"), "in_range": _in_range(o), "avg_hr": _r(o.get("avg_hr")),
                "avg_pace_s_per_km": _r(o.get("avg_pace_s_per_km")), "avg_cadence_spm": _r(o.get("avg_cadence_spm"), 1)},
        }
    payload: dict[str, Any] = {
        "payload_version": COACH_PAYLOAD_VERSION,
        "plan_schema_version": COACH_PLAN_SCHEMA_VERSION,
        "goal": goal_text,
        "profile": [{k: p.get(k) for k in ("key", "basis", "value_text", "value_num", "unit", "confidence")} for p in profile],
        "current_run": _current(current),
        "history": [_run(h, current.started_at) for h in sorted(history, key=lambda h: h.started_at, reverse=True)],
        "previous_recommendation": prev,
    }
    while payload["history"] and len(to_wire(payload).encode("utf-8")) > COACH_MAX_PAYLOAD_BYTES:
        payload["history"].pop()
    return payload
