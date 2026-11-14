"""Heart-rate validity (HR1) and heart-rate recovery (HRR1): pure functions, no database, no clock.

The Kotlin HrSmoothing.validSamples / RecoveryMetrics in 01_System/AtlasPhone implement the same rules;
tests/fixtures/recovery_golden.json is the shared oracle. Inputs are plain (timestamp, bpm) tuples so this
module does not depend on metrics.py.
"""

import statistics
from datetime import datetime, timedelta
from typing import Optional

from backend.config import (
    HR_SPIKE_MAX_BPM_PER_S, HR_VALID_MAX_BPM, HR_VALID_MIN_BPM, HRR_END_AFTER_S, HRR_END_BEFORE_S,
    HRR_MIN_VALID_SAMPLES, HRR_POINT_HALF_WINDOW_S, HRR_T1_S, HRR_T2_S, RECOVERY_CURVE_STEP_S,
    RECOVERY_CURVE_WINDOW_S,
)

Point = tuple[datetime, float]


def valid_hr_points(points: list[Point]) -> list[Point]:
    """HR1: range check, then drop isolated spikes (both range-valid neighbours differ by more than the limit).
    First/last range-valid samples are never spikes; neighbours are the range-valid neighbours. Values are never altered."""
    ranged = sorted((p for p in points if HR_VALID_MIN_BPM <= p[1] <= HR_VALID_MAX_BPM), key=lambda p: p[0])
    valid: list[Point] = []
    for i, (ts, bpm) in enumerate(ranged):
        if 0 < i < len(ranged) - 1:
            pts, pb = ranged[i - 1]
            nts, nb = ranged[i + 1]
            dt_prev = max((ts - pts).total_seconds(), 1.0)
            dt_next = max((nts - ts).total_seconds(), 1.0)
            if abs(bpm - pb) / dt_prev > HR_SPIKE_MAX_BPM_PER_S and abs(bpm - nb) / dt_next > HR_SPIKE_MAX_BPM_PER_S:
                continue
        valid.append((ts, bpm))
    return valid


def _point_value(valid: list[Point], a: datetime, b: datetime, training_end: datetime) -> Optional[float]:
    if b > training_end:
        return None  # window not fully observed
    vals = [bpm for ts, bpm in valid if a <= ts <= b]
    if len(vals) < HRR_MIN_VALID_SAMPLES:
        return None
    return float(statistics.median(vals))


def compute_recovery(points: list[Point], run_finished_at: datetime, training_end: datetime) -> dict:
    """HRR1. points = all raw HR samples of the run (running + recovery). Scalars are float|None, never 0 for missing."""
    valid = valid_hr_points(points)
    t0 = run_finished_at

    def at(offset_s: float, before: float, after: float) -> Optional[float]:
        return _point_value(valid, t0 + timedelta(seconds=offset_s - before),
                            t0 + timedelta(seconds=offset_s + after), training_end)

    hr_end = at(0.0, HRR_END_BEFORE_S, HRR_END_AFTER_S)
    hr_60 = at(HRR_T1_S, HRR_POINT_HALF_WINDOW_S, HRR_POINT_HALF_WINDOW_S)
    hr_120 = at(HRR_T2_S, HRR_POINT_HALF_WINDOW_S, HRR_POINT_HALF_WINDOW_S)

    curve: list[list[float]] = []
    half = RECOVERY_CURVE_WINDOW_S / 2
    k = 0
    while t0 + timedelta(seconds=k * RECOVERY_CURVE_STEP_S) <= training_end:
        tau = t0 + timedelta(seconds=k * RECOVERY_CURVE_STEP_S)
        vals = [bpm for ts, bpm in valid
                if tau - timedelta(seconds=half) <= ts <= tau + timedelta(seconds=half) and ts <= training_end]
        if vals:
            curve.append([k * RECOVERY_CURVE_STEP_S, sum(vals) / len(vals)])
        k += 1

    return {
        "hr_end": hr_end, "hr_60": hr_60, "hr_120": hr_120,
        "hrr60": None if hr_end is None or hr_60 is None else hr_end - hr_60,
        "hrr120": None if hr_end is None or hr_120 is None else hr_end - hr_120,
        "curve": curve,
    }
