"""Cadence estimator CAD1 (10_architecture.json invariants). Pure functions: no database, no clock.

The Kotlin CadenceEstimator in 01_System/AtlasPhone implements the same steps; tests/fixtures/cadence_golden.json
is the shared oracle. Step numbers in comments refer to invariant CAD1. Times are handled as float seconds since
the run start so both implementations see identical numbers.
"""

import math
from bisect import bisect_right
from collections import deque
from datetime import datetime, timedelta
from typing import Optional

from backend.config import (
    CAD_GAP_FACTOR, CAD_GAP_S, CAD_MAX_SPM, CAD_MIN_INTERVALS, CAD_MIN_SPM, CAD_MISSED_TOL, CAD_NORMAL_TOL,
    CAD_REANCHOR_IRREGULAR, CAD_SERIES_STEP_S, CAD_WINDOW_N, CADENCE_ALGO_VERSION,
)


def _median(values: list[float]) -> float:
    v = sorted(values)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2.0


def _segment_snapshots(steps: list[float]) -> list[tuple[float, Optional[tuple[float, float]]]]:
    """Steps 2-4 for ONE pause-free segment (sorted, distinct seconds). Returns (event_time, state) after each processed
    interval; state = (M, conf) or None while the window is shorter than CAD_MIN_INTERVALS (value would be null)."""
    snaps: list[tuple[float, Optional[tuple[float, float]]]] = []
    window: deque = deque(maxlen=CAD_WINDOW_N)   # (value, corrected)
    irregular = 0
    prev_normal = False
    lo, hi = 60.0 / CAD_MAX_SPM, 60.0 / CAD_MIN_SPM

    def median_m() -> Optional[float]:
        return _median([v for v, _ in window]) if len(window) >= CAD_MIN_INTERVALS else None

    # interval i (steps[i] - steps[i-1]) is processed when steps[i+1] is known
    for i in range(1, len(steps) - 1):
        d = steps[i] - steps[i - 1]
        d_next = steps[i + 1] - steps[i]
        m = median_m()
        if d > CAD_GAP_S or (m is not None and d > CAD_GAP_FACTOR * m):
            window.clear()
            irregular = 0
            prev_normal = False
        elif m is None:
            if lo <= d <= hi:
                window.append((d, False))
                irregular = 0
                prev_normal = True
            else:
                irregular += 1
                prev_normal = False
        elif abs(d - m) <= CAD_NORMAL_TOL * m:
            window.append((d, False))
            irregular = 0
            prev_normal = True
        elif prev_normal and abs(d - 2 * m) <= CAD_MISSED_TOL * 2 * m and abs(d_next - m) <= CAD_NORMAL_TOL * m:
            window.append((d / 2.0, True))
            window.append((d / 2.0, True))
            irregular = 0
            prev_normal = False   # previous-normal is true only after a NORMAL interval
        else:
            irregular += 1
            prev_normal = False
        if irregular >= CAD_REANCHOR_IRREGULAR:
            window.clear()
            irregular = 0
        m = median_m()
        if m is None:
            snaps.append((steps[i + 1], None))
            continue
        vals = [v for v, _ in window]
        mean = sum(vals) / len(vals)
        cv = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals)) / mean
        corrected = sum(1 for _, c in window if c) / len(window)
        conf = max(0.0, min(1.0, 1.0 - 2.0 * cv)) * (1.0 - 0.5 * corrected)
        snaps.append((steps[i + 1], (m, conf)))
    return snaps


def cadence_series(
    step_ts: list[datetime],
    pauses: list[tuple[datetime, datetime]],
    start: datetime,
    end: datetime,
) -> list[tuple[float, float, float]]:
    """Steps 1-6: (t_s_since_start, spm, conf) for every grid instant with a value; gaps are absent."""
    pauses = sorted(pauses)

    def in_pause(ts: datetime) -> bool:
        return any(a <= ts < b for a, b in pauses)

    def segment_of(ts: datetime) -> int:
        return sum(1 for _, b in pauses if b <= ts)

    # Step 1: distinct steps inside the running phase and outside pauses, grouped by segment.
    kept = sorted({ts for ts in step_ts if start <= ts <= end and not in_pause(ts)})
    segments: dict[int, list[float]] = {}
    for ts in kept:
        segments.setdefault(segment_of(ts), []).append((ts - start).total_seconds())
    snaps = {seg: _segment_snapshots(steps) for seg, steps in segments.items()}
    snap_times = {seg: [t for t, _ in s] for seg, s in snaps.items()}

    out: list[tuple[float, float, float]] = []
    k = 0
    while k * CAD_SERIES_STEP_S <= (end - start).total_seconds():
        t = k * CAD_SERIES_STEP_S
        k += 1
        tau = start + timedelta(seconds=t)
        if in_pause(tau):
            continue
        seg = segment_of(tau)
        steps = segments.get(seg)
        if not steps:
            continue
        known = [s for s in steps if s <= t]
        if not known or t - known[-1] > CAD_GAP_S:
            continue
        idx = bisect_right(snap_times[seg], t) - 1     # last interval processed at or before t
        if idx < 0 or snaps[seg][idx][1] is None:
            continue
        m, conf = snaps[seg][idx][1]
        out.append((t, round(60.0 / m, 1), round(conf, 2)))
    return out


def compute_cadence(
    step_ts: list[datetime],
    pauses: list[tuple[datetime, datetime]],
    started_at: datetime,
    end: Optional[datetime],
) -> Optional[dict]:
    """{avg_spm, series:[{t,spm,conf}], algo} or None (SQL NULL) when no step lies in the running phase."""
    pauses_sorted = sorted(pauses)
    kept = [ts for ts in step_ts
            if ts >= started_at and (end is None or ts <= end) and not any(a <= ts < b for a, b in pauses_sorted)]
    if not kept:
        return None
    series = cadence_series(step_ts, pauses, started_at, end if end is not None else max(kept))
    avg = round(sum(s for _, s, _ in series) / len(series), 1) if series else None
    return {"avg_spm": avg, "series": [{"t": t, "spm": s, "conf": c} for t, s, c in series], "algo": CADENCE_ALGO_VERSION}
