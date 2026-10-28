"""
Per-set timing events (migration 004): start / confirm / unconfirm on the ACTIVE workout.
Contract: server clock only, idempotent, no estimates, past sessions never receive timing.
"""

A = "11111111-1111-1111-1111-111111111111"


def rows(res):
    assert res.status_code == 200, res.text
    return res.json()["rows"]


def begin(client, seed):
    seed(A, "2026-06-01", "Pull", [("Row", 30, [10, 10], None), ("Curl", 12, [12], None)])
    sid = rows(client.post("/api/workout/sessions/start", json={"split": "Pull"}))[0]["id"]
    ex = rows(client.get(f"/api/workout/sessions/{sid}/exercises"))
    return sid, ex[0]["id"], ex[1]["id"]


def timing(db_conn, ex_id, n):
    with db_conn.cursor() as cur:
        cur.execute(
            f"select set{n}_reps r, set{n}_started_at s, set{n}_ended_at e, status from workout.workout_log "
            "where workout_log_id=%s", (ex_id,))
        return cur.fetchone()


def test_legacy_rows_have_no_timing(client, db_conn, seed):
    seed(A, "2026-06-01", "Pull", [("Row", 30, [10, 10], None)])
    with db_conn.cursor() as cur:
        cur.execute("select count(*) c from workout.workout_log where set1_started_at is not null or set1_ended_at is not null")
        assert cur.fetchone()["c"] == 0
    r = rows(client.get(f"/api/workout/sessions/{A}/exercises"))[0]
    assert r["set1_started_at"] is None and r["set1_ended_at"] is None


def test_start_is_idempotent_and_uses_server_clock(client, db_conn, seed):
    _, ex, _ = begin(client, seed)
    client.post(f"/api/workout/exercises/{ex}/sets/1/start", json={"started_at": "2000-01-01T00:00:00Z"})
    first = timing(db_conn, ex, 1)["s"]
    assert first is not None and first.year >= 2026       # client-supplied time ignored
    client.post(f"/api/workout/exercises/{ex}/sets/1/start")
    assert timing(db_conn, ex, 1)["s"] == first             # second tap does not move it


def test_confirm_persists_reps_marks_done_and_keeps_missing_start_null(client, db_conn, seed):
    _, ex, _ = begin(client, seed)
    t = timing(db_conn, ex, 1)
    assert t["status"] == "planned" and t["r"] is None
    out = rows(client.post(f"/api/workout/exercises/{ex}/sets/1/confirm", json={"reps": 9, "weight_kg": 32.5}))
    row = next(r for r in out if r["id"] == ex)
    assert row["status"] == "done" and row["set1_reps"] == 9 and row["weight_kg"] == 32.5
    t = timing(db_conn, ex, 1)
    assert t["e"] is not None and t["s"] is None            # forgotten start tap stays NULL


def test_start_then_confirm_orders_timestamps(client, db_conn, seed):
    _, ex, _ = begin(client, seed)
    client.post(f"/api/workout/exercises/{ex}/sets/2/start")
    client.post(f"/api/workout/exercises/{ex}/sets/2/confirm", json={"reps": 8, "weight_kg": 30})
    t = timing(db_conn, ex, 2)
    assert t["s"] is not None and t["e"] >= t["s"]


def test_reconfirm_updates_reps_but_never_moves_timestamps(client, db_conn, seed):
    _, ex, _ = begin(client, seed)
    client.post(f"/api/workout/exercises/{ex}/sets/1/start")
    client.post(f"/api/workout/exercises/{ex}/sets/1/confirm", json={"reps": 8, "weight_kg": 30})
    before = timing(db_conn, ex, 1)
    client.post(f"/api/workout/exercises/{ex}/sets/1/confirm", json={"reps": 10, "weight_kg": 30})
    client.post(f"/api/workout/exercises/{ex}/sets/1/start")           # start after confirm: no-op
    after = timing(db_conn, ex, 1)
    assert after["r"] == 10 and after["s"] == before["s"] and after["e"] == before["e"]


def test_unconfirm_clears_reps_and_both_timestamps_and_last_one_returns_to_planned(client, db_conn, seed):
    _, ex, _ = begin(client, seed)
    for n in (1, 2):
        client.post(f"/api/workout/exercises/{ex}/sets/{n}/start")
        client.post(f"/api/workout/exercises/{ex}/sets/{n}/confirm", json={"reps": 8, "weight_kg": 30})
    client.post(f"/api/workout/exercises/{ex}/sets/2/unconfirm")
    t2 = timing(db_conn, ex, 2)
    assert t2["r"] is None and t2["s"] is None and t2["e"] is None and t2["status"] == "done"
    assert timing(db_conn, ex, 1)["e"] is not None
    client.post(f"/api/workout/exercises/{ex}/sets/1/unconfirm")
    assert timing(db_conn, ex, 1)["status"] == "planned"


def test_past_and_unknown_exercises_reject_events(client, db_conn, seed):
    seed(A, "2026-06-01", "Pull", [("Row", 30, [10], None)])
    old = rows(client.get(f"/api/workout/sessions/{A}/exercises"))[0]["id"]
    for path, body in (("start", None), ("confirm", {"reps": 5}), ("unconfirm", None)):
        res = client.post(f"/api/workout/exercises/{old}/sets/1/{path}", json=body)
        assert res.status_code == 409 and res.json()["error"]["code"] == "SESSION_NOT_ACTIVE"
    assert timing(db_conn, old, 1)["e"] is None
    assert client.post("/api/workout/exercises/999999/sets/1/start").status_code == 404


def test_validation(client, seed):
    _, ex, _ = begin(client, seed)
    assert client.post(f"/api/workout/exercises/{ex}/sets/6/start").status_code == 400
    assert client.post(f"/api/workout/exercises/{ex}/sets/0/confirm", json={"reps": 5}).status_code == 400
    assert client.post(f"/api/workout/exercises/{ex}/sets/1/confirm", json={"reps": -1}).status_code == 400


def test_details_update_leaves_sets_status_and_timing_alone_and_null_clears(client, db_conn, seed):
    _, ex, _ = begin(client, seed)
    client.post(f"/api/workout/exercises/{ex}/sets/1/start")
    client.post(f"/api/workout/exercises/{ex}/sets/1/confirm", json={"reps": 8, "weight_kg": 30})
    before = timing(db_conn, ex, 1)
    out = rows(client.patch(f"/api/workout/exercises/{ex}/details", json={"exercise": "Row 2", "weight_kg": 35, "comment": "ok"}))
    row = next(r for r in out if r["id"] == ex)
    assert row["exercise"] == "Row 2" and row["weight_kg"] == 35 and row["comment"] == "ok" and row["set1_reps"] == 8
    out = rows(client.patch(f"/api/workout/exercises/{ex}/details", json={"exercise": "Row 2", "weight_kg": None, "comment": None}))
    row = next(r for r in out if r["id"] == ex)
    assert row["weight_kg"] is None and row["comment"] is None
    assert timing(db_conn, ex, 1) == before


def test_planned_exercise_details_keep_it_planned(client, db_conn, seed):
    _, _, planned = begin(client, seed)
    client.patch(f"/api/workout/exercises/{planned}/details", json={"exercise": "Curl", "weight_kg": 14, "comment": None})
    assert timing(db_conn, planned, 1)["status"] == "planned"


def test_past_session_patch_clearing_a_set_clears_its_timing(client, db_conn, seed):
    _, ex, _ = begin(client, seed)
    client.post(f"/api/workout/exercises/{ex}/sets/1/confirm", json={"reps": 8, "weight_kg": 30})
    client.post(f"/api/workout/exercises/{ex}/sets/2/confirm", json={"reps": 7, "weight_kg": 30})
    client.patch(f"/api/workout/exercises/{ex}", json={"exercise": "Row", "weight_kg": 30, "set1_reps": 8, "comment": None})
    assert timing(db_conn, ex, 1)["e"] is not None            # kept set keeps its timing
    t2 = timing(db_conn, ex, 2)
    assert t2["r"] is None and t2["e"] is None                # cleared set loses it


def test_session_stores_valid_tz_and_rejects_invalid(client, db_conn, seed):
    seed(A, "2026-06-01", "Pull", [("Row", 30, [10], None)])
    bad = client.post("/api/workout/sessions/start", json={"split": "Pull", "tz": "Mars/Base"})
    assert bad.status_code == 400
    sid = rows(client.post("/api/workout/sessions/start", json={"split": "Pull", "tz": "Europe/Berlin"}))[0]["id"]
    with db_conn.cursor() as cur:
        cur.execute("select tz from workout.workout_session where workout_id=%s", (sid,))
        assert cur.fetchone()["tz"] == "Europe/Berlin"
