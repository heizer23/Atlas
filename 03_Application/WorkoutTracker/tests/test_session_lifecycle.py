"""
Session lifecycle, archetypes, planned exercises, delta semantics and history.
Migration 003 contract: legacy rows are 'done'; sessions without a workout_session row are finished.
"""

A = "11111111-1111-1111-1111-111111111111"
B = "22222222-2222-2222-2222-222222222222"
C = "33333333-3333-3333-3333-333333333333"


def rows(res):
    assert res.status_code == 200, res.text
    return res.json()["rows"]


def test_no_active_session_returns_empty_dataset(client):
    assert rows(client.get("/api/workout/sessions/active")) == []


def test_archetypes_group_case_insensitively_and_use_latest_spelling(client, seed):
    seed(A, "2026-05-01", "Push hotel", [("Dips", None, [8, 8], None)])
    seed(B, "2026-06-01", "Push Hotel", [("Dips", None, [9, 8], None)])
    seed(C, "2026-05-20", "Pull", [("Pull up", None, [5, 5], None)])
    arch = rows(client.get("/api/workout/archetypes"))
    assert [a["split"] for a in arch] == ["Push Hotel", "Pull"]
    assert arch[0]["session_count"] == 2


def test_start_creates_planned_copy_without_results_or_comments(client, seed):
    seed(A, "2026-06-01", "Pull", [("Pull up", None, [8, 7, 6], "grip slipped"), ("Row", 30, [10, 10], None)])
    started = rows(client.post("/api/workout/sessions/start", json={"split": "pull"}))
    assert len(started) == 1 and started[0]["split"] == "pull"
    sid = started[0]["id"]
    ex = rows(client.get(f"/api/workout/sessions/{sid}/exercises"))
    assert [e["exercise"] for e in ex] == ["Pull up", "Row"]
    assert all(e["status"] == "planned" for e in ex)
    assert all(e["set1_reps"] is None and e["comment"] is None for e in ex)
    assert ex[1]["weight_kg"] == 30.0  # starting prescription carried over
    # template untouched
    old = rows(client.get(f"/api/workout/sessions/{A}/exercises"))
    assert old[0]["set1_reps"] == 8 and old[0]["comment"] == "grip slipped" and old[0]["status"] == "done"


def test_active_session_resumes_and_second_start_is_rejected(client, seed):
    seed(A, "2026-06-01", "Pull", [("Pull up", None, [8], None)])
    sid = rows(client.post("/api/workout/sessions/start", json={"split": "Pull"}))[0]["id"]
    assert rows(client.get("/api/workout/sessions/active"))[0]["id"] == sid
    dup = client.post("/api/workout/sessions/start", json={"split": "Pull"})
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "ACTIVE_SESSION_EXISTS"
    assert len(rows(client.get("/api/workout/sessions/active"))) == 1


def test_start_with_unknown_split_has_no_planned_rows(client):
    sid = rows(client.post("/api/workout/sessions/start", json={"split": "Brand New"}))[0]["id"]
    assert rows(client.get(f"/api/workout/sessions/{sid}/exercises")) == []
    added = client.post(f"/api/workout/sessions/{sid}/exercises", json={"exercise": "Squat", "status": "planned"})
    assert rows(added)[0]["status"] == "planned"


def test_saving_reps_marks_planned_exercise_done(client, seed):
    seed(A, "2026-06-01", "Pull", [("Pull up", None, [8], None)])
    sid = rows(client.post("/api/workout/sessions/start", json={"split": "Pull"}))[0]["id"]
    ex = rows(client.get(f"/api/workout/sessions/{sid}/exercises"))[0]
    res = client.patch(f"/api/workout/exercises/{ex['id']}", json={"exercise": "Pull up", "set1_reps": 9, "comment": "ok"})
    assert rows(res)[0]["status"] == "done"
    no_reps = client.patch(f"/api/workout/exercises/{ex['id']}", json={"exercise": "Pull up"})
    assert no_reps.status_code != 200  # still needs reps to count as performed


def test_finish_removes_planned_rows_and_makes_session_finished(client, seed):
    seed(A, "2026-06-01", "Pull", [("Pull up", None, [8], None), ("Row", 30, [10], None)])
    sid = rows(client.post("/api/workout/sessions/start", json={"split": "Pull"}))[0]["id"]
    first = rows(client.get(f"/api/workout/sessions/{sid}/exercises"))[0]
    client.patch(f"/api/workout/exercises/{first['id']}", json={"exercise": "Pull up", "set1_reps": 9})
    assert client.post(f"/api/workout/sessions/{sid}/finish").status_code == 200
    ex = rows(client.get(f"/api/workout/sessions/{sid}/exercises"))
    assert [e["exercise"] for e in ex] == ["Pull up"]
    assert rows(client.get("/api/workout/sessions/active")) == []
    listed = rows(client.get("/api/workout/sessions"))
    assert listed[0]["id"] == sid and listed[0]["status"] == "finished" and listed[0]["exercise_count"] == 1
    assert client.post(f"/api/workout/sessions/{sid}/finish").status_code == 404


def test_finish_with_nothing_performed_discards_session(client, seed):
    seed(A, "2026-06-01", "Pull", [("Pull up", None, [8], None)])
    sid = rows(client.post("/api/workout/sessions/start", json={"split": "Pull"}))[0]["id"]
    assert client.post(f"/api/workout/sessions/{sid}/finish").status_code == 200
    assert rows(client.get("/api/workout/sessions/active")) == []
    assert client.get(f"/api/workout/sessions/{sid}/exercises").status_code == 404
    assert len(rows(client.get("/api/workout/sessions"))) == 1  # only the legacy one


def test_active_session_hidden_from_log_by_default_and_filter_is_case_insensitive(client, seed):
    seed(A, "2026-06-01", "Pull", [("Pull up", None, [8], None)])
    seed(B, "2026-06-02", "Push", [("Dips", None, [8], None)])
    sid = rows(client.post("/api/workout/sessions/start", json={"split": "Pull"}))[0]["id"]
    assert sid not in [s["id"] for s in rows(client.get("/api/workout/sessions"))]
    assert sid in [s["id"] for s in rows(client.get("/api/workout/sessions?include_active=true"))]
    assert [s["id"] for s in rows(client.get("/api/workout/sessions?split=PUSH"))] == [B]


def test_delete_active_session_cancels_it(client, seed):
    seed(A, "2026-06-01", "Pull", [("Pull up", None, [8], None)])
    sid = rows(client.post("/api/workout/sessions/start", json={"split": "Pull"}))[0]["id"]
    assert client.delete(f"/api/workout/sessions/{sid}").status_code == 200
    assert rows(client.get("/api/workout/sessions/active")) == []
    assert len(rows(client.get("/api/workout/sessions"))) == 1


def test_progress_delta_only_for_same_weight_and_never_for_planned(client, seed):
    seed(A, "2026-05-01", "Push", [("Bench", 50, [10, 10], None)])      # 20
    seed(B, "2026-05-08", "Push", [("Bench", 55, [10, 10], None)])      # weight change -> no delta
    seed(C, "2026-05-15", "Push", [("Bench", 55, [10, 9], None)])       # -1 vs previous
    d = {r["exercise"]: r["delta"] for r in rows(client.get(f"/api/workout/sessions/{B}/progress"))}
    assert d["Bench"] is None
    d = {r["exercise"]: r["delta"] for r in rows(client.get(f"/api/workout/sessions/{C}/progress"))}
    assert d["Bench"] == -1
    sid = rows(client.post("/api/workout/sessions/start", json={"split": "Push"}))[0]["id"]
    assert rows(client.get(f"/api/workout/sessions/{sid}/progress")) == []  # planned: no result, no delta


def test_history_excludes_planned_includes_comment_and_split_across_archetypes(client, seed):
    seed(A, "2026-05-01", "Push", [("Bench", 50, [10], "felt strong")])
    seed(B, "2026-05-08", "Push Hotel", [("bench", 50, [9], None)])      # other archetype, other case
    client.post("/api/workout/sessions/start", json={"split": "Push"})   # planned Bench in a new session
    hist = rows(client.get("/api/workout/exercises/history?name=BENCH"))
    assert [h["workout_date"] for h in hist] == ["2026-05-01", "2026-05-08"]
    assert hist[0]["comment"] == "felt strong" and hist[1]["split"] == "Push Hotel"


def test_legacy_sessions_unchanged_by_migration(client, seed):
    seed(A, "2026-05-01", "Pull", [("Pull up", None, [8, 7, 6], "c")])
    ex = rows(client.get(f"/api/workout/sessions/{A}/exercises"))
    assert ex[0]["status"] == "done" and ex[0]["set3_reps"] == 6 and ex[0]["total_reps"] == 21
    assert rows(client.get("/api/workout/sessions"))[0]["status"] == "finished"


def test_exercise_rows_carry_delta_only_when_comparable(client, seed):
    seed(A, "2026-05-01", "Push", [("Bench", 50, [10, 10], None)])
    seed(B, "2026-05-08", "Push", [("Bench", 50, [10, 12], None)])      # +2 same weight
    seed(C, "2026-05-15", "Push", [("Bench", 60, [10, 12], None)])      # weight changed -> None
    assert rows(client.get(f"/api/workout/sessions/{B}/exercises"))[0]["delta"] == 2
    assert rows(client.get(f"/api/workout/sessions/{C}/exercises"))[0]["delta"] is None
    sid = rows(client.post("/api/workout/sessions/start", json={"split": "Push"}))[0]["id"]
    planned = rows(client.get(f"/api/workout/sessions/{sid}/exercises"))[0]
    assert planned["status"] == "planned" and planned["delta"] is None


def test_exercise_names_merge_case_and_span_archetypes(client, seed):
    seed(A, "2026-05-01", "Push", [("Dips", None, [8], None), ("Bench", 50, [8], None)])
    seed(B, "2026-05-08", "Push Hotel", [("dips", None, [9], None)])
    names = rows(client.get("/api/workout/exercises/names"))
    assert [(n["exercise"], n["use_count"]) for n in names] == [("dips", 2), ("Bench", 1)]


def test_repeat_from_session_id_uses_that_session_and_client_date(client, seed):
    seed(A, "2026-05-01", "Push", [("Bench", 50, [10, 10], "old comment")])
    seed(B, "2026-05-08", "Push", [("Dips", None, [8], None)])
    res = client.post("/api/workout/sessions/start",
                      json={"split": "Push", "from_session_id": A, "workout_date": "2026-06-30"})
    started = rows(res)[0]
    assert started["workout_date"] == "2026-06-30"
    ex = rows(client.get(f"/api/workout/sessions/{started['id']}/exercises"))
    assert [e["exercise"] for e in ex] == ["Bench"] and ex[0]["comment"] is None and ex[0]["set1_reps"] is None
    assert rows(client.get(f"/api/workout/sessions/{A}/exercises"))[0]["comment"] == "old comment"


def test_start_validates_inputs(client):
    bad_id = client.post("/api/workout/sessions/start", json={"split": "Push", "from_session_id": "nope"})
    bad_date = client.post("/api/workout/sessions/start", json={"split": "Push", "workout_date": "31.06.2026"})
    unknown = client.post("/api/workout/sessions/start", json={"split": "Push", "from_session_id": A})
    assert bad_id.json()["error"]["code"] == "VALIDATION_ERROR"
    assert bad_date.json()["error"]["code"] == "VALIDATION_ERROR"
    assert unknown.status_code == 404
    assert rows(client.get("/api/workout/sessions/active")) == []  # nothing half-created


def test_start_race_on_unique_index_is_409_not_500(client, db_conn):
    # Simulate the losing side of a race: an active row exists but the pre-check is bypassed
    # by inserting it directly between the check and the insert -> here, insert first and
    # call the endpoint; the endpoint must answer 409 either way.
    with db_conn.cursor() as cur:
        cur.execute("insert into workout.workout_session (workout_id, split, workout_date) "
                    "values (%s, 'Pull', current_date)", (A,))
    res = client.post("/api/workout/sessions/start", json={"split": "Pull"})
    assert res.status_code == 409 and res.json()["error"]["code"] == "ACTIVE_SESSION_EXISTS"


def test_planned_exercise_only_into_active_session(client, seed):
    seed(A, "2026-05-01", "Push", [("Bench", 50, [10], None)])  # legacy = finished
    res = client.post(f"/api/workout/sessions/{A}/exercises", json={"exercise": "Dips", "status": "planned"})
    assert res.status_code != 200 and res.json()["error"]["code"] == "VALIDATION_ERROR"
    done = client.post(f"/api/workout/sessions/{A}/exercises", json={"exercise": "Dips", "set1_reps": 8})
    assert len(rows(done)) == 2  # logging a performed exercise into an old session still works


def test_split_filter_trims_whitespace(client, seed):
    seed(A, "2026-05-01", "Ganzkörper ", [("Squat", 40, [10], None)])
    assert [s["id"] for s in rows(client.get("/api/workout/sessions?split=ganzkörper"))] == [A]


def test_sessions_list_include_exercises_is_opt_in_and_read_only(client, seed, db_conn):
    seed(A, "2026-05-01", "Push", [("Bench", 50, [10, 10], "c1"), ("Dips", None, [8, 8, 7], None)])
    seed(B, "2026-05-08", "Push", [("Bench", 50, [10, 12], None)])
    plain = rows(client.get("/api/workout/sessions"))
    assert all("exercises" not in r for r in plain)
    full = rows(client.get("/api/workout/sessions?include_exercises=true"))
    assert [r["id"] for r in full] == [B, A]  # newest first
    newest = full[0]["exercises"][0]
    assert newest["exercise"] == "Bench" and newest["delta"] == 2 and newest["set2_reps"] == 12
    assert [e["exercise"] for e in full[1]["exercises"]] == ["Bench", "Dips"]  # entry order
    with db_conn.cursor() as cur:  # reading never creates sessions
        cur.execute("select count(*) as n from workout.workout_session")
        assert cur.fetchone()["n"] == 0


def test_history_rows_carry_session_id_and_are_read_only(client, seed, db_conn):
    seed(A, "2026-05-01", "Push", [("Bench", 50, [10], "felt strong")])
    seed(B, "2026-05-08", "Pull", [("Bench", 52.5, [9], None)])
    hist = rows(client.get("/api/workout/exercises/history?name=bench"))
    assert [h["session_id"] for h in hist] == [A, B]
    assert hist[1]["weight_kg"] == 52.5
    with db_conn.cursor() as cur:
        cur.execute("select count(*) as n from workout.workout_log")
        assert cur.fetchone()["n"] == 2
