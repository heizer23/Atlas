"""FIT import (source 'fit_import') and the run category round trip. Uses a synthetic FIT built in-test."""

import struct
from pathlib import Path

from backend.fit_import import build_run, import_fit, parse_fit
from tests.conftest import RUN_COMPLETE

W = "/api/runningtracker"
T0 = 1162907396  # FIT seconds


def make_fit(n: int = 120, hr_every: int = 1) -> bytes:
    """Little-endian FIT: one record definition (ts, lat, lon, hr, dist, speed) + n records, session message."""
    def definition(local, glob, fields):
        return bytes([0x40 | local, 0, 0]) + struct.pack("<HB", glob, len(fields)) + b"".join(bytes(f) for f in fields)
    rec_def = definition(0, 20, [(253, 4, 0x86), (0, 4, 0x85), (1, 4, 0x85), (3, 1, 0x02), (5, 4, 0x86), (6, 2, 0x84)])
    ses_def = definition(1, 18, [(7, 4, 0x86), (8, 4, 0x86), (9, 4, 0x86)])
    body = rec_def
    lat0 = int(53.59 / (180.0 / 2**31))
    for i in range(n):
        hr = 150 if i % hr_every == 0 else 0xFF
        # 3 m/s north: 0.00002697 deg per second
        body += bytes([0]) + struct.pack("<IiiBIH", T0 + i, lat0 + int(i * 3 * 0.00000899 / (180.0 / 2**31)),
                                         int(10.0 / (180.0 / 2**31)), hr, i * 300, 3000)
    body += ses_def + bytes([1]) + struct.pack("<III", n * 1000, n * 1000, (n - 1) * 300)
    header = struct.pack("<BBHI4s", 12, 0x20, 2000, len(body), b".FIT")
    return header + body + b"\0\0"


def test_parse_and_convert_keeps_raw_values_and_missing_stays_missing():
    run = build_run(make_fit(n=60, hr_every=2))
    locs = [s for s in run["samples"] if s[0] == "location"]
    hrs = [s for s in run["samples"] if s[0] == "heart_rate"]
    assert len(locs) == 60 and len(hrs) == 30                      # missing HR is skipped, not filled
    assert [s[1] for s in run["samples"]] == list(range(1, 91))      # shared contiguous sequence
    p = locs[0][2]
    assert abs(p["latitude"] - 53.59) < 1e-5 and abs(p["longitude"] - 10.0) < 1e-5
    assert p["accuracyMeters"] is None and p["bearingDegrees"] is None   # not fabricated
    assert abs(p["speedMetersPerSecond"] - 3.0) < 1e-9
    assert p["timestamp"] == "2026-11-06T13:49:56.000Z"
    assert run["elapsed_s"] == 60.0 and run["distance_m"] == 177.0
    assert len(parse_fit(make_fit(5))[20]) == 5


def test_import_creates_complete_run_with_metrics_and_is_idempotent(tmp_path, app, db_conn):
    f = Path(tmp_path) / "r.fit"
    f.write_bytes(make_fit(n=300))
    run_id, created = import_fit(f, "Easy Continuous")
    again, created2 = import_fit(f, "Easy Continuous")
    assert created and not created2 and run_id == again
    with db_conn.cursor() as cur:
        cur.execute("select status, source, category, device_id, run_type from runningtracker.runs where id=%s", (run_id,))
        r = cur.fetchone()
        assert (r["status"], r["source"], r["category"], r["device_id"], r["run_type"]) == (
            "complete", "fit_import", "Easy Continuous", None, "continuous")
        cur.execute("select count(*) n from runningtracker.run_samples where run_id=%s", (run_id,))
        assert cur.fetchone()["n"] == 600
        cur.execute("select server_distance_m, avg_hr from runningtracker.run_metrics where run_id=%s", (run_id,))
        m = cur.fetchone()
        assert 800 < m["server_distance_m"] < 920 and m["avg_hr"] == 150   # ~3 m/s * 299 s, no accuracy field needed


def test_category_round_trip(client):
    assert client.get(f"{W}/runs/{RUN_COMPLETE}").json()["rows"][0]["category"] is None
    r = client.patch(f"{W}/runs/{RUN_COMPLETE}", json={"category": "  Easy Continuous "})
    assert r.json()["rows"][0]["category"] == "Easy Continuous"
    # omitted category leaves it unchanged; explicit null clears it
    r = client.patch(f"{W}/runs/{RUN_COMPLETE}", json={"comment": "x"})
    assert r.json()["rows"][0]["category"] == "Easy Continuous"
    r = client.patch(f"{W}/runs/{RUN_COMPLETE}", json={"category": None})
    assert r.json()["rows"][0]["category"] is None
    assert client.patch(f"{W}/runs/{RUN_COMPLETE}", json={"category": "x" * 61}).status_code == 422
