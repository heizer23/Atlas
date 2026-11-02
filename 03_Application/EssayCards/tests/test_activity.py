"""GET /api/essaycards/activity — per-day effort flags for HabitTracker linked habits."""

URL = "/api/essaycards/activity"
CARD = "fc000025-0000-0000-0000-000000000025"


def _get(client, start="2020-05-04", end="2020-05-08"):
    r = client.get(URL, params={"start": start, "end": end})
    assert r.status_code == 200
    return {d["date"]: d for d in r.json()["days"]}, r.json()["first"]


def _one_section(db_conn):
    with db_conn.cursor() as cur:
        cur.execute("select essay_id, id from essaycards.essay_sections limit 1")
        r = cur.fetchone()
    return r["essay_id"], r["id"]


def test_flashcard_review_counts_on_berlin_day_not_utc(client, db_conn):
    with db_conn.cursor() as cur:
        cur.execute("delete from essaycards.review_events")
        # 23:30 UTC on 05-05 is 01:30 Berlin (CEST) on 05-06
        cur.execute("""insert into essaycards.review_events
            (flashcard_id, grade, reviewed_at, was_due, prior_review_interval, resulting_review_interval)
            values (%s, 'good', '2020-05-05 23:30+00', true, interval '1 day', interval '2 days')""", (CARD,))
    days, _ = _get(client)
    assert days["2020-05-06"]["flashcards"] is True
    assert days["2020-05-05"]["flashcards"] is False
    assert days["2020-05-06"]["oral"] is False


def test_oral_from_guided_session_and_examinations(client, db_conn):
    essay_id, section_id = _one_section(db_conn)
    with db_conn.cursor() as cur:
        cur.execute("""insert into essaycards.section_guided_sessions
            (essay_id, section_id, level, section_version_at, session_at, transcript, recommendation,
             rationale, demonstrated, learner_decision)
            values (%s, %s, 1, now(), '2020-05-04 10:00+00', 't', 'continue', 'r', 'd', 'stay')""",
                    (essay_id, section_id))
        cur.execute("""insert into essaycards.essay_examinations
            (essay_id, exam_type, examined_at, question, answer_transcript, score, passed)
            values (%s, 'unguided', '2020-05-07 10:00+00', 'q', 'a', 2, false)""", (essay_id,))
    days, first = _get(client)
    assert days["2020-05-04"]["oral"] and days["2020-05-07"]["oral"]
    assert not days["2020-05-05"]["oral"]
    assert first["oral"] <= "2020-05-04"


def test_no_activity_and_validation(client, db_conn):
    days, _ = _get(client, "1999-01-01", "1999-01-03")
    assert all(not d["flashcards"] and not d["oral"] for d in days.values()) and len(days) == 3
    assert client.get(URL, params={"start": "x", "end": "2020-01-01"}).status_code == 400
    assert client.get(URL, params={"start": "2020-02-01", "end": "2020-01-01"}).status_code == 400
