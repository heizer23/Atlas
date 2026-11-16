"""Pure profile logic (PROF1). coach_profile imports coach_payload, never the reverse."""

import statistics
from datetime import timedelta
from typing import Optional

from backend.coach_payload import RunFacts, avg_pace, avg_step_length
from backend.config import (
    COACH_HR_PACE_MIN_RUNS, COACH_INFERRED_KEYS, COACH_MIN_RUNS_INFERRED, COACH_PACE_MATCH_TOL,
)


def _row(key: str, value: float, digits: int, unit: str, n_runs: int) -> dict:
    v = round(value, digits) if digits else int(round(value))
    return {"key": key, "value_text": f"{v} {unit}", "value_num": float(v), "unit": unit, "n_runs": n_runs}


def compute_measured_profile(window: list[RunFacts]) -> list[dict]:
    """window = latest complete runs, newest first. A key without a basis is absent, never 0."""
    rows: list[dict] = []
    if not window:
        return rows

    cads = [f.avg_cadence_spm for f in window if f.avg_cadence_spm]
    if cads:
        rows.append(_row("natural_cadence_spm", statistics.median(cads), 0, "spm", len(cads)))
    steps = [s for s in (avg_step_length(f) for f in window) if s]
    if steps:
        rows.append(_row("avg_step_length_m", sum(steps) / len(steps), 2, "m", len(steps)))

    paces = [(avg_pace(f), f) for f in window]
    paces = [(p, f) for p, f in paces if p]
    if paces:
        median_pace = statistics.median([p for p, _ in paces])
        qualifying = [f.avg_hr for p, f in paces
                      if abs(p - median_pace) <= COACH_PACE_MATCH_TOL * median_pace and f.avg_hr is not None]
        if len(qualifying) >= COACH_HR_PACE_MIN_RUNS:
            rows.append(_row("hr_at_median_pace_bpm", sum(qualifying) / len(qualifying), 0, "bpm", len(qualifying)))

    # Frequency and volume over the 28 days ending at the latest run's own date (domain time, never the server clock).
    latest = max(f.started_at for f in window)
    recent = [f for f in window if f.started_at > latest - timedelta(days=28)]
    rows.append(_row("runs_per_week", len(recent) / 4.0, 1, "runs/week", len(recent)))
    rows.append(_row("km_per_week", sum(f.distance_m or 0 for f in recent) / 1000.0 / 4.0, 1, "km/week", len(recent)))

    full_km = [s["duration_s"] for f in window for s in f.splits if not s.get("partial") and s.get("duration_s")]
    if full_km:
        rows.append(_row("pr_fastest_1k_s", min(full_km), 0, "s", len(window)))
    longest = max((f.distance_m for f in window if f.distance_m), default=None)
    if longest:
        rows.append(_row("pr_longest_run_m", longest, 0, "m", len(window)))
    return rows


def validate_profile_updates(updates: list[dict], n_runs: int) -> list[dict]:
    """PROF1: [] below COACH_MIN_RUNS_INFERRED; else allowed keys only, text 1..200, confidence capped; first entry per key wins."""
    if n_runs < COACH_MIN_RUNS_INFERRED:
        return []
    cap = min(0.9, 0.2 + 0.1 * n_runs)
    out: list[dict] = []
    seen: set[str] = set()
    for u in updates:
        if not isinstance(u, dict):
            continue
        key, value, conf = u.get("key"), u.get("value"), u.get("confidence")
        if key not in COACH_INFERRED_KEYS or key in seen:
            continue
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= 200:
            continue
        if isinstance(conf, bool) or not isinstance(conf, (int, float)) or not 0 <= conf <= 1:
            continue
        seen.add(key)
        out.append({"key": key, "value_text": value.strip(), "confidence": round(min(float(conf), cap), 2)})
    return out
