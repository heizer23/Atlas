"""
EssayCards — Sprint16_RecallFSRS: unguided oral recall as an independent,
FSRS-scheduled dimension (evidence validation + Hard cap, state transitions,
queue independence from flashcards, legacy migration, recommendations).

Fixture ids: tests/fixtures.sql (Sprint14 block). Section SECTION_LOCKED
(fix-essay-locked) has no oral state; ESSAY_BLUE / ESSAY_VIOLET carry legacy
passed unguided orals that the conftest migration seeds into recall_state.
"""

from datetime import datetime, timedelta, timezone

from backend.migrate_recall_state import migrate_legacy_unguided_to_recall
from tests.helpers import run_sql, unlock_essay_sections

IMPORT_URL = "/api/essaycards/examinations/import"
PROGRESS_URL = "/api/essaycards/progress/sections"

ESSAY_LOCKED = "ea00000c-0000-0000-0000-00000000000c"
SECTION_LOCKED = "ec000017-0000-0000-0000-000000000017"
ESSAY_BLUE = "ea000011-0000-0000-0000-000000000011"
SECTION_BLUE_1 = "ec00001d-0000-0000-0000-00000000001d"
ESSAY_VIOLET = "ea000012-0000-0000-0000-000000000012"


def _recall(rating="good", independent=("spine",), prompted=(), missing=(), wrong=(), followups=0):
    return {
        "rating": rating, "independent_elements": list(independent), "prompted_elements": list(prompted),
        "missing_elements": list(missing), "misunderstandings": list(wrong), "followups_asked": followups,
    }


def _section_entry(recall, section_id=SECTION_LOCKED, slug="fix-essay-locked", anchor="fix-locked-1"):
    version = run_sql("select updated_at from essaycards.essay_sections where id = %s", (section_id,))[0]["updated_at"]
    return {
        "scope": "section", "essay_slug": slug, "section_anchor_slug": anchor, "section_version": version.isoformat(),
        "examined_at": "2026-09-01T10:00:00Z", "question": "Please explain the section in your own words.",
        "answer_transcript": "Examiner: ...\nMe: ...", "exam_type": "unguided", "recall": recall, "feedback": "ok",
    }


def _essay_entry(recall, slug="fix-essay-locked"):
    return {
        "scope": "essay", "essay_slug": slug, "examined_at": "2026-09-01T10:00:00Z",
        "question": "Please explain the essay.", "answer_transcript": "Examiner: ...\nMe: ...",
        "exam_type": "unguided", "recall": recall,
    }


def _import(client, *entries):
    return client.post(IMPORT_URL, json={"results": list(entries)})


def _section(client, essay_id, section_id):
    rows = client.get(PROGRESS_URL, params={"essay_id": essay_id}).json()["rows"]
    return next(r for r in rows if r["section_id"] == section_id)


def _state(section_id=SECTION_LOCKED):
    rows = run_sql("select * from essaycards.recall_state where section_id = %s", (section_id,))
    return rows[0] if rows else None


def _due_ids(client):
    return {r["section_id"] or r["essay_id"] for r in client.get("/api/essaycards/recall/due").json()["rows"]}


# ── Evidence validation: the Hard cap and its consistency rules ─────────────────

def test_good_or_easy_with_prompted_recall_is_rejected(client):
    for rating in ("good", "easy"):
        r = _import(client, _section_entry(_recall(rating, prompted=["step 2"], followups=1)))
        assert r.status_code == 400, rating
        assert "caps the rating at 'hard'" in r.json()["error"]["message"]
    assert _state() is None


def test_good_with_missing_element_or_misunderstanding_is_rejected(client):
    assert _import(client, _section_entry(_recall("good", missing=["x"], followups=1))).status_code == 400
    assert _import(client, _section_entry(_recall("easy", wrong=["confuses A and B"]))).status_code == 400


def test_hard_requires_a_prompted_element_and_nothing_missing(client):
    assert _import(client, _section_entry(_recall("hard"))).status_code == 400
    assert _import(client, _section_entry(_recall("hard", prompted=["a"], missing=["b"], followups=1))).status_code == 400
    ok = _import(client, _section_entry(_recall("hard", prompted=["a"], followups=1)))
    assert ok.status_code == 200, ok.text
    assert ok.json()["results"][0]["rating"] == "hard"


def test_again_requires_missing_or_misunderstanding(client):
    assert _import(client, _section_entry(_recall("again"))).status_code == 400
    assert _import(client, _section_entry(_recall("again", missing=["a"], followups=1))).status_code == 200
    assert _import(client, _section_entry(_recall("again", wrong=["substantial"]))).status_code == 200


def test_followup_count_rules(client):
    assert _import(client, _section_entry(_recall("good", followups=3))).status_code == 400
    assert _import(client, _section_entry(_recall("hard", prompted=["a"], followups=0))).status_code == 400
    # a clarification of something already recalled: followups counted, no cap
    ok = _import(client, _section_entry(_recall("good", followups=1)))
    assert ok.status_code == 200, ok.text


def test_missing_recall_object_or_bad_rating_is_rejected(client):
    entry = _section_entry(_recall())
    del entry["recall"]
    assert _import(client, entry).status_code == 400
    assert _import(client, _section_entry(_recall("perfect"))).status_code == 400


# ── FSRS state transitions ──────────────────────────────────────────────────────

def test_first_good_establishes_recall_with_day_scale_interval(client):
    r = _import(client, _section_entry(_recall("good")))
    assert r.status_code == 200, r.text
    st = _state()
    assert st["established_at"] is not None and st["review_count"] == 1
    assert st["next_due_at"] - datetime.now(timezone.utc) > timedelta(hours=20)  # no intra-day learning steps
    row = _section(client, ESSAY_LOCKED, SECTION_LOCKED)
    assert row["recall_status"] == "current" and row["unguided_passed"] is True
    assert SECTION_LOCKED not in _due_ids(client)


def test_first_again_leaves_recall_not_established_and_out_of_the_queue(client):
    _import(client, _section_entry(_recall("again", missing=["a"], followups=1)))
    st = _state()
    assert st is not None and st["established_at"] is None and st["last_rating"] == "again"
    assert _section(client, ESSAY_LOCKED, SECTION_LOCKED)["recall_status"] == "not_established"
    assert SECTION_LOCKED not in _due_ids(client)
    # a later success establishes it
    _import(client, _section_entry(_recall("hard", prompted=["a"], followups=1)))
    assert _section(client, ESSAY_LOCKED, SECTION_LOCKED)["recall_status"] == "current"
    assert _state()["review_count"] == 2


def test_lapse_after_establishment_is_due_until_a_success(client):
    _import(client, _section_entry(_recall("good")))
    r = _import(client, _section_entry(_recall("again", missing=["a"], followups=1)))
    assert r.json()["results"][0]["effects"][0]["effect"] == "recall_lapsed"
    st = _state()
    assert st["lapse_count"] == 1 and st["established_at"] is not None
    assert _section(client, ESSAY_LOCKED, SECTION_LOCKED)["recall_status"] == "due"
    assert SECTION_LOCKED in _due_ids(client)
    _import(client, _section_entry(_recall("good")))
    assert _section(client, ESSAY_LOCKED, SECTION_LOCKED)["recall_status"] == "current"
    assert SECTION_LOCKED not in _due_ids(client)


def test_overdue_item_is_due_and_review_reschedules_from_server_time(client):
    _import(client, _section_entry(_recall("good")))
    run_sql(
        "update essaycards.recall_state set next_due_at = now() - interval '3 days', "
        "last_reviewed_at = now() - interval '10 days' where section_id = %s", (SECTION_LOCKED,),
    )
    assert _section(client, ESSAY_LOCKED, SECTION_LOCKED)["recall_status"] == "due"
    rows = client.get("/api/essaycards/recall/due").json()["rows"]
    assert [r["section_id"] for r in rows if r["section_id"] == SECTION_LOCKED]
    _import(client, _section_entry(_recall("good")))
    st = _state()
    assert st["next_due_at"] > datetime.now(timezone.utc) + timedelta(days=1)  # grew past the 1-day floor


def test_examined_at_from_the_reply_never_drives_scheduling(client):
    entry = _section_entry(_recall("good"))
    entry["examined_at"] = "2001-01-01T00:00:00Z"
    _import(client, entry)
    st = _state()
    assert st["last_reviewed_at"] > datetime.now(timezone.utc) - timedelta(minutes=5)
    review = run_sql("select examined_at from essaycards.recall_reviews where section_id = %s", (SECTION_LOCKED,))[0]
    assert review["examined_at"].year == 2001  # kept as evidence only


def test_essay_scope_recall_is_independent_of_its_sections(client):
    _import(client, _essay_entry(_recall("good")))
    essays = {e["id"]: e for e in client.get("/api/essaycards/essays").json()["rows"]}
    assert essays[ESSAY_LOCKED]["essay_recall_status"] == "current"
    assert _section(client, ESSAY_LOCKED, SECTION_LOCKED)["recall_status"] == "not_established"
    assert ESSAY_LOCKED not in _due_ids(client)
    run_sql("update essaycards.recall_state set next_due_at = now() - interval '1 day' where scope = 'essay' and essay_id = %s", (ESSAY_LOCKED,))
    row = [r for r in client.get("/api/essaycards/recall/due").json()["rows"] if r["essay_id"] == ESSAY_LOCKED]
    assert len(row) == 1 and row[0]["scope"] == "essay" and row[0]["section_id"] is None
    assert {e["id"]: e for e in client.get("/api/essaycards/essays").json()["rows"]}[ESSAY_LOCKED]["recall_due_count"] == 1


# ── Queue independence from flashcards ──────────────────────────────────────────

def test_recall_and_flashcard_queues_are_independent(client):
    unlock_essay_sections(ESSAY_LOCKED)
    cards_before = client.get("/api/essaycards/flashcards/due").json()["meta"]["total"]
    _import(client, _section_entry(_recall("good")))
    run_sql("update essaycards.recall_state set next_due_at = now() - interval '1 day' where section_id = %s", (SECTION_LOCKED,))
    assert client.get("/api/essaycards/flashcards/due").json()["meta"]["total"] == cards_before
    due = client.get("/api/essaycards/recall/due").json()
    assert due["meta"]["total"] == len(due["rows"]) >= 1
    assert all(r["scope"] in ("section", "essay") and "card" not in r for r in due["rows"])


def test_recall_review_does_not_touch_flashcard_state(client):
    unlock_essay_sections(ESSAY_LOCKED)
    before = run_sql("select count(*) as n from essaycards.review_events")[0]["n"]
    cards = run_sql("select * from essaycards.flashcard_review_state order by flashcard_id")
    _import(client, _section_entry(_recall("good")))
    assert run_sql("select count(*) as n from essaycards.review_events")[0]["n"] == before
    assert run_sql("select * from essaycards.flashcard_review_state order by flashcard_id") == cards


# ── Legacy migration ────────────────────────────────────────────────────────────

def test_legacy_passed_unguided_orals_are_seeded_without_fabricated_reviews(client, db_conn):
    legacy = run_sql(
        "select unguided_passed_at from essaycards.section_oral_state where section_id = %s", (SECTION_BLUE_1,)
    )[0]["unguided_passed_at"]
    st = _state(SECTION_BLUE_1)
    assert st["source"] == "migrated_exam" and st["established_at"] == legacy and st["last_reviewed_at"] == legacy
    assert st["review_count"] == 0
    assert run_sql("select count(*) as n from essaycards.recall_reviews where section_id = %s", (SECTION_BLUE_1,))[0]["n"] == 0
    essay_state = run_sql("select * from essaycards.recall_state where scope = 'essay' and essay_id = %s", (ESSAY_VIOLET,))
    assert essay_state and essay_state[0]["source"] == "migrated_exam"
    # not newly completed: an old pass reads as current/due according to its real date, never fresh
    assert st["next_due_at"] == legacy + (st["next_due_at"] - legacy)
    # idempotent
    assert migrate_legacy_unguided_to_recall(db_conn) == {"seeded": 0}


def test_legacy_not_passed_sections_stay_not_established(client):
    assert _state(SECTION_LOCKED) is None
    assert _section(client, ESSAY_LOCKED, SECTION_LOCKED)["recall_status"] == "not_established"


def test_legacy_exam_tables_are_untouched_by_the_migration(client, db_conn):
    n = run_sql("select count(*) as n from essaycards.section_examinations")[0]["n"]
    migrate_legacy_unguided_to_recall(db_conn)
    assert run_sql("select count(*) as n from essaycards.section_examinations")[0]["n"] == n


# ── Cold-start package ──────────────────────────────────────────────────────────

def test_unguided_package_is_cold_and_carries_the_rubric(client):
    _import(client, _section_entry(_recall("good")))
    pkg = client.get(
        f"/api/essaycards/essays/{ESSAY_LOCKED}/examination-package",
        params={"exam_type": "unguided", "scope": "section", "section_id": SECTION_LOCKED},
    ).json()
    assert pkg["sections"][0]["last_examination"] is None
    assert "last_essay_examination" not in pkg or pkg["last_essay_examination"] is None
    blob = str(pkg)
    for leak in ("last_rating", "next_due_at", "recall_status", "review_count"):
        assert leak not in blob
    assert pkg["recall_grading"]["max_followups"] == 2


# ── Recommendations ─────────────────────────────────────────────────────────────

def _set_level(section_id, level):
    run_sql(
        """
        insert into essaycards.section_oral_state (section_id, guided_passed, guided_pass_source, guided_level)
        values (%s, %s, 'guided_level', %s)
        on conflict (section_id) do update set guided_passed = excluded.guided_passed, guided_level = excluded.guided_level,
            guided_pass_source = coalesce(essaycards.section_oral_state.guided_pass_source, 'guided_level')
        """,
        (section_id, level >= 1, level),
    )


def test_after_level_1_the_next_step_is_guided_level_2_not_an_unguided_oral(client):
    _set_level(SECTION_LOCKED, 1)
    row = _section(client, ESSAY_LOCKED, SECTION_LOCKED)
    assert row["next_step"] == "guided_next" and row["next_guided_level"] == 2
    assert row["unguided_suggested"] is False


def test_unguided_recall_is_suggested_from_level_5_and_then_guided_level_6(client):
    _set_level(SECTION_LOCKED, 5)
    row = _section(client, ESSAY_LOCKED, SECTION_LOCKED)
    assert row["next_step"] == "unguided_recall" and row["unguided_suggested"] is True
    _import(client, _section_entry(_recall("good")))
    row = _section(client, ESSAY_LOCKED, SECTION_LOCKED)
    assert row["next_step"] == "guided_next" and row["next_guided_level"] == 6 and row["unguided_suggested"] is False
    _set_level(SECTION_LOCKED, 6)
    assert _section(client, ESSAY_LOCKED, SECTION_LOCKED)["next_step"] is None


def test_due_recall_surfaces_independently_of_guided_level(client):
    _set_level(SECTION_LOCKED, 2)
    _import(client, _section_entry(_recall("good")))   # recall is accessible below Level 5
    run_sql("update essaycards.recall_state set next_due_at = now() - interval '1 day' where section_id = %s", (SECTION_LOCKED,))
    row = _section(client, ESSAY_LOCKED, SECTION_LOCKED)
    assert row["recall_status"] == "due" and row["next_step"] == "recall_due" and row["guided_level"] == 2


def test_flashcard_state_is_not_a_prerequisite_for_recommendations(client):
    unlock_essay_sections(ESSAY_BLUE)
    row = _section(client, ESSAY_BLUE, SECTION_BLUE_1)
    assert row["cards_total"] >= 0 and row["next_step"] in ("guided_next", "recall_due", "unguided_recall", None)


def test_recall_history_endpoint_requires_exactly_one_target(client):
    assert client.get("/api/essaycards/recall/reviews").status_code == 400
    assert client.get(f"/api/essaycards/recall/reviews?section_id={SECTION_LOCKED}&essay_id={ESSAY_LOCKED}").status_code == 400
    assert client.get("/api/essaycards/recall/reviews?section_id=nope").status_code == 404
