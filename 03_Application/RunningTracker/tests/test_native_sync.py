"""begin / samples / finish / ownership / adoption / idempotency / verification scenarios (10_test_spec.md)."""

from datetime import datetime, timedelta, timezone

from tests.conftest import (
    NEW_RUN, PREPARED_EXPIRED, PREPARED_FRESH, RUN_COMPLETE, RUN_GAP, RUN_REVOKED_COMPLETE,
    RUN_REVOKED_UPLOADING, TOKEN_1, TOKEN_3, auth, DEVICE_1,
)

NATIVE = "/api/runningtracker/native"
T0 = datetime(2026, 2, 1, 7, 0, 0, tzinfo=timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def loc(seq, t):
    return {"stream": "location", "seq": seq, "payload": {
        "type": "location.sample", "timestamp": iso(T0 + timedelta(seconds=t)),
        "latitude": 52.0 + 4.0 * t / 111194.9266, "longitude": 13.0, "accuracyMeters": 5.0,
        "speedMetersPerSecond": None, "altitudeMeters": None, "bearingDegrees": None, "elapsedRealtimeNanos": None}}


def hr(seq, t, bpm=150):
    return {"stream": "heart_rate", "seq": seq, "payload": {
        "type": "heartRate.sample", "timestamp": iso(T0 + timedelta(seconds=t)), "bpm": bpm, "rrIntervalsMs": None,
        "source": "bluetooth", "elapsedRealtimeNanos": None}}


def batch(n_loc, n_hr):
    """Shared increasing seq: locations then heart rates interleaved (loc, loc, hr, ...)."""
    out, seq, li, hi = [], 1, 0, 0
    while li < n_loc or hi < n_hr:
        if li < n_loc and (hi >= n_hr or li * n_hr <= hi * n_loc):
            li += 1
            out.append(loc(seq, seq))
        else:
            hi += 1
            out.append(hr(seq, seq))
        seq += 1
    return out


def begin(client, run_id=NEW_RUN, token=TOKEN_1, started_at=T0):
    return client.post(f"{NATIVE}/runs/{run_id}/begin", json={"started_at": iso(started_at)}, headers=auth(token))


def put(client, run_id, samples, token=TOKEN_1):
    return client.put(f"{NATIVE}/runs/{run_id}/samples", json={"samples": samples}, headers=auth(token))


def finish_body(last_seq, loc_n, hr_n, pauses=None, finished=None):
    return {
        "finished_at": iso(finished or T0 + timedelta(seconds=last_seq + 1)), "elapsed_s": last_seq + 1.0, "moving_s": float(last_seq),
        "distance_m": 4.0 * last_seq, "last_seq": last_seq, "expected_counts": {"location": loc_n, "heart_rate": hr_n},
        "pauses": pauses or [],
    }


def finish(client, run_id, body, token=TOKEN_1):
    return client.post(f"{NATIVE}/runs/{run_id}/finish", json=body, headers=auth(token))


def _row(db_conn, sql, *params):
    with db_conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


# ── Prepared runs ────────────────────────────────────────────────────────────

def test_prepared_run_lifecycle(client):
    web = "/api/runningtracker/prepared-runs"
    # fixtures contain prepared runs; the lifecycle is checked on a newly created one
    created = client.post(web, json={"title": "Sunday long"})
    assert created.status_code == 201
    row = created.json()["rows"][0]
    assert created.json()["meta"]["total"] == 1 and len(row["short_id"]) == 6
    expires = datetime.fromisoformat(row["expires_at"])
    assert 47 * 3600 < (expires - datetime.now(timezone.utc)).total_seconds() <= 48 * 3600

    listed = client.get(f"{NATIVE}/prepared-runs", headers=auth()).json()["prepared_runs"]
    assert row["id"] in [p["id"] for p in listed]
    one = client.get(f"{NATIVE}/prepared-runs/{row['id']}", headers=auth())
    assert one.status_code == 200 and one.json()["title"] == "Sunday long" and one.json()["short_id"] == row["short_id"]

    assert client.delete(f"/api/runningtracker/runs/{row['id']}").status_code == 200
    assert client.get(f"{NATIVE}/prepared-runs/{row['id']}", headers=auth()).status_code == 404


def test_expired_prepared_run_is_hidden_from_the_phone(client):
    listed = client.get(f"{NATIVE}/prepared-runs", headers=auth()).json()["prepared_runs"]
    ids = [p["id"] for p in listed]
    assert PREPARED_FRESH in ids and PREPARED_EXPIRED not in ids
    assert client.get(f"{NATIVE}/prepared-runs/{PREPARED_EXPIRED}", headers=auth()).status_code == 404

    web = client.get("/api/runningtracker/prepared-runs").json()["rows"]
    expired = next(r for r in web if r["id"] == PREPARED_EXPIRED)
    assert expired["is_expired"] is True
    assert next(r for r in web if r["id"] == PREPARED_FRESH)["is_expired"] is False


# ── begin ────────────────────────────────────────────────────────────────────

def test_begin_is_idempotent_and_returns_cursors(client, db_conn):
    first, second = begin(client), begin(client)
    for r in (first, second):
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "uploading" and body["run_id"] == NEW_RUN
        assert body["high_seq"] == {"location": 0, "heart_rate": 0} and body["contiguous_seq"] == 0
    assert len(_row(db_conn, "select 1 from runningtracker.runs where id = %s", NEW_RUN)) == 1

    # a run owned by another non-revoked device answers 404
    assert begin(client, token=TOKEN_3).status_code == 404


def test_begin_on_a_prepared_run_converts_it(client, db_conn):
    r = begin(client, run_id=PREPARED_FRESH)
    assert r.status_code == 200 and r.json()["status"] == "uploading"
    row = _row(db_conn, "select status, started_at, device_id from runningtracker.runs where id = %s", PREPARED_FRESH)[0]
    assert row["status"] == "uploading" and row["started_at"] == T0 and str(row["device_id"]) == DEVICE_1
    again = begin(client, run_id=PREPARED_FRESH, started_at=T0 + timedelta(hours=1))
    assert again.status_code == 200
    assert _row(db_conn, "select started_at from runningtracker.runs where id = %s", PREPARED_FRESH)[0]["started_at"] == T0


def test_begin_adopts_a_run_of_a_revoked_device(client, db_conn):
    r = begin(client, run_id=RUN_REVOKED_UPLOADING)
    assert r.status_code == 200
    assert str(_row(db_conn, "select device_id from runningtracker.runs where id = %s", RUN_REVOKED_UPLOADING)[0]["device_id"]) == DEVICE_1
    assert begin(client, run_id=RUN_REVOKED_COMPLETE).status_code == 404


# ── samples ──────────────────────────────────────────────────────────────────

def test_sample_upload_is_idempotent(client, db_conn):
    begin(client)
    samples = batch(100, 30)
    first = put(client, NEW_RUN, samples)
    assert first.status_code == 200
    assert first.json()["stored"] == 130 and first.json()["duplicates"] == 0
    assert first.json()["contiguous_seq"] == 130
    second = put(client, NEW_RUN, samples)
    assert second.json()["stored"] == 0 and second.json()["duplicates"] == 130
    assert _row(db_conn, "select count(*) as n from runningtracker.run_samples where run_id = %s", NEW_RUN)[0]["n"] == 130

    stored = {(r["stream"], r["seq"]): r["payload"] for r in _row(
        db_conn, "select stream, seq, payload from runningtracker.run_samples where run_id = %s", NEW_RUN)}
    for s in samples:
        assert stored[(s["stream"], s["seq"])] == s["payload"]
    assert stored[("location", 1)]["speedMetersPerSecond"] is None  # nullable fields stay null


def test_duplicate_seq_with_different_payload_never_overwrites_raw_data(client, db_conn):
    begin(client)
    original = loc(7, 7)
    assert put(client, NEW_RUN, [original]).json()["stored"] == 1
    changed = loc(7, 7)
    changed["payload"]["latitude"] = 10.0
    r = put(client, NEW_RUN, [changed])
    assert r.json()["stored"] == 0 and r.json()["duplicates"] == 1
    payload = _row(db_conn, "select payload from runningtracker.run_samples where run_id = %s and seq = 7", NEW_RUN)[0]["payload"]
    assert payload == original["payload"]


def test_batch_limit_and_validation(client, db_conn):
    begin(client)
    too_many = [loc(i, i) for i in range(1, 2002)]
    bad_ts = loc(1, 1)
    bad_ts["payload"]["timestamp"] = "not-a-timestamp"
    zero_seq = loc(0, 1)
    for bad in (too_many, [bad_ts], [loc(5, 5), zero_seq], [loc(5, 5), bad_ts]):
        r = put(client, NEW_RUN, bad)
        assert r.status_code == 422, r.text
        assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert _row(db_conn, "select count(*) as n from runningtracker.run_samples where run_id = %s", NEW_RUN)[0]["n"] == 0


def test_samples_rejected_for_a_complete_run(client):
    r = put(client, RUN_COMPLETE, [loc(41, 41)])
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "RUN_NOT_UPLOADABLE"


def test_resume_cursors_reflect_stored_data(client):
    r = begin(client, run_id=RUN_GAP)
    body = r.json()
    assert body["contiguous_seq"] == 4
    assert body["high_seq"] == {"location": 19, "heart_rate": 20}
    sent = put(client, RUN_GAP, [loc(21, 21), hr(22, 22)])
    assert sent.status_code == 200
    assert sent.json()["contiguous_seq"] == 4
    assert sent.json()["high_seq"] == {"location": 21, "heart_rate": 22}
    filled = put(client, RUN_GAP, [loc(5, 5), hr(6, 6), loc(7, 7), hr(8, 8)])
    assert filled.json()["contiguous_seq"] == 22


def test_finish_on_a_still_prepared_run_is_a_conflict(client):
    r = finish(client, PREPARED_FRESH, finish_body(1, 1, 0))
    assert r.status_code == 409
    assert put(client, PREPARED_FRESH, [loc(1, 1)]).status_code == 409


# ── finish ───────────────────────────────────────────────────────────────────

def test_finish_verifies_and_completes(client, db_conn):
    begin(client)
    put(client, NEW_RUN, batch(100, 30))
    pauses = [
        {"started_at": iso(T0 + timedelta(seconds=20)), "ended_at": iso(T0 + timedelta(seconds=30)), "started_elapsed_s": 20, "ended_elapsed_s": 30},
        {"started_at": iso(T0 + timedelta(seconds=60)), "ended_at": iso(T0 + timedelta(seconds=70)), "started_elapsed_s": 60, "ended_elapsed_s": 70},
    ]
    body = finish_body(130, 100, 30, pauses)
    r = finish(client, NEW_RUN, body)
    assert r.status_code == 200
    out = r.json()
    assert out["result"] == "complete" and out["verified_counts"] == {"location": 100, "heart_rate": 30}
    assert out["missing_seq_ranges"] == [] and out["count_mismatch"] == []
    run = _row(db_conn, "select status, distance_m, elapsed_s from runningtracker.runs where id = %s", NEW_RUN)[0]
    assert run["status"] == "complete" and run["distance_m"] == 520.0
    assert _row(db_conn, "select count(*) as n from runningtracker.run_pauses where run_id = %s", NEW_RUN)[0]["n"] == 2
    metrics = _row(db_conn, "select algo_version, server_distance_m from runningtracker.run_metrics where run_id = %s", NEW_RUN)
    assert len(metrics) == 1 and metrics[0]["algo_version"] == 1 and metrics[0]["server_distance_m"] > 0

    again = finish(client, NEW_RUN, body)
    assert again.status_code == 200 and again.json()["result"] == "complete"
    assert again.json()["verified_counts"] == out["verified_counts"]
    assert _row(db_conn, "select count(*) as n from runningtracker.run_pauses where run_id = %s", NEW_RUN)[0]["n"] == 2
    assert _row(db_conn, "select count(*) as n from runningtracker.run_metrics where run_id = %s", NEW_RUN)[0]["n"] == 1


def test_finish_category_fills_empty_but_never_overwrites(client, db_conn):
    begin(client)
    put(client, NEW_RUN, batch(10, 0))
    r = finish(client, NEW_RUN, {**finish_body(10, 10, 0), "category": "4 km \u00b7 HR 140"})
    assert r.status_code == 200
    q = "select category from runningtracker.runs where id = %s"
    assert _row(db_conn, q, NEW_RUN)[0]["category"] == "4 km \u00b7 HR 140"
    db_conn.cursor().execute("update runningtracker.runs set category = 'Web edit' where id = %s", (NEW_RUN,))
    db_conn.commit()
    finish(client, NEW_RUN, {**finish_body(10, 10, 0), "category": "other"})
    assert _row(db_conn, q, NEW_RUN)[0]["category"] == "Web edit"


def test_finish_detects_gaps(client, db_conn):
    r = finish(client, RUN_GAP, finish_body(20, 10, 10))
    assert r.status_code == 200
    out = r.json()
    assert out["result"] == "incomplete"
    assert out["missing_seq_ranges"] == [{"start": 5, "end": 8}]
    assert {m["stream"] for m in out["count_mismatch"]} == {"location", "heart_rate"}
    run = _row(db_conn, "select status, distance_m from runningtracker.runs where id = %s", RUN_GAP)[0]
    assert run["status"] == "uploading" and run["distance_m"] == 80.0  # summary stored even when incomplete

    put(client, RUN_GAP, [loc(5, 5), hr(6, 6), loc(7, 7), hr(8, 8)])
    done = finish(client, RUN_GAP, finish_body(20, 10, 10))
    assert done.json()["result"] == "complete"


def test_finish_detects_count_mismatch_without_gaps(client):
    begin(client)
    put(client, NEW_RUN, batch(10, 5))
    r = finish(client, NEW_RUN, finish_body(15, 10, 9))
    out = r.json()
    assert out["result"] == "incomplete"
    assert out["missing_seq_ranges"] == []
    assert out["count_mismatch"] == [{"stream": "heart_rate", "expected": 9, "stored": 5}]


def test_finish_rejects_inconsistent_times(client, db_conn):
    begin(client)
    put(client, NEW_RUN, batch(10, 0))
    r = finish(client, NEW_RUN, finish_body(10, 10, 0, finished=T0 - timedelta(seconds=5)))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    run = _row(db_conn, "select status, finished_at, distance_m from runningtracker.runs where id = %s", NEW_RUN)[0]
    assert run["status"] == "uploading" and run["finished_at"] is None and run["distance_m"] is None


def test_gps_only_run_completes_with_empty_heart_rate_series(client, db_conn):
    begin(client)
    put(client, NEW_RUN, [loc(i, i) for i in range(1, 61)])
    r = finish(client, NEW_RUN, finish_body(60, 60, 0))
    assert r.json()["result"] == "complete"
    assert _row(db_conn, "select avg_hr, max_hr from runningtracker.run_metrics where run_id = %s", NEW_RUN)[0] == {"avg_hr": None, "max_hr": None}
    series = client.get(f"/api/runningtracker/runs/{NEW_RUN}/series", params={"metric": "heart_rate"})
    assert series.status_code == 200
    assert series.json()["rows"] == [] and series.json()["meta"]["total"] == 0
    pace = client.get(f"/api/runningtracker/runs/{NEW_RUN}/series", params={"metric": "pace"}).json()
    assert pace["meta"]["total"] > 0 and all(row["value"] > 0 for row in pace["rows"])


def test_ownership_on_every_native_call(client, db_conn):
    before = _row(db_conn, "select count(*) as n from runningtracker.run_samples where run_id = %s", RUN_GAP)[0]["n"]
    assert put(client, RUN_GAP, [loc(30, 30)], token=TOKEN_3).status_code == 404
    assert client.get(f"{NATIVE}/prepared-runs/{RUN_GAP}", headers=auth(TOKEN_3)).status_code == 404
    assert finish(client, RUN_GAP, finish_body(20, 10, 10), token=TOKEN_3).status_code == 404
    assert finish(client, RUN_COMPLETE, finish_body(40, 20, 20), token=TOKEN_3).status_code == 404
    assert begin(client, run_id=RUN_GAP, token=TOKEN_3).status_code == 404
    after = _row(db_conn, "select count(*) as n from runningtracker.run_samples where run_id = %s", RUN_GAP)[0]["n"]
    assert before == after
    run = _row(db_conn, "select distance_m, status from runningtracker.runs where id = %s", RUN_GAP)[0]
    assert run["distance_m"] is None and run["status"] == "uploading"
    # unknown / malformed ids are 404 too
    assert put(client, "not-a-uuid", [loc(1, 1)]).status_code == 404
    assert finish(client, "b1000000-0000-0000-0000-000000000009", finish_body(1, 1, 0)).status_code == 404


def test_finish_links_route_and_library_lists_qualified_runs(client, db_conn):
    with db_conn.cursor() as cur:
        cur.execute(
            "insert into runningtracker.routes (name, geometry, reference_distance_m, is_loop, point_count, geometry_version) "
            "values ('Test route', '[[50,10,0],[50.001,10,111]]'::jsonb, 111, false, 2, 1) returning id")
        route_id = str(cur.fetchone()["id"])
    db_conn.commit()
    lib = client.get(f"{NATIVE}/library", headers=auth())
    assert lib.status_code == 200 and set(lib.json()) == {"routes", "runs"}
    assert any(r["route_id"] == route_id for r in lib.json()["routes"])
    assert client.get(f"{NATIVE}/library").status_code in (401, 403)
    begin(client)
    put(client, NEW_RUN, batch(10, 0))
    finish(client, NEW_RUN, {**finish_body(10, 10, 0), "route_id": route_id, "ghost_run_id": "not-a-uuid"})
    got = _row(db_conn, "select route_id, ghost_run_id from runningtracker.runs where id = %s", NEW_RUN)[0]
    assert str(got["route_id"]) == route_id and got["ghost_run_id"] is None
