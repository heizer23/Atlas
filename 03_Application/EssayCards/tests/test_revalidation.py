"""
EssayCards — Sprint14_SectionProgressionAndRevalidation: the Revalidation
queue and the server-derived revalidation branch of POST /flashcards/{id}/review.

Traceability: each function name maps to a scenario in
Sprint14_SectionProgressionAndRevalidation/10_test_spec.md ("Revalidation").
Flagging is done directly in SQL where the cascade itself is not the subject
(the cascade is covered in tests/test_oral_state.py).
"""

from tests.helpers import run_sql

FLASHCARDS = "/api/essaycards/flashcards"
ESSAY_A = "ea000001-0000-0000-0000-000000000001"
ESSAY_E = "ea000005-0000-0000-0000-000000000005"
ESSAY_VIOLET = "ea000012-0000-0000-0000-000000000012"

V1 = "fc000046-0000-0000-0000-000000000046"  # violet section 1, level 1, has fsrs_card_state
V2 = "fc000047-0000-0000-0000-000000000047"  # violet section 1, level 2
V3 = "fc000048-0000-0000-0000-000000000048"  # violet section 2, level 1
FC_ORIGINS_3 = "fc000003-0000-0000-0000-000000000003"  # essay A, due, reviewed 60m ago
FC_E_BACK_90D = "fc000015-0000-0000-0000-000000000015"  # essay E, established + due


def _flag(*card_ids):
    for cid in card_ids:
        run_sql("update essaycards.flashcard_review_state set needs_revalidation = true where flashcard_id = %s", (cid,))


def _state(card_id):
    return run_sql(
        "select last_reviewed_at, next_due_at, review_interval, needs_revalidation, updated_at "
        "from essaycards.flashcard_review_state where flashcard_id = %s",
        (card_id,),
    )[0]


def _fsrs(card_id):
    rows = run_sql("select * from essaycards.fsrs_card_state where flashcard_id = %s", (card_id,))
    return rows[0] if rows else None


def _n(sql, params=()):
    return run_sql(sql, params)[0]["n"]


def _review(client, card_id, grade):
    r = client.post(f"{FLASHCARDS}/{card_id}/review", json={"grade": grade})
    assert r.status_code == 200, r.text
    return r.json()


def _ids(resp):
    return [r["flashcard_id"] for r in resp.json()["rows"]]


def test_flagged_cards_are_available_regardless_of_due_date(client):
    _flag(V3, V2, V1)  # all due months in the future
    r = client.get(f"{FLASHCARDS}/revalidation", params={"essay_id": ESSAY_VIOLET})
    assert r.status_code == 200
    assert _ids(r) == [V1, V2, V3]  # section order, then level, then creation order
    assert all(row["is_new"] is False for row in r.json()["rows"])


def test_flagged_cards_are_excluded_from_the_normal_due_queue(client):
    _flag(FC_ORIGINS_3, FC_E_BACK_90D)  # both past their FSRS due date
    assert FC_ORIGINS_3 not in _ids(client.get(f"{FLASHCARDS}/due", params={"essay_id": ESSAY_A}))
    assert FC_E_BACK_90D not in _ids(client.get(f"{FLASHCARDS}/due"))  # unscoped review queue
    assert FC_E_BACK_90D not in _ids(client.get(f"{FLASHCARDS}/due", params={"essay_id": ESSAY_E}))


def test_revalidation_queue_scoping(client):
    _flag(V1, FC_ORIGINS_3)
    assert set(_ids(client.get(f"{FLASHCARDS}/revalidation"))) == {V1, FC_ORIGINS_3}
    assert _ids(client.get(f"{FLASHCARDS}/revalidation", params={"essay_id": ESSAY_VIOLET})) == [V1]
    unknown = client.get(f"{FLASHCARDS}/revalidation", params={"essay_id": "00000000-0000-0000-0000-000000000000"})
    assert unknown.status_code == 200 and unknown.json()["rows"] == []


def test_correct_revalidation_preserves_fsrs_state_exactly(client):
    _flag(V1)
    state_before, fsrs_before = _state(V1), _fsrs(V1)
    body = _review(client, V1, "good")
    assert body["revalidation_outcome"] == "preserved"
    state_after, fsrs_after = _state(V1), _fsrs(V1)
    assert state_after["needs_revalidation"] is False
    for col in ("last_reviewed_at", "next_due_at", "review_interval", "updated_at"):
        assert state_after[col] == state_before[col], col
    assert fsrs_after == fsrs_before
    assert body["next_due_at"] == state_before["next_due_at"].isoformat()
    assert body["last_reviewed_at"] == state_before["last_reviewed_at"].isoformat()


def test_correct_revalidation_is_not_a_normal_review(client):
    _flag(V1)
    events_before = _n("select count(*) as n from essaycards.review_events")
    stats_urls = [f"/api/essaycards/review-stats/{p}" for p in ("today", "summary", "activity")]
    stats_before = [client.get(u).json() for u in stats_urls]

    _review(client, V1, "good")

    assert _n("select count(*) as n from essaycards.review_events") == events_before
    assert [client.get(u).json() for u in stats_urls] == stats_before
    audit = run_sql("select outcome from essaycards.revalidation_events where flashcard_id = %s", (V1,))
    assert [a["outcome"] for a in audit] == ["preserved"]


def test_hard_and_easy_also_count_as_correct(client):
    _flag(V1, V2)
    assert _review(client, V1, "hard")["revalidation_outcome"] == "preserved"
    assert _review(client, V2, "easy")["revalidation_outcome"] == "preserved"
    assert _n("select count(*) as n from essaycards.review_events where flashcard_id in (%s, %s)", (V1, V2)) == 0


def test_incorrect_revalidation_is_a_genuine_fsrs_failure(client):
    _flag(V1)
    state_before, fsrs_before = _state(V1), _fsrs(V1)
    events_before = _n("select count(*) as n from essaycards.review_events")
    body = _review(client, V1, "again")
    assert body["revalidation_outcome"] == "failed"
    state_after = _state(V1)
    assert state_after["needs_revalidation"] is False
    assert state_after["last_reviewed_at"] > state_before["last_reviewed_at"]
    assert state_after["next_due_at"] < state_before["next_due_at"]  # long interval collapsed by the failure
    assert _fsrs(V1)["raw_state"] != fsrs_before["raw_state"]
    assert _n("select count(*) as n from essaycards.review_events") == events_before + 1
    audit = run_sql("select outcome, grade from essaycards.revalidation_events where flashcard_id = %s", (V1,))
    assert [(a["outcome"], a["grade"]) for a in audit] == [("failed", "again")]


def test_revalidation_completes_when_the_last_flagged_card_is_checked(client):
    cards = [f"fc0000{n}-0000-0000-0000-0000000000{n}" for n in (11, 12, 13, 14, 15)]
    _flag(*cards)
    before = {c: _state(c) for c in cards}
    assert len(client.get(f"{FLASHCARDS}/revalidation", params={"essay_id": ESSAY_E}).json()["rows"]) == 5

    for c in cards[:4]:
        assert _review(client, c, "good")["revalidation_outcome"] == "preserved"
    assert _review(client, cards[4], "again")["revalidation_outcome"] == "failed"

    assert client.get(f"{FLASHCARDS}/revalidation", params={"essay_id": ESSAY_E}).json()["rows"] == []
    essay_row = next(r for r in client.get("/api/essaycards/essays").json()["rows"] if r["id"] == ESSAY_E)
    assert essay_row["revalidation_pending_count"] == 0
    for c in cards[:4]:
        assert _state(c)["next_due_at"] == before[c]["next_due_at"]
    assert _state(cards[4])["next_due_at"] != before[cards[4]]["next_due_at"]


def test_review_of_a_card_flagged_mid_session_is_handled_as_revalidation(client):
    assert FC_ORIGINS_3 in _ids(client.get(f"{FLASHCARDS}/due", params={"essay_id": ESSAY_A}))  # fetched normally
    _flag(FC_ORIGINS_3)  # a cascade flags it while the stale client still shows it
    events_before = _n("select count(*) as n from essaycards.review_events")
    body = _review(client, FC_ORIGINS_3, "good")
    assert body["revalidation_outcome"] == "preserved"
    assert _n("select count(*) as n from essaycards.review_events") == events_before
