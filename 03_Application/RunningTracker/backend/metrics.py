"""Algorithm A1 (algo_version 1): pure computation plus persistence of run_metrics.

The Kotlin RunMetrics in 01_System/AtlasPhone implements the same steps; tests/fixtures/metrics_golden.json
is the shared oracle. Step numbers refer to invariant A1 in 10_architecture.json.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from psycopg2.extras import Json

from backend.config import (
    ACCURACY_MAX_M, ALGO_VERSION, MAX_SPEED_MPS, MIN_STEP_M, PARTIAL_SPLIT_MIN_M,
    SERIES_BUCKET_S, SMOOTHING_WINDOW_S, SPLIT_DISTANCE_M,
)

EARTH_RADIUS_M = 6_371_000.0


@dataclass
class SampleRow:
    seq: int
    ts: datetime
    payload: dict


@dataclass
class PauseRow:
    started_at: datetime
    ended_at: datetime


@dataclass
class MetricsResult:
    server_distance_m: float
    avg_hr: Optional[float]
    max_hr: Optional[int]
    splits: list[dict] = field(default_factory=list)
    pace_series: list[list[float]] = field(default_factory=list)
    hr_series: list[list[float]] = field(default_factory=list)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


@dataclass
class _Point:
    wall: float     # seconds since started_at
    moving: float   # wall minus earlier pause durations
    dist: float     # cumulative distance
    segment: int    # number of pauses fully before this fix


def compute_metrics(
    locations: list[SampleRow],
    heart_rates: list[SampleRow],
    pauses: list[PauseRow],
    started_at: datetime,
) -> MetricsResult:
    pauses = sorted(pauses, key=lambda p: p.started_at)

    def in_pause(ts: datetime) -> bool:
        return any(p.started_at <= ts < p.ended_at for p in pauses)

    def segment_of(ts: datetime) -> int:
        return sum(1 for p in pauses if p.ended_at <= ts)

    def moving_of(ts: datetime) -> float:
        paused = sum((p.ended_at - p.started_at).total_seconds() for p in pauses if p.ended_at <= ts)
        return (ts - started_at).total_seconds() - paused

    # Steps 1-3: usable fixes, anchors, distance.
    points: list[_Point] = []
    anchor = None  # (lat, lon, ts, nanos, segment)
    distance = 0.0
    for fix in sorted(locations, key=lambda s: s.seq):
        pl = fix.payload
        acc, lat, lon = pl.get("accuracyMeters"), pl.get("latitude"), pl.get("longitude")
        # Unknown accuracy (e.g. FIT imports carry none) is kept, never invented; known-bad accuracy is dropped.
        if (acc is not None and acc > ACCURACY_MAX_M) or lat is None or lon is None:
            continue
        if in_pause(fix.ts):
            continue
        seg = segment_of(fix.ts)
        nanos = pl.get("elapsedRealtimeNanos")
        if anchor is None or anchor[4] != seg:
            anchor = (lat, lon, fix.ts, nanos, seg)
            points.append(_Point((fix.ts - started_at).total_seconds(), moving_of(fix.ts), distance, seg))
            continue
        d = haversine_m(anchor[0], anchor[1], lat, lon)
        if d < MIN_STEP_M:
            continue
        if nanos is not None and anchor[3] is not None and nanos - anchor[3] > 0:
            dt = (nanos - anchor[3]) / 1e9
        else:
            dt = (fix.ts - anchor[2]).total_seconds()
        if dt <= 0 or d / dt > MAX_SPEED_MPS:
            continue
        distance += d
        anchor = (lat, lon, fix.ts, nanos, seg)
        points.append(_Point((fix.ts - started_at).total_seconds(), moving_of(fix.ts), distance, seg))

    # Step 5: smoothed pace at every accepted fix.
    pace_points: list[tuple[float, float]] = []  # (wall, pace s/km)
    lo = 0  # earliest candidate j; moves forward only (thresholds grow with the moving-time axis)
    for i, p in enumerate(points):
        if i == 0 or points[i - 1].segment != p.segment:
            lo = i  # a new pause-free segment never looks back across the pause
        while lo < i and points[lo].moving < p.moving - SMOOTHING_WINDOW_S:
            lo += 1
        if lo < i and p.dist - points[lo].dist >= 1.0:
            q = points[lo]
            pace_points.append((p.wall, (p.moving - q.moving) / (p.dist - q.dist) * 1000.0))

    # Step 7: heart rate outside pauses (bpm >= 1).
    hr = [(s.ts, s.payload.get("bpm")) for s in sorted(heart_rates, key=lambda s: s.seq)]
    hr = [(ts, bpm) for ts, bpm in hr if isinstance(bpm, (int, float)) and bpm >= 1 and not in_pause(ts)]
    avg_hr = sum(b for _, b in hr) / len(hr) if hr else None
    max_hr = int(max(b for _, b in hr)) if hr else None

    # Step 6: splits.
    splits: list[dict] = []
    if points:
        def split_hr(t0: float, t1: float, inclusive_end: bool) -> Optional[float]:
            vals = [b for ts, b in hr if t0 <= moving_of(ts) and (moving_of(ts) <= t1 if inclusive_end else moving_of(ts) < t1)]
            return sum(vals) / len(vals) if vals else None

        t_prev = points[0].moving
        k = 1
        for a, b in zip(points, points[1:]):
            while b.dist > a.dist and a.dist < k * SPLIT_DISTANCE_M <= b.dist:
                t_cross = a.moving + (k * SPLIT_DISTANCE_M - a.dist) / (b.dist - a.dist) * (b.moving - a.moving)
                duration = t_cross - t_prev
                splits.append({
                    "km": k, "distance_m": SPLIT_DISTANCE_M, "duration_s": duration,
                    "pace_s_per_km": duration, "avg_hr": split_hr(t_prev, t_cross, False), "partial": False,
                })
                t_prev = t_cross
                k += 1
        remainder = distance - (k - 1) * SPLIT_DISTANCE_M
        if remainder >= PARTIAL_SPLIT_MIN_M:
            t_end = points[-1].moving
            duration = t_end - t_prev
            splits.append({
                "km": k, "distance_m": remainder, "duration_s": duration,
                "pace_s_per_km": duration / remainder * 1000.0, "avg_hr": split_hr(t_prev, t_end, True), "partial": True,
            })

    # Step 8: series bucketed by run (wall) time; null values omitted.
    pace_buckets: dict[int, float] = {}
    for wall, pace in pace_points:
        pace_buckets[int(wall // SERIES_BUCKET_S)] = pace  # last point per bucket
    hr_buckets: dict[int, list[float]] = {}
    for ts, bpm in hr:
        wall = (ts - started_at).total_seconds()
        hr_buckets.setdefault(int(wall // SERIES_BUCKET_S), []).append(bpm)

    return MetricsResult(
        server_distance_m=distance,
        avg_hr=avg_hr,
        max_hr=max_hr,
        splits=splits,
        pace_series=[[b * SERIES_BUCKET_S, v] for b, v in sorted(pace_buckets.items())],
        hr_series=[[b * SERIES_BUCKET_S, sum(v) / len(v)] for b, v in sorted(hr_buckets.items())],
    )


def recompute_and_store(conn, run_id: str) -> None:
    """Load samples and pauses ordered by seq, run compute_metrics, upsert run_metrics with ALGO_VERSION."""
    with conn.cursor() as cur:
        cur.execute("select started_at from runningtracker.runs where id = %s", (run_id,))
        started_at = cur.fetchone()["started_at"]
        cur.execute(
            "select stream, seq, sample_ts, payload from runningtracker.run_samples where run_id = %s order by seq",
            (run_id,),
        )
        locations, heart_rates = [], []
        for r in cur.fetchall():
            row = SampleRow(r["seq"], r["sample_ts"], r["payload"])
            (locations if r["stream"] == "location" else heart_rates).append(row)
        cur.execute("select started_at, ended_at from runningtracker.run_pauses where run_id = %s", (run_id,))
        pauses = [PauseRow(r["started_at"], r["ended_at"]) for r in cur.fetchall()]

        m = compute_metrics(locations, heart_rates, pauses, started_at)
        cur.execute(
            """
            insert into runningtracker.run_metrics
                (run_id, algo_version, computed_at, server_distance_m, avg_hr, max_hr, splits, pace_series, hr_series)
            values (%s, %s, now(), %s, %s, %s, %s, %s, %s)
            on conflict (run_id) do update set
                algo_version = excluded.algo_version, computed_at = excluded.computed_at,
                server_distance_m = excluded.server_distance_m, avg_hr = excluded.avg_hr, max_hr = excluded.max_hr,
                splits = excluded.splits, pace_series = excluded.pace_series, hr_series = excluded.hr_series
            """,
            (run_id, ALGO_VERSION, m.server_distance_m, m.avg_hr, m.max_hr,
             Json(m.splits), Json(m.pace_series), Json(m.hr_series)),
        )
