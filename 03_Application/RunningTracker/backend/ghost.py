"""Route progress and ghost profile (PROGRESS_ALGO_VERSION 1). Pure functions, no I/O.

Definitions
- Progress: distance in metres ALONG the reference route (its cumulative distance), not GPS-travelled distance.
- Time basis: MOVING time (seconds since start minus manual pauses); paused time counts for neither runner.
- Profile: list of [t, s, hr] ordered by t; s non-decreasing; hr is the recorded bpm near t or None (never filled).
- Comparison sign convention: time_gap_s = my_t - ghost_t(at my progress); NEGATIVE = ahead, POSITIVE = behind.
  lead_m = my_s - ghost_s(at my time); POSITIVE = ahead.
The Kotlin engine in AtlasPhone must reproduce these results (tests/fixtures/ghost_golden.json is the shared oracle).
"""

import math
from bisect import bisect_left
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from backend.config import (
    ACCURACY_MAX_M, MAX_SPEED_MPS, PROFILE_HR_MAX_AGE_S, PROFILE_MIN_SPACING_S, PROGRESS_BACK_TOLERANCE_M,
    PROGRESS_FORWARD_SLACK_M, PROGRESS_MIN_COVERAGE, PROGRESS_OFF_COURSE_M, PROGRESS_START_WINDOW_M,
)

_K = math.pi / 180.0 * 6_371_000.0


class RouteProjector:
    """Projects (lat, lon) onto a route polyline [[lat, lon, cum_m], ...] using a local flat plane."""

    def __init__(self, geometry: list[list[float]]):
        self.lat0 = math.radians(geometry[0][0])
        self.xy = [self._to_xy(p[0], p[1]) for p in geometry]
        self.cum = [p[2] for p in geometry]
        self.length = self.cum[-1]

    def _to_xy(self, lat: float, lon: float) -> tuple[float, float]:
        return lon * _K * math.cos(self.lat0), lat * _K

    def project(self, lat: float, lon: float, s_lo: float, s_hi: float) -> Optional[tuple[float, float]]:
        """Nearest point on the path within progress window [s_lo, s_hi] -> (progress_m, distance_m) or None."""
        px, py = self._to_xy(lat, lon)
        best = None
        first = max(0, bisect_left(self.cum, s_lo) - 1)
        for i in range(first, len(self.xy) - 1):
            if self.cum[i] > s_hi:
                break
            (ax, ay), (bx, by) = self.xy[i], self.xy[i + 1]
            dx, dy = bx - ax, by - ay
            seg2 = dx * dx + dy * dy
            seg_len = self.cum[i + 1] - self.cum[i]
            # Only points of this segment whose progress lies inside the window are candidates, so a fix far ahead on
            # the same long segment is measured against the window edge (and rejected as off-course), never snapped.
            u_lo = 0.0 if seg_len <= 0 else max(0.0, (s_lo - self.cum[i]) / seg_len)
            u_hi = 1.0 if seg_len <= 0 else min(1.0, (s_hi - self.cum[i]) / seg_len)
            if u_lo > u_hi:
                continue
            u = 0.0 if seg2 == 0 else ((px - ax) * dx + (py - ay) * dy) / seg2
            u = max(u_lo, min(u_hi, u))
            d = math.hypot(px - (ax + u * dx), py - (ay + u * dy))
            s = self.cum[i] + u * seg_len
            if best is None or d < best[1]:
                best = (s, d)
        return best


@dataclass
class ProgressResult:
    profile: list[list[Optional[float]]]   # [[t, s, hr], ...]
    end_progress_m: float
    coverage: float
    matched: int
    off_course: int
    qualified: bool
    reason: Optional[str]


def build_progress(
    geometry: list[list[float]],
    fixes: list[tuple[datetime, float, float, Optional[float]]],        # (ts, lat, lon, accuracy_m or None), seq order
    heart_rates: list[tuple[datetime, float]],                           # (ts, bpm)
    pauses: list[tuple[datetime, datetime]],
    started_at: datetime,
) -> ProgressResult:
    """Match a run onto the route with movement continuity and emit the progress-vs-moving-time profile."""
    proj = RouteProjector(geometry)
    pauses = sorted(pauses)

    def in_pause(ts: datetime) -> bool:
        return any(a <= ts < b for a, b in pauses)

    def moving_of(ts: datetime) -> float:
        paused = sum((b - a).total_seconds() for a, b in pauses if b <= ts)
        return (ts - started_at).total_seconds() - paused

    hr = sorted((moving_of(ts), bpm) for ts, bpm in heart_rates if bpm >= 1 and not in_pause(ts))
    hr_t = [t for t, _ in hr]

    def hr_near(t: float) -> Optional[float]:
        if not hr:
            return None
        i = bisect_left(hr_t, t)
        cands = [hr[j] for j in (i - 1, i) if 0 <= j < len(hr)]
        t_h, bpm = min(cands, key=lambda c: abs(c[0] - t))
        return float(bpm) if abs(t_h - t) <= PROFILE_HR_MAX_AGE_S else None

    profile: list[list[Optional[float]]] = []
    s_prev, t_prev = None, None
    matched = off = 0
    for ts, lat, lon, acc in fixes:
        if (acc is not None and acc > ACCURACY_MAX_M) or in_pause(ts):
            continue
        t = moving_of(ts)
        if s_prev is None:
            window = (0.0, PROGRESS_START_WINDOW_M)
        else:
            dt = max(0.0, t - t_prev)
            window = (max(0.0, s_prev - PROGRESS_BACK_TOLERANCE_M),
                      min(proj.length, s_prev + MAX_SPEED_MPS * dt + PROGRESS_FORWARD_SLACK_M))
        hit = proj.project(lat, lon, *window)
        if hit is None or hit[1] > PROGRESS_OFF_COURSE_M:
            off += 1
            continue
        s = hit[0] if s_prev is None else max(s_prev, hit[0])    # progress never goes backwards
        matched += 1
        s_prev, t_prev = s, t
        if profile and t - profile[-1][0] < PROFILE_MIN_SPACING_S:
            continue
        profile.append([round(t, 2), round(s, 2), hr_near(t)])

    end = profile[-1][1] if profile else 0.0
    coverage = end / proj.length if proj.length else 0.0
    reason = None
    if len(profile) < 2:
        reason = "too_few_matched_fixes"
    elif coverage < PROGRESS_MIN_COVERAGE:
        reason = "route_not_completed"
    return ProgressResult(profile, end, coverage, matched, off, reason is None, reason)


# ---- live comparison (reference implementation of what the phone computes) ----

def _interp(xs: list[float], ys: list[Optional[float]], x: float) -> Optional[float]:
    """Linear interpolation; None when x is outside the sampled range or a neighbour value is missing."""
    if not xs or x < xs[0] or x > xs[-1]:
        return None
    i = bisect_left(xs, x)
    if xs[i] == x:
        return ys[i]
    x0, x1, y0, y1 = xs[i - 1], xs[i], ys[i - 1], ys[i]
    if y0 is None or y1 is None:
        return None
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def ghost_time_at_progress(profile: list[list[Optional[float]]], s: float) -> Optional[float]:
    """Moving time at which the ghost first reached progress s (None beyond the ghost's end). Flat parts: earliest t."""
    ss = [p[1] for p in profile]
    if not profile or s < ss[0] or s > ss[-1]:
        return None
    i = bisect_left(ss, s)
    if ss[i] == s:
        return profile[i][0]
    (t0, s0), (t1, s1) = (profile[i - 1][0], ss[i - 1]), (profile[i][0], ss[i])
    return t0 + (t1 - t0) * (s - s0) / (s1 - s0)


def ghost_progress_at_time(profile: list[list[Optional[float]]], t: float) -> Optional[float]:
    return _interp([p[0] for p in profile], [p[1] for p in profile], t)


def ghost_hr_at_time(profile: list[list[Optional[float]]], t: float) -> Optional[float]:
    return _interp([p[0] for p in profile], [p[2] for p in profile], t)


def ghost_hr_at_progress(profile: list[list[Optional[float]]], s: float) -> Optional[float]:
    t = ghost_time_at_progress(profile, s)
    return None if t is None else ghost_hr_at_time(profile, t)


def compare(profile: list[list[Optional[float]]], my_t: float, my_s: float) -> dict:
    """The four live values. Everything the ghost cannot answer is None (never a fabricated number)."""
    ghost_t = ghost_time_at_progress(profile, my_s)
    finished = bool(profile) and my_t > profile[-1][0]
    ghost_s = profile[-1][1] if finished else ghost_progress_at_time(profile, my_t)   # a finished ghost stays at the end
    return {
        "time_gap_s": None if ghost_t is None else my_t - ghost_t,        # negative = ahead
        "lead_m": None if ghost_s is None else my_s - ghost_s,            # positive = ahead
        "ghost_hr_at_position": ghost_hr_at_progress(profile, my_s),
        "ghost_hr_at_time": ghost_hr_at_time(profile, my_t),
        "ghost_finished": finished,
    }
