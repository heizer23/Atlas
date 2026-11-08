"""Canonical route geometry (geometry_version 1): run fixes -> simplified path with cumulative distance.

Pure functions. The path is the reference for progress/ghost comparison, so cumulative distance is measured
ALONG THE SIMPLIFIED POLYLINE (not summed over raw jitter): reference_distance_m = last cumulative value.
"""

import math
from typing import Optional

from backend.config import (
    ACCURACY_MAX_M, MAX_SPEED_MPS, MIN_STEP_M, ROUTE_LOOP_MAX_GAP_M, ROUTE_MIN_POINTS, ROUTE_SIMPLIFY_TOLERANCE_M,
)
from backend.metrics import SampleRow, haversine_m


def usable_fixes(locations: list[SampleRow]) -> list[tuple[float, float]]:
    """Fixes in seq order with unknown-or-acceptable accuracy, de-jittered like metrics A1 (min step, speed cap)."""
    out: list[tuple[float, float]] = []
    last_ts = None
    for fix in sorted(locations, key=lambda s: s.seq):
        pl = fix.payload
        lat, lon, acc = pl.get("latitude"), pl.get("longitude"), pl.get("accuracyMeters")
        if lat is None or lon is None or (acc is not None and acc > ACCURACY_MAX_M):
            continue
        if not out:
            out.append((lat, lon)); last_ts = fix.ts
            continue
        d = haversine_m(out[-1][0], out[-1][1], lat, lon)
        dt = (fix.ts - last_ts).total_seconds()
        if d < MIN_STEP_M or dt <= 0 or d / dt > MAX_SPEED_MPS:
            continue
        out.append((lat, lon)); last_ts = fix.ts
    return out


def _xy(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    lat0 = math.radians(points[0][0])
    k = math.pi / 180.0 * 6_371_000.0
    return [(p[1] * k * math.cos(lat0), p[0] * k) for p in points]


def simplify(points: list[tuple[float, float]], tolerance_m: float) -> list[tuple[float, float]]:
    """Douglas-Peucker on a local flat projection; keeps first and last point."""
    if len(points) <= 2:
        return list(points)
    xy = _xy(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = xy[a]; bx, by = xy[b]
        dx, dy = bx - ax, by - ay
        norm = math.hypot(dx, dy)
        far, far_d = -1, tolerance_m
        for i in range(a + 1, b):
            px, py = xy[i]
            d = math.hypot(px - ax, py - ay) if norm == 0 else abs(dx * (ay - py) - (ax - px) * dy) / norm
            if d > far_d:
                far, far_d = i, d
        if far != -1:
            keep[far] = True
            stack += [(a, far), (far, b)]
    return [p for p, k in zip(points, keep) if k]


def build_geometry(locations: list[SampleRow]) -> Optional[dict]:
    """{geometry: [[lat, lon, cum_m], ...], reference_distance_m, is_loop, point_count} or None if too few fixes."""
    fixes = usable_fixes(locations)
    if len(fixes) < ROUTE_MIN_POINTS:
        return None
    path = simplify(fixes, ROUTE_SIMPLIFY_TOLERANCE_M)
    geometry, cum = [], 0.0
    for i, (lat, lon) in enumerate(path):
        if i:
            cum += haversine_m(path[i - 1][0], path[i - 1][1], lat, lon)
        geometry.append([lat, lon, round(cum, 2)])
    if cum <= 0:
        return None
    gap = haversine_m(path[0][0], path[0][1], path[-1][0], path[-1][1])
    return {"geometry": geometry, "reference_distance_m": round(cum, 2), "is_loop": gap <= ROUTE_LOOP_MAX_GAP_M,
            "point_count": len(geometry)}
