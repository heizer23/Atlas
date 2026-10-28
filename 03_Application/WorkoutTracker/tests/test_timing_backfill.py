"""
Synthetic backfill of legacy set timing + the derived timing views (migration 005).
Contract: only sessions without a workout_session row are touched, only timing columns change,
the rule is deterministic and idempotent, DST-correct, and fully undoable.
"""

import os

A = "11111111-1111-1111-1111-111111111111"   # legacy, summer (CEST, UTC+2)
B = "22222222-2222-2222-2222-222222222222"   # legacy, winter (CET, UTC+1)
R = "33333333-3333-3333-3333-333333333333"   # real: has a workout_session row

_here = os.path.dirname(__file__)
TIMING = [f"set{n}_{k}_at" for n in range(1, 6) for k in ("started", "ended")]


def script(db_conn, name):
    with open(os.path.join(_here, "../scripts", name)) as f:
        with db_conn.cursor() as cur:
            cur.execute(f.read())


def snapshot(db_conn, cols):
    with db_conn.cursor() as cur:
        cur.execute(f"select workout_log_id, {', '.join(cols)} from workout.workout_log order by workout_log_id")
        return [tuple(r.values()) for r in cur.fetchall()]


def seed_all(seed, db_conn):
    seed(A, "2026-06-01", "Pull", [("Row", 30, [10, 10, 9], "c1"), ("Curl", 12, [12, None, 11], None)])
    seed(B, "2026-01-15", "Push", [("Dips", None, [8, 8], None)])
    seed(R, "2026-06-02", "Pull", [("Row", 30, [10], None)])
    with db_conn.cursor() as cur:  # R was started from the app: it has a lifecycle row
        cur.execute("insert into workout.workout_session (workout_id, split, workout_date, status, finished_at) "
                    "values (%s, 'Pull', '2026-06-02', 'finished', now())", (R,))


def utc(ts):
    return ts.astimezone(__import__("datetime").timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def test_backfill_is_deterministic_dst_correct_and_leaves_everything_else_alone(db_conn, seed):
    seed_all(seed, db_conn)
    other = [c for c in ("exercise", "weight_kg", "set1_reps", "set2_reps", "set3_reps", "set4_reps", "set5_reps",
                         "comment", "status", "workout_id", "workout_date", "split", "created_at")]
    before = snapshot(db_conn, other)
    script(db_conn, "backfill_set_timing.sql")
    assert snapshot(db_conn, other) == before                      # nothing but timing changed

    with db_conn.cursor() as cur:
        cur.execute("select exercise, set1_started_at s1, set1_ended_at e1, set2_started_at s2, set3_started_at s3, "
                    "set3_ended_at e3 from workout.workout_log where workout_id = %s order by workout_log_id", (A,))
        row, curl = cur.fetchall()
        assert utc(row["s1"]) == "2026-06-01 15:00:00"             # 17:00 CEST
        assert utc(row["e1"]) == "2026-06-01 15:00:40"             # 40 s set
        assert utc(row["s2"]) == "2026-06-01 15:02:40"             # + 120 s rest
        # Curl: starts after Row's 3 sets (3*40 + 2*120 + 180 = 540 s)
        assert utc(curl["s1"]) == "2026-06-01 15:09:00"
        assert curl["s2"] is None                                  # set 2 was never performed
        assert utc(curl["s3"]) == "2026-06-01 15:11:40"            # second performed set
        cur.execute("select set1_started_at s from workout.workout_log where workout_id = %s", (B,))
        assert utc(cur.fetchone()["s"]) == "2026-01-15 16:00:00"   # 17:00 CET
        cur.execute("select count(*) c from workout.workout_log where workout_id = %s and set1_started_at is not null", (R,))
        assert cur.fetchone()["c"] == 0                            # app-started session untouched


def test_backfill_is_idempotent_and_never_overwrites_real_timing(db_conn, seed):
    seed_all(seed, db_conn)
    script(db_conn, "backfill_set_timing.sql")
    first = snapshot(db_conn, TIMING)
    script(db_conn, "backfill_set_timing.sql")
    assert snapshot(db_conn, TIMING) == first

    # a legacy-session row that somehow has real timing keeps it
    with db_conn.cursor() as cur:
        cur.execute("update workout.workout_log set set1_started_at = null, set1_ended_at = null, "
                    "set2_started_at = null, set2_ended_at = null, set3_started_at = null, set3_ended_at = null "
                    "where workout_id = %s", (A,))
        cur.execute("update workout.workout_log set set1_ended_at = '2026-06-01 10:00:00+00' where workout_id = %s "
                    "and exercise = 'Row'", (A,))
    script(db_conn, "backfill_set_timing.sql")
    with db_conn.cursor() as cur:
        cur.execute("select set1_ended_at e, set1_started_at s from workout.workout_log where workout_id = %s and exercise = 'Row'", (A,))
        r = cur.fetchone()
        assert utc(r["e"]) == "2026-06-01 10:00:00" and r["s"] is None


def test_active_session_is_never_backfilled(db_conn, seed, client):
    seed(A, "2026-06-01", "Pull", [("Row", 30, [10, 10], None)])
    client.post("/api/workout/sessions/start", json={"split": "Pull"})
    script(db_conn, "backfill_set_timing.sql")
    with db_conn.cursor() as cur:
        cur.execute("select count(*) c from workout.workout_log where set1_started_at is not null and status = 'planned'")
        assert cur.fetchone()["c"] == 0


def test_remove_restores_legacy_only(db_conn, seed):
    seed_all(seed, db_conn)
    with db_conn.cursor() as cur:  # real timing on the app-started session
        cur.execute("update workout.workout_log set set1_started_at = now() - interval '1 minute', set1_ended_at = now() "
                    "where workout_id = %s", (R,))
    real = snapshot(db_conn, TIMING)[-1]
    script(db_conn, "backfill_set_timing.sql")
    script(db_conn, "remove_backfilled_set_timing.sql")
    rows = snapshot(db_conn, TIMING)
    assert all(v is None for r in rows[:-1] for v in r[1:])        # legacy rows: back to no timing
    assert rows[-1] == real                                         # real timing survives


def test_views_expose_measured_values_only(db_conn, seed):
    seed_all(seed, db_conn)
    script(db_conn, "backfill_set_timing.sql")
    with db_conn.cursor() as cur:
        cur.execute("select set_no, duration_sec, rest_sec, interval_sec, interrupted from workout.set_timing t "
                    "join workout.workout_log l using (workout_log_id) where l.workout_id = %s and l.exercise = 'Row' "
                    "order by set_no", (A,))
        rows = cur.fetchall()
        assert [r["duration_sec"] for r in rows] == [40, 40, 40]
        assert [r["rest_sec"] for r in rows] == [None, 120, 120]   # first set has no previous set
        assert [r["interval_sec"] for r in rows] == [None, 160, 160]
        assert not any(r["interrupted"] for r in rows)
        cur.execute("select duration_sec, rest_avg_sec, time_of_day from workout.exercise_timing t "
                    "join workout.workout_log l using (workout_log_id) where l.workout_id = %s and l.exercise = 'Row'", (A,))
        e = cur.fetchone()
        assert e["duration_sec"] == 3 * 40 + 2 * 120 and e["rest_avg_sec"] == 120
        assert e["time_of_day"] == "17:00"                          # local, legacy sessions read as Europe/Berlin


def test_missing_start_gives_interval_but_no_rest_and_long_rest_is_interrupted(db_conn, seed):
    seed(A, "2026-06-01", "Pull", [("Row", 30, [10, 10, 10], None)])
    with db_conn.cursor() as cur:
        cur.execute("""update workout.workout_log set
            set1_started_at = '2026-06-01 15:00:00+00', set1_ended_at = '2026-06-01 15:00:40+00',
            set2_ended_at   = '2026-06-01 15:03:00+00',                         -- start forgotten
            set3_started_at = '2026-06-01 15:20:00+00', set3_ended_at = '2026-06-01 15:20:30+00'""")
        cur.execute("select set_no, rest_sec, interval_sec, interrupted from workout.set_timing order by set_no")
        r = cur.fetchall()
    assert r[1]["rest_sec"] is None and r[1]["interval_sec"] == 140
    assert r[2]["rest_sec"] == 1020 and r[2]["interrupted"] is True
    with db_conn.cursor() as cur:
        cur.execute("select rest_avg_sec from workout.exercise_timing")
        assert cur.fetchone()["rest_avg_sec"] is None              # the only rest is interrupted: excluded


def test_history_endpoint_carries_timing_or_nulls(client, db_conn, seed):
    seed(A, "2026-06-01", "Pull", [("Row", 30, [10, 10], None)])
    seed(B, "2026-06-08", "Pull", [("Row", 30, [10, 10], None)])
    with db_conn.cursor() as cur:
        cur.execute("""update workout.workout_log set
            set1_started_at = '2026-06-08 15:00:00+00', set1_ended_at = '2026-06-08 15:00:40+00',
            set2_started_at = '2026-06-08 15:02:40+00', set2_ended_at = '2026-06-08 15:03:20+00'
            where workout_id = %s""", (B,))
    rows = client.get("/api/workout/exercises/history", params={"name": "row"}).json()["rows"]
    assert rows[0]["duration_sec"] is None and rows[0]["time_of_day"] is None     # not measured: never fabricated
    assert rows[1]["duration_sec"] == 200 and rows[1]["rest_avg_sec"] == 120 and rows[1]["time_of_day"] == "17:00"
