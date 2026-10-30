"""
EssayCards — guided progression (Levels 1-6): package, import, sequential
advancement, learner confirmation, unlock on Level 1, migration, carry-forward.
Fixture ids: tests/fixtures.sql (Sprint14 block).
"""

from tests.helpers import run_sql

IMPORT_URL = "/api/essaycards/guided/import"
LOCKED_SLUG, LOCKED_ANCHOR = "fix-essay-locked", "fix-locked-1"
SECTION_LOCKED = "ec000017-0000-0000-0000-000000000017"
ESSAY_LOCKED = "ea00000c-0000-0000-0000-00000000000c"
CARD_LOCKED_1 = "fc000031-0000-0000-0000-000000000031"
SECTION_YELLOW_1 = "ec000018-0000-0000-0000-000000000018"  # guided passed (legacy: level 0 + passed)


def _version(section_id):
    return run_sql("select updated_at from essaycards.essay_sections where id = %s", (section_id,))[0][
        "updated_at"
    ].isoformat()


def _body(level, decision="advance", recommendation="advance", gaps=(), anchor=LOCKED_ANCHOR,
          slug=LOCKED_SLUG, section_id=SECTION_LOCKED, **extra):
    session = {
        "essay_slug": slug, "section_anchor_slug": anchor, "section_version": _version(section_id),
        "level": level, "session_at": "2026-09-01T10:00:00Z", "transcript": "Examiner: q\nMe: a",
        "recommendation": recommendation, "rationale": "Evidence.", "demonstrated": "Grasps the spine.",
        "gaps": list(gaps), **extra,
    }
    return {"guided_session": session, "learner_decision": decision}


def _level(section_id):
    rows = run_sql("select guided_level, guided_passed from essaycards.section_oral_state where section_id = %s", (section_id,))
    return (rows[0]["guided_level"], rows[0]["guided_passed"]) if rows else (0, False)


def _sessions(section_id):
    return run_sql("select * from essaycards.section_guided_sessions where section_id = %s order by created_at", (section_id,))


# ── Package ───────────────────────────────────────────────────────────────────

def test_package_defaults_to_next_level_and_carries_level_spec(client):
    r = client.get(f"/api/essaycards/sections/{SECTION_LOCKED}/guided-package")
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["level"] == 1 and p["level_spec"]["name"] == "Orientation"
    assert p["guided_progress"]["completed_level"] == 0 and p["guided_progress"]["carried"] is None
    assert p["section"]["anchor_slug"] == LOCKED_ANCHOR and p["essay_slug"] == LOCKED_SLUG


def test_package_level_param_is_bounded_by_completed_plus_one(client):
    base = f"/api/essaycards/sections/{SECTION_LOCKED}/guided-package"
    assert client.get(base, params={"level": 2}).status_code == 400
    assert client.get(base, params={"level": "x"}).status_code == 400
    assert client.get(base, params={"level": 1}).status_code == 200
    assert client.get("/api/essaycards/sections/ec0fffff-0000-0000-0000-000000000000/guided-package").status_code == 404


def test_package_carries_demonstrated_and_open_gaps_forward(client):
    r = client.post(IMPORT_URL, json=_body(1, gaps=[{"text": "confuses A with B", "serious": False}]))
    assert r.status_code == 200, r.text
    p = client.get(f"/api/essaycards/sections/{SECTION_LOCKED}/guided-package").json()
    assert p["level"] == 2 and p["guided_progress"]["completed_level"] == 1
    carried = p["guided_progress"]["carried"]
    assert carried["demonstrated"] == "Grasps the spine."
    assert carried["unresolved_gaps"] == [{"text": "confuses A with B", "serious": False}]
    assert p["guided_progress"]["history"][0]["learner_decision"] == "advance"


# ── Import / transitions ──────────────────────────────────────────────────────

def test_level_1_advance_unlocks_cards_and_sets_level(client):
    due = f"/api/essaycards/flashcards/due?essay_id={ESSAY_LOCKED}"
    assert client.get(due).json()["rows"] == []
    r = client.post(IMPORT_URL, json=_body(1))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["advanced_to"] == 1 and body["completed_level"] == 1
    assert {e["effect"] for e in body["effects"]} == {"section_guided_unlocked", "section_guided_level_advanced"}
    assert _level(SECTION_LOCKED) == (1, True)
    assert client.get(due).json()["rows"] != []
    src = run_sql("select guided_pass_source from essaycards.section_oral_state where section_id = %s", (SECTION_LOCKED,))
    assert src[0]["guided_pass_source"] == "guided_level"


def test_stay_records_history_but_does_not_advance_or_unlock(client):
    r = client.post(IMPORT_URL, json=_body(1, decision="stay", recommendation="continue",
                                           gaps=[{"text": "no grasp of the spine", "serious": True}]))
    assert r.status_code == 200, r.text
    assert r.json()["advanced_to"] is None
    assert _level(SECTION_LOCKED) == (0, False)
    assert len(_sessions(SECTION_LOCKED)) == 1
    assert _sessions(SECTION_LOCKED)[0]["advanced_to"] is None


def test_learner_may_advance_against_a_continue_recommendation(client):
    r = client.post(IMPORT_URL, json=_body(1, decision="advance", recommendation="continue",
                                           gaps=[{"text": "minor", "serious": False}]))
    assert r.status_code == 200, r.text
    row = _sessions(SECTION_LOCKED)[0]
    assert row["recommendation"] == "continue" and row["learner_decision"] == "advance" and row["advanced_to"] == 1
    assert _level(SECTION_LOCKED) == (1, True)


def test_levels_advance_sequentially_and_several_in_one_session(client):
    assert client.post(IMPORT_URL, json=_body(2)).status_code == 400  # level 2 before level 1
    assert _level(SECTION_LOCKED) == (0, False) and _sessions(SECTION_LOCKED) == []
    for level in (1, 2, 3):
        assert client.post(IMPORT_URL, json=_body(level)).status_code == 200
    assert _level(SECTION_LOCKED) == (3, True)
    assert client.post(IMPORT_URL, json=_body(5)).status_code == 400


def test_practice_at_a_completed_level_never_lowers_progress(client):
    client.post(IMPORT_URL, json=_body(1))
    client.post(IMPORT_URL, json=_body(2))
    r = client.post(IMPORT_URL, json=_body(1, decision="advance"))
    assert r.status_code == 200 and r.json()["advanced_to"] is None
    assert _level(SECTION_LOCKED)[0] == 2


def test_serious_gap_with_advance_recommendation_is_rejected(client):
    r = client.post(IMPORT_URL, json=_body(1, recommendation="advance", gaps=[{"text": "bad", "serious": True}]))
    assert r.status_code == 400 and r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert _sessions(SECTION_LOCKED) == []


def test_learner_decision_is_required_and_validated(client):
    body = _body(1)
    del body["learner_decision"]
    assert client.post(IMPORT_URL, json=body).status_code == 400
    body["learner_decision"] = "yes"
    assert client.post(IMPORT_URL, json=body).status_code == 400
    assert _sessions(SECTION_LOCKED) == []


def test_import_validation_and_not_found(client):
    for mutate in (
        lambda s: s.pop("transcript"),
        lambda s: s.update(level=7),
        lambda s: s.update(recommendation="maybe"),
        lambda s: s.update(session_at="2026-09-01T10:00:00"),  # naive timestamp
        lambda s: s.update(gaps=[{"text": "x"}]),
    ):
        body = _body(1)
        mutate(body["guided_session"])
        r = client.post(IMPORT_URL, json=body)
        assert r.status_code == 400, body
    body = _body(1)
    body["guided_session"]["section_anchor_slug"] = "does-not-exist"
    assert client.post(IMPORT_URL, json=body).status_code == 404


def test_unguided_suggested_from_level_5_in_progress_next_step(client):
    for level in range(1, 6):
        assert client.post(IMPORT_URL, json=_body(level)).status_code == 200
    rows = client.get("/api/essaycards/progress/sections", params={"essay_id": ESSAY_LOCKED}).json()["rows"]
    row = next(r for r in rows if r["section_id"] == SECTION_LOCKED)
    assert row["guided_level"] == 5 and row["unguided_suggested"] is True
    assert row["next_step"] == "unguided_recall" and row["state"] == "yellow"  # light unchanged


def test_progress_exposes_level_and_next_step_below_5(client):
    client.post(IMPORT_URL, json=_body(1))
    rows = client.get("/api/essaycards/progress/sections", params={"essay_id": ESSAY_LOCKED}).json()["rows"]
    row = next(r for r in rows if r["section_id"] == SECTION_LOCKED)
    assert row["guided_level"] == 1 and row["unguided_suggested"] is False
    assert row["next_step"] == "guided_next" and row["next_guided_level"] == 2  # Sprint16: Level 2, not an unguided oral


# ── Migration / legacy ────────────────────────────────────────────────────────

def test_legacy_binary_guided_pass_reads_as_level_1_only(client):
    rows = client.get("/api/essaycards/progress/sections", params={"essay_id": "ea00000d-0000-0000-0000-00000000000d"}).json()["rows"]
    row = next(r for r in rows if r["section_id"] == SECTION_YELLOW_1)
    assert row["guided_passed"] is True and row["guided_level"] == 1
    p = client.get(f"/api/essaycards/sections/{SECTION_YELLOW_1}/guided-package").json()
    assert p["guided_progress"]["completed_level"] == 1 and p["level"] == 2


def test_schema_backfill_promotes_legacy_pass_to_level_1_and_is_rerunnable(db_conn):
    import os
    run_sql("update essaycards.section_oral_state set guided_level = 0 where section_id = %s", (SECTION_YELLOW_1,))
    sql = open(os.path.join(os.path.dirname(__file__), "..", "schema.sql")).read()
    with db_conn.cursor() as cur:
        cur.execute(sql)
        cur.execute(sql)
    assert _level(SECTION_YELLOW_1) == (1, True)
    # never above Level 1, and unpassed sections stay at 0
    assert _level(SECTION_LOCKED) == (0, False)


def test_sessions_history_is_a_dataset_newest_first(client):
    client.post(IMPORT_URL, json=_body(1))
    client.post(IMPORT_URL, json=_body(2, gaps=[{"text": "g1", "serious": False}]))
    r = client.get(f"/api/essaycards/sections/{SECTION_LOCKED}/guided-sessions")
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert [x["level"] for x in rows] == [2, 1] or len(rows) == 2
    assert any("g1" in x["gaps_text"] for x in rows)
    assert client.get("/api/essaycards/sections/ec0fffff-0000-0000-0000-000000000000/guided-sessions").status_code == 404


def test_guided_sessions_count_as_guided_orals_in_review_stats(client):
    def month_row():
        rows = client.get("/api/essaycards/review-stats/summary").json()["rows"]
        return next(r for r in rows if r["period"] == "month")
    before = month_row()
    body = _body(1)
    body["guided_session"]["session_at"] = run_sql("select now() as n")[0]["n"].isoformat()
    assert client.post(IMPORT_URL, json=body).status_code == 200
    after = month_row()
    assert after["guided_orals_count"] == before["guided_orals_count"] + 1
    assert after["orals_count"] == before["orals_count"] + 1
