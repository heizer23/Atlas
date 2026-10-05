"""
EssayCards — Sprint14_SectionProgressionAndRevalidation: derived section/essay
traffic lights, flashcard unlocking, card maturity (Learned), overview data and
the schema backfill migration.

Traceability: each function name maps to a scenario in
Sprint14_SectionProgressionAndRevalidation/10_test_spec.md ("Section state and
unlocking", "Card maturity", "Essay state", "Overview data", "Migration").
"""

import os
from datetime import datetime

from tests.helpers import run_sql, unlock_essay_sections

IMPORT_URL = "/api/essaycards/examinations/import"
PROGRESS_URL = "/api/essaycards/progress/sections"
FLASHCARDS = "/api/essaycards/flashcards"

ESSAY_LOCKED = "ea00000c-0000-0000-0000-00000000000c"
SECTION_LOCKED = "ec000017-0000-0000-0000-000000000017"
CARD_LOCKED_1 = "fc000031-0000-0000-0000-000000000031"
CARD_LOCKED_2 = "fc000032-0000-0000-0000-000000000032"
ESSAY_YELLOW = "ea00000d-0000-0000-0000-00000000000d"
SECTION_YELLOW_1 = "ec000018-0000-0000-0000-000000000018"
SECTION_YELLOW_2 = "ec000019-0000-0000-0000-000000000019"  # guided passed, zero cards
CARD_YELLOW_LEARNING = "fc000034-0000-0000-0000-000000000034"
ESSAY_GREEN = "ea00000e-0000-0000-0000-00000000000e"
SECTION_GREEN = "ec00001a-0000-0000-0000-00000000001a"
ESSAY_LEARNED = "ea00000f-0000-0000-0000-00000000000f"
CARD_LEARNED_29D = "fc000037-0000-0000-0000-000000000037"
ESSAY_MATURITY = "ea000010-0000-0000-0000-000000000010"
ESSAY_BLUE = "ea000011-0000-0000-0000-000000000011"
ESSAY_VIOLET = "ea000012-0000-0000-0000-000000000012"
ESSAY_ZERO_CARDS = "ea000009-0000-0000-0000-000000000009"


def _section_version(section_id):
    return run_sql("select updated_at from essaycards.essay_sections where id = %s", (section_id,))[0][
        "updated_at"
    ].isoformat()


def _section_result(slug, anchor, section_id, score, exam_type):
    return {
        "scope": "section", "essay_slug": slug, "section_anchor_slug": anchor,
        "section_version": _section_version(section_id), "examined_at": "2026-09-01T10:00:00Z",
        "question": "Q", "answer_transcript": "A", "score": score, "exam_type": exam_type,
    }


def _essay_result(slug, score, exam_type, examined_at="2026-09-01T10:00:00Z"):
    return {
        "scope": "essay", "essay_slug": slug, "examined_at": examined_at,
        "question": "Q", "answer_transcript": "A", "score": score, "exam_type": exam_type,
    }


def _import(client, *results):
    r = client.post(IMPORT_URL, json={"results": list(results)})
    assert r.status_code == 200, r.text
    return r.json()


def _section(client, essay_id, section_id):
    rows = client.get(PROGRESS_URL, params={"essay_id": essay_id}).json()["rows"]
    return next(r for r in rows if r["section_id"] == section_id)


def _essay(client, essay_id):
    return next(r for r in client.get("/api/essaycards/essays").json()["rows"] if r["id"] == essay_id)


def _set_interval(card_id, interval_sql):
    """Set a card's review_interval and make last_reviewed_at/next_due_at consistent with it."""
    run_sql(
        f"""
        update essaycards.flashcard_review_state
        set last_reviewed_at = now() - interval '1 hour',
            next_due_at = now() - interval '1 hour' + {interval_sql},
            review_interval = {interval_sql}
        where flashcard_id = %s
        """,
        (card_id,),
    )


def _questions(client, essay_id):
    return {r["card_key"]: r for r in client.get(f"/api/essaycards/essays/{essay_id}/questions").json()["rows"]}


# ── Section state and unlocking ──────────────────────────────────────────────

def test_passing_the_guided_section_oral_unlocks_that_sections_cards(client):
    assert client.get(f"{FLASHCARDS}/due?essay_id={ESSAY_LOCKED}").json()["rows"] == []
    body = _import(client, _section_result("fix-essay-locked", "fix-locked-1", SECTION_LOCKED, 5, "guided"))
    assert any(e["effect"] == "section_guided_unlocked" for e in body["results"][0]["effects"])
    assert _section(client, ESSAY_LOCKED, SECTION_LOCKED)["state"] == "yellow"
    due = client.get(f"{FLASHCARDS}/due?essay_id={ESSAY_LOCKED}").json()["rows"]
    assert {r["flashcard_id"] for r in due} == {CARD_LOCKED_1, CARD_LOCKED_2}


def test_locked_section_cards_are_excluded_from_focus_and_review_queues(client):
    run_sql("update essaycards.essays set category = 'LockedTopic' where id = %s", (ESSAY_LOCKED,))
    urls = [
        f"{FLASHCARDS}/due?essay_id={ESSAY_LOCKED}",
        f"{FLASHCARDS}/due?essay_id={ESSAY_LOCKED}&section_id={SECTION_LOCKED}",
        f"{FLASHCARDS}/due?topic=LockedTopic",
        f"{FLASHCARDS}/due",
    ]
    for url in urls:
        ids = {r["flashcard_id"] for r in client.get(url).json()["rows"]}
        assert not ids & {CARD_LOCKED_1, CARD_LOCKED_2}, url


def test_locked_cards_are_not_counted_in_the_queue_forecast(client):
    rows = client.get(f"{FLASHCARDS}/stats?essay_id={ESSAY_LOCKED}").json()["rows"]
    assert len(rows) == 7 and all(r["count"] == 0 for r in rows)


def test_failing_a_guided_attempt_after_passing_does_not_relock(client):
    _import(client, _section_result("fix-essay-yellow", "fix-yellow-1", SECTION_YELLOW_1, 3, "guided"))
    row = _section(client, ESSAY_YELLOW, SECTION_YELLOW_1)
    assert row["state"] == "yellow" and row["is_locked"] is False
    assert row["guided_latest_score"] == 3
    q = _questions(client, ESSAY_YELLOW)
    assert q["fix-yellow-est"]["is_locked"] is False


def test_a_card_added_to_an_already_unlocked_section_is_unlocked(client):
    r = client.post(f"{FLASHCARDS}/upsert", json={
        "essay_slug": "fix-essay-yellow", "section_id": SECTION_YELLOW_1,
        "card": {"id": "fix-yellow-added", "level": 2, "q": "new q", "a": "new a"},
    })
    assert r.status_code == 200, r.text
    due = client.get(f"{FLASHCARDS}/due?essay_id={ESSAY_YELLOW}&section_id={SECTION_YELLOW_1}").json()["rows"]
    assert r.json()["flashcard_id"] in {x["flashcard_id"] for x in due}


def test_reviewing_a_locked_card_is_rejected(client):
    before = run_sql(
        "select last_reviewed_at, next_due_at, review_interval from essaycards.flashcard_review_state where flashcard_id = %s",
        (CARD_LOCKED_1,),
    )
    events = run_sql("select count(*) as n from essaycards.review_events")[0]["n"]
    r = client.post(f"{FLASHCARDS}/{CARD_LOCKED_1}/review", json={"grade": "good"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    after = run_sql(
        "select last_reviewed_at, next_due_at, review_interval from essaycards.flashcard_review_state where flashcard_id = %s",
        (CARD_LOCKED_1,),
    )
    assert before == after
    assert run_sql("select count(*) as n from essaycards.review_events")[0]["n"] == events


def test_section_is_green_only_when_every_card_is_established(client):
    assert _section(client, ESSAY_YELLOW, SECTION_YELLOW_1)["state"] == "yellow"  # one card still learning
    _set_interval(CARD_YELLOW_LEARNING, "interval '2 days'")
    assert _section(client, ESSAY_YELLOW, SECTION_YELLOW_1)["state"] == "green"


def test_section_with_guided_passed_but_zero_cards_is_yellow_never_green(client):
    row = _section(client, ESSAY_YELLOW, SECTION_YELLOW_2)
    assert row["cards_total"] == 0
    assert row["state"] == "yellow"


def test_passing_the_unguided_section_oral_makes_the_section_blue(client):
    assert _section(client, ESSAY_GREEN, SECTION_GREEN)["state"] == "green"
    _import(client, _section_result("fix-essay-green", "fix-green-1", SECTION_GREEN, 5, "unguided"))
    row = _section(client, ESSAY_GREEN, SECTION_GREEN)
    assert row["state"] == "blue" and row["next_step"] is None


def test_unguided_pass_on_a_section_that_never_passed_guided_is_blue(client):
    assert _section(client, ESSAY_LOCKED, SECTION_LOCKED)["state"] == "grey"
    _import(client, _section_result("fix-essay-locked", "fix-locked-1", SECTION_LOCKED, 5, "unguided"))
    assert _section(client, ESSAY_LOCKED, SECTION_LOCKED)["state"] == "blue"


def test_failing_an_unguided_section_oral_does_not_revoke_blue(client):
    section_id = "ec00001d-0000-0000-0000-00000000001d"
    assert _section(client, ESSAY_BLUE, section_id)["state"] == "blue"
    _import(client, _section_result("fix-essay-blue", "fix-blue-1", section_id, 2, "unguided"))
    assert _section(client, ESSAY_BLUE, section_id)["state"] == "blue"
    hist = client.get(f"/api/essaycards/sections/{section_id}/examinations").json()["rows"]
    assert len(hist) == 1 and hist[0]["passed"] is False


def test_section_progress_lists_every_section_in_essay_then_section_order(client):
    run_sql("update essaycards.essays set category = 'Zeta', sort_index = 1 where id = %s", (ESSAY_YELLOW,))
    run_sql("update essaycards.essays set category = 'Alpha', sort_index = 1 where id = %s", (ESSAY_BLUE,))
    run_sql("update essaycards.essays set category = 'Alpha', sort_index = 0 where id = %s", (ESSAY_VIOLET,))
    all_rows = client.get(PROGRESS_URL).json()["rows"]
    # essay order = (category asc nulls last, sort_index asc, created_at asc), then section order
    essay_order = []
    for r in all_rows:
        if r["essay_id"] not in essay_order:
            essay_order.append(r["essay_id"])
    assert essay_order.index(ESSAY_VIOLET) < essay_order.index(ESSAY_BLUE) < essay_order.index(ESSAY_YELLOW)
    assert essay_order.index(ESSAY_YELLOW) < essay_order.index(ESSAY_LOCKED)  # uncategorized last
    for essay_id in essay_order:
        idx = [r["order_index"] for r in all_rows if r["essay_id"] == essay_id]
        assert idx == sorted(idx)

    filtered = client.get(PROGRESS_URL, params={"essay_id": ESSAY_YELLOW}).json()["rows"]
    assert {r["essay_id"] for r in filtered} == {ESSAY_YELLOW} and len(filtered) == 2

    unknown = client.get(PROGRESS_URL, params={"essay_id": "00000000-0000-0000-0000-000000000000"})
    assert unknown.status_code == 200 and unknown.json()["rows"] == []


# ── Card maturity ────────────────────────────────────────────────────────────

def test_learned_starts_at_30_days(client):
    q = _questions(client, ESSAY_MATURITY)
    assert q["fix-mat-23h59m"]["card_state"] == "learning"
    assert q["fix-mat-24h"]["card_state"] == "established"
    assert q["fix-mat-29d"]["card_state"] == "established"
    assert q["fix-mat-30d"]["card_state"] == "learned"


def test_new_and_locked_states(client):
    locked = _questions(client, ESSAY_LOCKED)
    assert locked["fix-locked-c1"]["card_state"] == "locked" and locked["fix-locked-c1"]["is_locked"] is True
    new = _questions(client, ESSAY_MATURITY)["fix-mat-new"]
    assert new["card_state"] == "new" and new["is_locked"] is False


# ── Essay state ──────────────────────────────────────────────────────────────

def test_essay_is_grey_with_no_oral_and_not_all_cards_learned(client):
    assert _essay(client, ESSAY_LOCKED)["essay_state"] == "grey"


def test_essay_is_yellow_only_from_a_passed_guided_essay_oral(client):
    r = client.post("/api/essaycards/essays/ingest", json={
        "title": "yellow-gate", "slug": "yellow-gate",
        "sections": [
            {"heading": "A", "anchor_slug": "yg-a", "body_markdown": "b", "cards": []},
            {"heading": "B", "anchor_slug": "yg-b", "body_markdown": "b", "cards": []},
        ],
    })
    essay_id = r.json()["essay_id"]
    unlock_essay_sections(essay_id)  # every section passed its guided SECTION oral
    assert _essay(client, essay_id)["essay_state"] == "grey"
    _import(client, _essay_result("yellow-gate", 5, "guided"))
    assert _essay(client, essay_id)["essay_state"] == "yellow"


def test_essay_is_green_when_every_card_is_learned(client):
    assert _essay(client, ESSAY_LEARNED)["essay_state"] != "green"  # one card at 29d
    _set_interval(CARD_LEARNED_29D, "interval '30 days'")
    assert _essay(client, ESSAY_LEARNED)["essay_state"] == "green"


def test_essay_with_zero_cards_is_never_green(client):
    row = _essay(client, ESSAY_ZERO_CARDS)
    assert row["progress_total"] == 0 and row["essay_state"] != "green"


def test_essay_is_blue_when_every_section_has_passed_unguided(client):
    r = client.post("/api/essaycards/essays/ingest", json={
        "title": "blue-gate", "slug": "blue-gate",
        "sections": [
            {"heading": f"S{i}", "anchor_slug": f"bg-{i}", "body_markdown": "b", "cards": []} for i in range(3)
        ],
    })
    essay_id = r.json()["essay_id"]
    ids = [s["id"] for s in client.get(f"/api/essaycards/essays/{essay_id}").json()["rows"][0]["sections"]]
    for i in (0, 1):
        _import(client, _section_result("blue-gate", f"bg-{i}", ids[i], 5, "unguided"))
    assert _essay(client, essay_id)["essay_state"] != "blue"
    _import(client, _section_result("blue-gate", "bg-2", ids[2], 5, "unguided"))
    assert _essay(client, essay_id)["essay_state"] == "blue"


def test_essay_is_violet_after_a_passing_unguided_essay_oral(client):
    assert _essay(client, ESSAY_BLUE)["essay_state"] == "blue"
    _import(client, _essay_result("fix-essay-blue", 5, "unguided", examined_at="2026-09-03T08:00:00Z"))
    row = _essay(client, ESSAY_BLUE)
    assert row["essay_state"] == "violet"
    assert datetime.fromisoformat(row["essay_unguided_passed_at"]) == datetime.fromisoformat("2026-09-03T08:00:00+00:00")


def test_violet_retake_that_passes_keeps_violet_and_updates_the_date(client):
    before = _essay(client, ESSAY_VIOLET)
    body = _import(client, _essay_result("fix-essay-violet", 6, "unguided", examined_at="2030-01-01T00:00:00Z"))
    after = _essay(client, ESSAY_VIOLET)
    assert after["essay_state"] == "violet"
    assert after["essay_unguided_passed_at"] > before["essay_unguided_passed_at"]
    assert body["revalidation"] == [] and after["revalidation_pending_count"] == 0
    hist = client.get(f"/api/essaycards/essays/{ESSAY_VIOLET}/examinations").json()["rows"]
    assert hist[0]["score"] == 6 and hist[0]["passed"] is True


def test_highest_satisfied_state_is_shown(client):
    # fix-essay-blue: every section unguided passed; make every card learned too -> green AND blue.
    for card in ("fc000044-0000-0000-0000-000000000044", "fc000045-0000-0000-0000-000000000045"):
        _set_interval(card, "interval '31 days'")
    row = _essay(client, ESSAY_BLUE)
    assert row["cards_learned_count"] == 2
    assert row["essay_state"] == "blue"


# ── Overview data ────────────────────────────────────────────────────────────

def test_category_level_counts_are_preserved(client):
    row = _essay(client, ESSAY_YELLOW)
    assert row["progress_total"] == 2          # every card
    assert row["progress_established"] == 1    # interval >= 24h


def test_open_count_excludes_locked_and_flagged_cards(client):
    assert _essay(client, ESSAY_LOCKED)["open_count"] == 0  # due by date but locked
    # fix-essay-violet: make two cards due and flag them -> not open
    run_sql(
        "update essaycards.flashcard_review_state set next_due_at = now() - interval '1 minute' "
        "where flashcard_id in ('fc000046-0000-0000-0000-000000000046','fc000047-0000-0000-0000-000000000047')"
    )
    assert _essay(client, ESSAY_VIOLET)["open_count"] == 2
    run_sql(
        "update essaycards.flashcard_review_state set needs_revalidation = true "
        "where flashcard_id = 'fc000046-0000-0000-0000-000000000046'"
    )
    assert _essay(client, ESSAY_VIOLET)["open_count"] == 1


def test_essay_oral_history_lists_attempts_newest_first(client):
    rows = client.get(f"/api/essaycards/essays/{ESSAY_YELLOW}/examinations").json()["rows"]
    assert [r["exam_type"] for r in rows] == ["unguided", "guided"]
    assert [r["passed"] for r in rows] == [False, True]
    assert client.get(f"/api/essaycards/essays/{ESSAY_LOCKED}/examinations").json()["rows"] == []
    unknown = client.get("/api/essaycards/essays/00000000-0000-0000-0000-000000000000/examinations")
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "NOT_FOUND"


# ── Migration ────────────────────────────────────────────────────────────────

def _apply_schema(db_conn):
    schema_path = os.path.join(os.path.dirname(__file__), "../schema.sql")
    with open(schema_path) as f:
        ddl = f.read()
    with db_conn.cursor() as cur:
        cur.execute(ddl)


def _seed_pre_sprint_world(db_conn):
    """Section A: a reviewed card. Section B: a guided exam scored 3, no reviewed cards.
    Section C: neither. Returns (sectionA, sectionB, sectionC)."""
    with db_conn.cursor() as cur:
        cur.execute(
            "insert into essaycards.essays (id, title, slug) values "
            "('ea0000f1-0000-0000-0000-0000000000f1', 'Mig', 'fix-mig-essay')"
        )
        cur.execute(
            "insert into essaycards.essay_sections (id, essay_id, order_index, heading, anchor_slug, body_markdown) values "
            "('ec0000f1-0000-0000-0000-0000000000f1','ea0000f1-0000-0000-0000-0000000000f1',0,'A','mig-a','a'),"
            "('ec0000f2-0000-0000-0000-0000000000f2','ea0000f1-0000-0000-0000-0000000000f1',1,'B','mig-b','b'),"
            "('ec0000f3-0000-0000-0000-0000000000f3','ea0000f1-0000-0000-0000-0000000000f1',2,'C','mig-c','c')"
        )
        cur.execute(
            "insert into essaycards.flashcards (id, essay_id, section_id, card_key, question, answer) values "
            "('fc0000f1-0000-0000-0000-0000000000f1','ea0000f1-0000-0000-0000-0000000000f1','ec0000f1-0000-0000-0000-0000000000f1','mig-ca','q','a'),"
            "('fc0000f2-0000-0000-0000-0000000000f2','ea0000f1-0000-0000-0000-0000000000f1','ec0000f2-0000-0000-0000-0000000000f2','mig-cb','q','a'),"
            "('fc0000f3-0000-0000-0000-0000000000f3','ea0000f1-0000-0000-0000-0000000000f1','ec0000f3-0000-0000-0000-0000000000f3','mig-cc','q','a')"
        )
        cur.execute(
            "insert into essaycards.flashcard_review_state (flashcard_id, last_reviewed_at, next_due_at, review_interval) values "
            "('fc0000f1-0000-0000-0000-0000000000f1', now() - interval '1 day', now() + interval '1 day', interval '2 days'),"
            "('fc0000f2-0000-0000-0000-0000000000f2', null, now(), interval '0'),"
            "('fc0000f3-0000-0000-0000-0000000000f3', null, now(), interval '0')"
        )
        cur.execute(
            "insert into essaycards.section_examinations "
            "(essay_id, section_id, section_version_at, examined_at, question, answer_transcript, score, passed, exam_type) values "
            "('ea0000f1-0000-0000-0000-0000000000f1','ec0000f2-0000-0000-0000-0000000000f2', now(), now(), 'q', 'a', 3, false, 'guided')"
        )
        # Simulate the pre-sprint database: no oral-state table yet, verdicts not stored yet.
        cur.execute("drop table essaycards.section_oral_state")
        cur.execute("alter table essaycards.section_examinations alter column passed drop not null")
        cur.execute("update essaycards.section_examinations set passed = null")


def _oral_rows(db_conn):
    with db_conn.cursor() as cur:
        cur.execute(
            "select section_id::text, guided_passed, guided_pass_source from essaycards.section_oral_state "
            "where section_id::text like 'ec0000f_%' order by section_id"
        )
        return {r["section_id"][-1]: r for r in cur.fetchall()}


def test_backfill_grandfathers_sections_with_reviewed_cards_or_old_passing_guided_exams(client, db_conn):
    _seed_pre_sprint_world(db_conn)
    _apply_schema(db_conn)
    rows = _oral_rows(db_conn)
    assert rows["1"]["guided_passed"] and rows["1"]["guided_pass_source"] == "grandfathered"
    assert rows["2"]["guided_passed"] and rows["2"]["guided_pass_source"] == "grandfathered"
    assert "3" not in rows  # no history: no state row, therefore locked


def test_backfill_is_one_time(client, db_conn):
    _seed_pre_sprint_world(db_conn)
    _apply_schema(db_conn)
    assert "3" not in _oral_rows(db_conn)
    # section C later receives a reviewed card but is deliberately left without state
    with db_conn.cursor() as cur:
        cur.execute(
            "update essaycards.flashcard_review_state "
            "set last_reviewed_at = now(), next_due_at = now() + interval '1 day', review_interval = interval '1 day' "
            "where flashcard_id = 'fc0000f3-0000-0000-0000-0000000000f3'"
        )
    _apply_schema(db_conn)
    assert "3" not in _oral_rows(db_conn)


def test_backfill_records_stored_verdicts_under_the_70_percent_rule(client, db_conn):
    _seed_pre_sprint_world(db_conn)
    with db_conn.cursor() as cur:
        for score in (3, 4, 5, 6):
            cur.execute(
                "insert into essaycards.section_examinations "
                "(essay_id, section_id, section_version_at, examined_at, question, answer_transcript, score, passed, exam_type) "
                "values ('ea0000f1-0000-0000-0000-0000000000f1','ec0000f3-0000-0000-0000-0000000000f3', now(), now(), 'q', 'a', %s, null, 'unguided')",
                (score,),
            )
    _apply_schema(db_conn)
    with db_conn.cursor() as cur:
        cur.execute(
            "select score, passed from essaycards.section_examinations "
            "where section_id = 'ec0000f3-0000-0000-0000-0000000000f3' order by score"
        )
        assert [(r["score"], r["passed"]) for r in cur.fetchall()] == [(3, False), (4, False), (5, True), (6, True)]
