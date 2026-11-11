"""Route progress (projection with continuity), ghost profile, live comparison, stored profile and endpoints."""

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.ghost import build_progress, compare, ghost_time_at_progress, trim_idle_start
from tests.conftest import RUN_COMPLETE, TOKEN_1, auth

W = "/api/runningtracker"
T0 = datetime(2026, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
M = 1 / 111194.9266       # degrees latitude per metre
GOLDEN = json.loads((Path(__file__).parent / "fixtures" / "ghost_golden.json").read_text())


def geom(points_m):
    """Route from (north_m, east_m) vertices -> [[lat, lon, cum_m]]."""
    out, cum = [], 0.0
    for i, (n, e) in enumerate(points_m):
        if i:
            cum += math.hypot(n - points_m[i - 1][0], e - points_m[i - 1][1])
        out.append([53.59 + n * M, 10.0 + e * M / math.cos(math.radians(53.59)), cum])
    return out


def at(n, e):
    return 53.59 + n * M, 10.0 + e * M / math.cos(math.radians(53.59))


def run_fixes(path_m, speed=4.0, noise=0.0):
    """Fixes every second along a (north, east) polyline at constant speed; optional deterministic wobble."""
    pts, travelled, total = [], 0.0, 0.0
    segs = [(a, b, math.hypot(b[0] - a[0], b[1] - a[1])) for a, b in zip(path_m, path_m[1:])]
    length = sum(s[2] for s in segs)
    i = 0
    while travelled <= length:
        d, k = travelled, 0
        while k < len(segs) - 1 and d > segs[k][2]:
            d -= segs[k][2]; k += 1
        a, b, l = segs[k]
        u = min(1.0, d / l)
        n, e = a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u
        w = noise * math.sin(i * 1.7)
        lat, lon = at(n + w, e - w)
        pts.append((T0 + timedelta(seconds=i), lat, lon, None))
        travelled += speed; i += 1
    return pts


SQUARE = [(0, 0), (0, 250), (250, 250), (250, 0), (3, 0)]       # ~1 km near-loop


def test_clean_run_gives_linear_progress_and_qualifies():
    g = geom(SQUARE)
    res = build_progress(g, run_fixes(SQUARE), [], [], T0)
    assert res.qualified and res.coverage > 0.97 and res.off_course == 0
    t, s = [p[0] for p in res.profile], [p[1] for p in res.profile]
    assert s == sorted(s)
    for ti, si in zip(t, s):
        assert abs(si - 4.0 * ti) < 6          # constant 4 m/s, within projection error


def test_idle_start_is_trimmed_and_time_is_rezeroed():
    g = geom(SQUARE)
    fixes = [(T0 + timedelta(seconds=i), *at(0, 0), None) for i in range(40)]            # standing 40 s
    walk = run_fixes(SQUARE)
    fixes += [(T0 + timedelta(seconds=40) + (ts - T0), lat, lon, acc) for ts, lat, lon, acc in walk]
    res = build_progress(g, fixes, [], [], T0)
    assert res.qualified and res.profile[0][0] == 0.0 and res.profile[0][1] < 5
    assert abs(res.profile[-1][0] - (walk[-1][0] - T0).total_seconds()) < 3          # idle time gone from the ghost clock


def test_run_without_idle_start_is_left_untouched():
    prof = [[float(t), 4.0 * t, None] for t in range(60)]
    assert trim_idle_start(prof) == prof


def test_gps_noise_never_makes_progress_jump_or_go_back():
    g = geom(SQUARE)
    res = build_progress(g, run_fixes(SQUARE, noise=6.0), [], [], T0)
    s = [p[1] for p in res.profile]
    assert res.qualified and s == sorted(s)
    assert max(b - a for a, b in zip(s, s[1:])) < 25     # wiggle from +-6 m noise, but never a jump


def test_detour_off_course_is_skipped_and_progress_resumes():
    g = geom(SQUARE)
    fixes = run_fixes(SQUARE)
    off = [(ts, *at(-120, 120), None) if 40 <= i < 50 else (ts, lat, lon, acc) for i, (ts, lat, lon, acc) in enumerate(fixes)]
    res = build_progress(g, off, [], [], T0)
    assert res.off_course == 10 and res.qualified
    s = [p[1] for p in res.profile]
    assert s == sorted(s) and abs(res.end_progress_m - g[-1][2]) < 15


def test_out_and_back_does_not_jump_to_the_other_leg():
    path = [(0, 0), (400, 0), (3, 4)]            # out 400 m north, back along (almost) the same line
    g = geom(path)
    res = build_progress(g, run_fixes(path), [], [], T0)
    s = [p[1] for p in res.profile]
    assert res.qualified and s == sorted(s)
    assert abs(res.end_progress_m - g[-1][2]) < 15
    assert all(abs(p[1] - 4.0 * p[0]) < 25 for p in res.profile)


def test_pauses_are_removed_from_the_time_axis_and_hr_gaps_stay_null():
    g = geom(SQUARE)
    fixes = run_fixes(SQUARE)
    pause = (T0 + timedelta(seconds=60), T0 + timedelta(seconds=90))
    frozen = [(ts, *fixes[59][1:3], None) if pause[0] <= ts < pause[1] else (ts, la, lo, a) for ts, la, lo, a in fixes]
    hr = [(T0 + timedelta(seconds=i), 150.0) for i in range(0, 100)]       # HR stops at 100 s
    res = build_progress(g, frozen, hr, [pause], T0)
    by_t = {p[0]: p for p in res.profile}
    # wall 100 s = moving 70 s: the runner is at 4 m/s * 100 s = 400 m (the pause removed 30 s of clock, not distance)
    assert abs(by_t[70.0][1] - 400) < 8
    assert not any(60 < t < 60.5 for t in by_t)
    assert res.profile[0][2] == 150.0 and res.profile[-1][2] is None       # missing heart rate stays missing


def test_incomplete_run_does_not_qualify_as_ghost():
    g = geom(SQUARE)
    short = run_fixes(SQUARE)[:100]
    res = build_progress(g, short, [], [], T0)
    assert not res.qualified and res.reason == "route_not_completed"


def test_start_far_from_route_is_not_matched():
    g = geom(SQUARE)
    far = [(T0 + timedelta(seconds=i), *at(500, 500), None) for i in range(30)]
    res = build_progress(g, far, [], [], T0)
    assert not res.qualified and res.matched == 0 and res.reason == "too_few_matched_fixes"


def test_comparison_matches_golden_vectors():
    prof = GOLDEN["profile"]
    for case in GOLDEN["cases"]:
        got = compare(prof, case["my_t"], case["my_s"])
        for key in ("time_gap_s", "lead_m", "ghost_hr_at_position", "ghost_hr_at_time"):
            if case[key] is None:
                assert got[key] is None, (case, key, got)
            else:
                assert abs(got[key] - case[key]) < 1e-6, (case, key, got)
        assert got["ghost_finished"] is case["ghost_finished"]


def test_flat_ghost_section_returns_earliest_time():
    prof = [[0, 0, None], [10, 100, None], [20, 100, None], [30, 200, None]]
    assert ghost_time_at_progress(prof, 100) == 10


# ---- stored profile + endpoints ----

def test_profile_is_stored_when_run_is_linked_and_served_to_the_phone(client, db_conn):
    rid = client.post(f"{W}/routes", json={"run_id": RUN_COMPLETE, "name": "R"}).json()["rows"][0]["id"]
    with db_conn.cursor() as cur:
        cur.execute("select qualified, reason, profile from runningtracker.run_route_progress where run_id=%s", (RUN_COMPLETE,))
        row = cur.fetchone()
    assert row["qualified"], row["reason"]
    assert row["profile"][0][1] == 0

    p = client.get(f"{W}/native/runs/{RUN_COMPLETE}/ghost-profile", headers=auth())
    assert p.status_code == 200
    body = p.json()
    assert body["route_id"] == rid and body["time_basis"] == "moving_seconds" and len(body["points"]) >= 15
    r = client.get(f"{W}/native/routes/{rid}", headers=auth())
    assert r.status_code == 200 and r.json()["geometry"][0][2] == 0 and r.json()["geometry_version"] == 1
    assert client.get(f"{W}/native/runs/{RUN_COMPLETE}/ghost-profile").status_code == 401

    runs = client.get(f"{W}/routes/{rid}/runs").json()["rows"]
    assert len(runs) == 1 and runs[0]["ghost_eligible"] and runs[0]["is_latest"] and runs[0]["is_fastest"]

    # unlinking removes the derived profile
    client.patch(f"{W}/runs/{RUN_COMPLETE}", json={"route_id": None})
    assert client.get(f"{W}/native/runs/{RUN_COMPLETE}/ghost-profile", headers=auth()).status_code == 404


def test_prepared_run_with_route_and_ghost_selection(client):
    rid = client.post(f"{W}/routes", json={"run_id": RUN_COMPLETE, "name": "R"}).json()["rows"][0]["id"]
    # latest / fastest / explicit id all resolve to the one eligible run
    for sel in ("latest", "fastest", RUN_COMPLETE):
        r = client.post(f"{W}/prepared-runs", json={"title": "Race", "route_id": rid, "ghost": sel})
        assert r.status_code == 201, r.text
        row = r.json()["rows"][0]
        assert row["route_name"] == "R" and row["ghost_label"].startswith("2026-01-10 · 9:00")
    # the phone sees ids only
    prepared = client.get(f"{W}/native/prepared-runs", headers=auth()).json()["prepared_runs"]
    race = [p for p in prepared if p["title"] == "Race"][0]
    assert race["route_id"] == rid and race["ghost_run_id"] == RUN_COMPLETE
    plain = [p for p in prepared if p["title"] == "Easy 5k"][0]
    assert plain["route_id"] is None and plain["ghost_run_id"] is None
    # route without a ghost is fine
    ok = client.post(f"{W}/prepared-runs", json={"route_id": rid})
    assert ok.status_code == 201 and ok.json()["rows"][0]["ghost_label"] is None


def test_prepared_run_ghost_validation(client):
    rid = client.post(f"{W}/routes", json={"run_id": RUN_COMPLETE, "name": "R"}).json()["rows"][0]["id"]
    assert client.post(f"{W}/prepared-runs", json={"ghost": "latest"}).status_code == 422             # ghost needs a route
    assert client.post(f"{W}/prepared-runs", json={"route_id": "c1000000-0000-0000-0000-0000000000ff"}).status_code == 404
    assert client.post(f"{W}/prepared-runs", json={"route_id": rid, "ghost": "nonsense"}).status_code == 422
    other = "c1000000-0000-0000-0000-000000000004"                                                   # complete, but not on this route
    r = client.post(f"{W}/prepared-runs", json={"route_id": rid, "ghost": other})
    assert r.status_code == 409 and r.json()["error"]["code"] == "GHOST_NOT_ELIGIBLE"
    client.patch(f"{W}/runs/{RUN_COMPLETE}", json={"route_id": None})                               # no eligible run left
    assert client.post(f"{W}/prepared-runs", json={"route_id": rid, "ghost": "fastest"}).status_code == 409


def test_fix_far_ahead_on_the_same_long_segment_is_not_snapped_to_the_window_edge():
    g = geom([(0, 0), (0, 1000)])                      # one 1 km segment
    base = run_fixes([(0, 0), (0, 1000)])
    gap = base[:20] + base[60:]                        # 160 m of fixes missing in the middle, 1 s apart
    res = build_progress(g, [(T0 + timedelta(seconds=i), la, lo, a) for i, (_, la, lo, a) in enumerate(gap)], [], [], T0)
    s_at = {p[0]: p[1] for p in res.profile}
    assert res.off_course >= 1                         # the first fix after the jump cannot be matched (qualified, not faked)
    assert max(s_at.values()) > 900


def test_progress_matches_the_shared_oracle_fixture():
    """Same input and expected output are asserted by the Kotlin GhostEngineTest (parity with the phone)."""
    f = json.loads((Path(__file__).parent / "fixtures" / "ghost_progress_golden.json").read_text())
    start = datetime.fromtimestamp(f["started_at_ms"] / 1000, tz=timezone.utc)
    ts = lambda ms: datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    fixes = [(ts(a), lat, lon, acc) for a, lat, lon, acc in f["fixes"]]
    pauses = [(ts(a), ts(b)) for a, b in f["pauses_ms"]]
    res = build_progress(f["geometry"], fixes, [], pauses, start)
    assert [[p[0], p[1]] for p in res.profile] == f["expected"]["profile"]
    assert (res.matched, res.off_course, res.qualified) == (f["expected"]["matched"], f["expected"]["off_course"], f["expected"]["qualified"])
