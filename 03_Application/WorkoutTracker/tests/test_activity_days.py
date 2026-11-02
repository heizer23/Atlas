"""Finish celebration + light activity days through the API (time basis: client `today` param)."""

import datetime as dt
import zoneinfo

A = "11111111-1111-1111-1111-111111111111"
_now = dt.datetime.now(zoneinfo.ZoneInfo("Europe/Berlin")).date()
TODAY = _now.isoformat()                                   # the server accepts client dates within 1 day of this
YESTERDAY = (_now - dt.timedelta(days=1)).isoformat()
LAST_WEEK = (_now - dt.timedelta(days=7)).isoformat()
TOMORROW = (_now + dt.timedelta(days=3)).isoformat()


def start_and_log(client, seed, date=TODAY):
    seed(A, "2026-05-01", "Pull", [("Row", 30, [10], None)])
    sid = client.post("/api/workout/sessions/start", json={"split": "Pull", "workout_date": date}).json()["rows"][0]["id"]
    ex = client.get(f"/api/workout/sessions/{sid}/exercises").json()["rows"][0]
    client.patch(f"/api/workout/exercises/{ex['id']}", json={"exercise": "Row", "set1_reps": 9})
    return sid


def test_finish_returns_before_after_and_is_not_rewarded_on_retry(client, seed):
    sid = start_and_log(client, seed)
    r = client.post(f"/api/workout/sessions/{sid}/finish?today={TODAY}").json()
    c = r["celebration"]
    assert c["changed"] and c["before"]["month"]["count"] == 0 and c["after"]["month"]["count"] == 1
    assert c["after"]["current"]["length"] == 1
    again = client.post(f"/api/workout/sessions/{sid}/finish?today={TODAY}").json()
    assert again["celebration"] is None and again["already_finished"]


def test_second_session_same_day_saves_but_adds_no_progress(client, seed, db_conn):
    sid = start_and_log(client, seed)
    client.post(f"/api/workout/sessions/{sid}/finish?today={TODAY}")
    sid2 = client.post("/api/workout/sessions/start", json={"split": "Pull", "workout_date": TODAY}).json()["rows"][0]["id"]
    ex = client.get(f"/api/workout/sessions/{sid2}/exercises").json()["rows"][0]
    client.patch(f"/api/workout/exercises/{ex['id']}", json={"exercise": "Row", "set1_reps": 8})
    c = client.post(f"/api/workout/sessions/{sid2}/finish?today={TODAY}").json()["celebration"]
    assert not c["changed"] and c["note"] == "Today already counts."
    assert c["before"]["month"]["count"] == c["after"]["month"]["count"] == 1
    with db_conn.cursor() as cur:
        cur.execute("select count(*) c from workout.workout_session where status='finished'")
        assert cur.fetchone()["c"] == 2


def test_backdated_session_is_saved_without_celebration(client, seed):
    sid = start_and_log(client, seed, date=LAST_WEEK)
    assert client.post(f"/api/workout/sessions/{sid}/finish?today={TODAY}").json()["celebration"] is None


def test_discarded_empty_session_has_no_celebration(client, seed):
    seed(A, "2026-05-01", "Pull", [("Row", 30, [10], None)])
    sid = client.post("/api/workout/sessions/start", json={"split": "Pull", "workout_date": TODAY}).json()["rows"][0]["id"]
    assert client.post(f"/api/workout/sessions/{sid}/finish?today={TODAY}").json()["celebration"] is None


def test_finish_save_failure_leaves_session_active(client, seed, db_conn):
    sid = start_and_log(client, seed)
    with db_conn.cursor() as cur:  # make the status update fail
        cur.execute("alter table workout.workout_session add constraint ck_fail check (status <> 'finished') not valid")
    try:
        try:
            client.post(f"/api/workout/sessions/{sid}/finish?today={TODAY}")
        except Exception:
            pass
    finally:
        with db_conn.cursor() as cur:
            cur.execute("alter table workout.workout_session drop constraint ck_fail")
    assert client.get("/api/workout/sessions/active").json()["rows"][0]["id"] == sid  # still active, retry possible
    assert client.post(f"/api/workout/sessions/{sid}/finish?today={TODAY}").json()["celebration"]["changed"]


def test_light_activity_counts_equally_and_is_idempotent(client, seed):
    seed(A, YESTERDAY, "Pull", [("Row", 30, [10], None)])  # yesterday strength
    r = client.post(f"/api/workout/activity-days?today={TODAY}", json={"activity_date": TODAY, "kind": "stretching"}).json()
    assert r["celebration"]["changed"] and r["celebration"]["after"]["current"]["length"] == 2
    dup = client.post(f"/api/workout/activity-days?today={TODAY}", json={"activity_date": TODAY, "kind": "stretching"}).json()
    assert not dup["celebration"]["changed"]
    other = client.post(f"/api/workout/activity-days?today={TODAY}", json={"activity_date": TODAY, "kind": "mobility"}).json()
    assert not other["celebration"]["changed"] and other["celebration"]["after"]["current"]["length"] == 2


def test_activity_day_validation_and_delete_recalculates(client, seed):
    bad = client.post("/api/workout/activity-days", json={"activity_date": TODAY, "kind": "swim"})
    assert bad.status_code == 400 or "error" in bad.json()
    fut = client.post(f"/api/workout/activity-days?today={TODAY}", json={"activity_date": TOMORROW, "kind": "running"})
    assert "error" in fut.json()
    client.post(f"/api/workout/activity-days?today={TODAY}", json={"activity_date": LAST_WEEK, "kind": "running"})
    assert len(client.get("/api/workout/activity-days").json()["rows"]) == 1
    assert client.delete(f"/api/workout/activity-days/{LAST_WEEK}/running").json() == {"deleted": True}
    assert client.get("/api/workout/activity-days").json()["rows"] == []
    assert client.delete(f"/api/workout/activity-days/{LAST_WEEK}/running").status_code == 404


def test_implausible_client_today_falls_back_to_server_date(client, seed):
    sid = start_and_log(client, seed)
    c = client.post(f"/api/workout/sessions/{sid}/finish?today=2030-01-01").json()["celebration"]
    assert c["after"]["today"] == TODAY


def test_other_kind_counts_like_any_activity_day(client):
    r = client.post(f"/api/workout/activity-days?today={TODAY}", json={"activity_date": TODAY, "kind": "other"}).json()
    assert r["celebration"]["changed"] and r["celebration"]["after"]["current"]["length"] == 1


def test_calendar_lists_days_with_primary_kind(client, seed):
    seed(A, YESTERDAY, "Pull", [("Row", 30, [10], None)])
    for kind in ("running", "other"):
        client.post(f"/api/workout/activity-days?today={TODAY}", json={"activity_date": YESTERDAY, "kind": kind})
    client.post(f"/api/workout/activity-days?today={TODAY}", json={"activity_date": TODAY, "kind": "other"})
    rows = client.get(f"/api/workout/calendar?year={TODAY[:4]}").json()["rows"]
    by = {r["date"]: r for r in rows}
    assert by[YESTERDAY]["primary"] == "workout" and by[YESTERDAY]["kinds"] == ["workout", "running", "other"]
    assert by[TODAY]["primary"] == "other"
    assert client.get("/api/workout/calendar?year=1999").json()["rows"] == []


def test_progress_snapshot_is_one_row_dataset(client, seed):
    empty = client.get(f"/api/workout/progress?today={TODAY}").json()["rows"]
    assert len(empty) == 1 and empty[0]["ranking"] == [] and empty[0]["month"]["count"] == 0
    seed(A, YESTERDAY, "Pull", [("Row", 30, [10], None)])
    row = client.get(f"/api/workout/progress?today={TODAY}").json()["rows"][0]
    assert row["current"]["length"] == 1 and row["today"] == TODAY
