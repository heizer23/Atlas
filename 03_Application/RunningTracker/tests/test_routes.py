"""Route library: geometry from a run, create/list/patch/delete, run linking (route_id round trip)."""

import math
from datetime import datetime, timedelta, timezone

from backend.metrics import SampleRow
from backend.route_geometry import build_geometry, simplify, usable_fixes
from tests.conftest import RUN_COMPLETE, RUN_GAP

W = "/api/runningtracker"
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
M = 1 / 111194.9266  # degrees latitude per metre


def fixes(points, step_s=1):
    return [SampleRow(i + 1, T0 + timedelta(seconds=i * step_s),
                      {"latitude": lat, "longitude": lon, "accuracyMeters": None}) for i, (lat, lon) in enumerate(points)]


def square_loop(side_m=200, per_side=50):
    """Rectangle run clockwise at ~4 m/s with 1 Hz fixes, ~1 m jitter."""
    pts, n = [], per_side
    for i in range(n):
        pts.append((53.59 + 0 * M, 10.0 + (i * side_m / n) * M / math.cos(math.radians(53.59))))
    for i in range(n):
        pts.append((53.59 + (i * side_m / n) * M, 10.0 + side_m * M / math.cos(math.radians(53.59))))
    for i in range(n):
        pts.append((53.59 + side_m * M, 10.0 + (side_m - i * side_m / n) * M / math.cos(math.radians(53.59))))
    for i in range(n):
        pts.append((53.59 + (side_m - i * side_m / n) * M, 10.0))
    pts.append((53.59 + 1 * M, 10.0))
    return pts


def test_simplify_keeps_corners_and_cumulative_distance_is_along_the_path():
    geo = build_geometry(fixes(square_loop()))
    assert geo["is_loop"] is True
    assert geo["point_count"] < 20                                   # 200 fixes collapse to the corners
    assert abs(geo["reference_distance_m"] - 800) < 12
    cum = [g[2] for g in geo["geometry"]]
    assert cum[0] == 0 and cum == sorted(cum) and cum[-1] == geo["reference_distance_m"]


def test_out_and_back_and_not_loop():
    line = [(53.59 + i * 3 * M, 10.0) for i in range(100)]
    geo = build_geometry(fixes(line))
    assert geo["is_loop"] is False and geo["point_count"] == 2


def test_too_few_fixes_and_bad_accuracy_are_not_a_route():
    assert build_geometry(fixes([(53.59, 10.0)] * 5)) is None
    bad = [SampleRow(i, T0 + timedelta(seconds=i), {"latitude": 53.59 + i * 3 * M, "longitude": 10.0, "accuracyMeters": 80.0})
           for i in range(1, 30)]
    assert usable_fixes(bad) == []


def test_simplify_endpoints_survive():
    pts = [(53.59 + i * 3 * M, 10.0) for i in range(10)]
    assert simplify(pts, 4.0) == [pts[0], pts[-1]]


def test_create_list_patch_delete_round_trip(client):
    # the fixture run's 20 northward fixes (4 m/s) are enough for a route
    r = client.post(f"{W}/routes", json={"run_id": RUN_COMPLETE, "name": " Stadtpark Small ", "description": "loop"})
    assert r.status_code == 201, r.text
    row = r.json()["rows"][0]
    assert row["name"] == "Stadtpark Small" and row["run_count"] == 1 and row["best_moving_s"] == 540
    assert row["reference_distance_m"] > 50
    rid = row["id"]

    run = client.get(f"{W}/runs/{RUN_COMPLETE}").json()["rows"][0]
    assert run["route_id"] == rid and run["route_name"] == "Stadtpark Small"
    assert [x["id"] for x in client.get(f"{W}/routes").json()["rows"]] == [rid]

    # duplicate name (case-insensitive) rejected
    dup = client.post(f"{W}/routes", json={"run_id": RUN_COMPLETE, "name": "stadtpark small"})
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "ROUTE_NAME_TAKEN"

    # patch: omitted unchanged, null description clears, null name rejected
    assert client.patch(f"{W}/routes/{rid}", json={"name": "Stadtpark S"}).json()["rows"][0]["description"] == "loop"
    assert client.patch(f"{W}/routes/{rid}", json={"description": None}).json()["rows"][0]["description"] is None
    assert client.patch(f"{W}/routes/{rid}", json={"name": None}).status_code == 422

    # in use -> cannot delete; unlink via run patch, then delete
    assert client.delete(f"{W}/routes/{rid}").status_code == 409
    assert client.patch(f"{W}/runs/{RUN_COMPLETE}", json={"route_id": None}).json()["rows"][0]["route_id"] is None
    assert client.delete(f"{W}/routes/{rid}").status_code == 200
    assert client.get(f"{W}/routes").json()["rows"] == []


def test_create_requires_completed_run_and_known_ids(client):
    assert client.post(f"{W}/routes", json={"run_id": RUN_GAP, "name": "x"}).status_code == 409   # still uploading
    assert client.post(f"{W}/routes", json={"run_id": "c1000000-0000-0000-0000-0000000000ff", "name": "x"}).status_code == 404
    assert client.post(f"{W}/routes", json={"run_id": "nope", "name": "x"}).status_code == 404
    assert client.patch(f"{W}/runs/{RUN_COMPLETE}", json={"route_id": "c1000000-0000-0000-0000-0000000000ff"}).status_code == 404


def test_link_second_run_to_route(client):
    rid = client.post(f"{W}/routes", json={"run_id": RUN_COMPLETE, "name": "A"}).json()["rows"][0]["id"]
    r = client.patch(f"{W}/runs/{RUN_GAP}", json={"route_id": rid})
    assert r.json()["rows"][0]["route_name"] == "A"
    row = client.get(f"{W}/routes/{rid}").json()["rows"][0]
    assert row["run_count"] == 1                               # only complete runs count; the uploading one does not
