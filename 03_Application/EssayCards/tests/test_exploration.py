"""
EssayCards — HTTP-level pytest tests for the flashcard-exploration round trip:
  GET  /api/essaycards/flashcards/{flashcard_id}/exploration-package
  POST /api/essaycards/flashcards/exploration/import        (?dry_run=true)

Fixture IDs are defined in tests/fixtures.sql. FC_ORIGINS_1 (fc-origins-1) is
essay A / section 'origins' (q "Who coined the term?", a "Nobody knows for
certain."). FC_ORIGINS_3 (fc-origins-3) is essay A / section 'structure'.
"""

ESSAY_A_SLUG = "origins-of-long-form-formats"
ESSAY_A_ID = "ea000001-0000-0000-0000-000000000001"

SECTION_ORIGINS_ID = "ec000001-0000-0000-0000-000000000001"
SECTION_STRUCTURE_ID = "ec000002-0000-0000-0000-000000000002"

FC_ORIGINS_1 = "fc000001-0000-0000-0000-000000000001"
FC_ORIGINS_3 = "fc000003-0000-0000-0000-000000000003"

UNKNOWN_ID = "00000000-0000-0000-0000-000000000000"

PKG_URL = f"/api/essaycards/flashcards/{FC_ORIGINS_1}/exploration-package"
IMPORT_URL = "/api/essaycards/flashcards/exploration/import"
DRY_URL = IMPORT_URL + "?dry_run=true"


def _discussion(card_id=FC_ORIGINS_1, knowledge_gap="I conflated two ideas."):
    return {
        "type": "save_discussion",
        "card_id": card_id,
        "discussion": {
            "exploration_question": "Is consciousness basically the self for Husserl?",
            "discussion_summary": "We separated the intentional stream from the transcendental ego.",
            "resolution": "Consciousness and the transcendental ego are related but not identical.",
            "knowledge_gap": knowledge_gap,
        },
    }


# ── Export package ──────────────────────────────────────────────────────────────

def test_export_package_shape(client):
    r = client.get(PKG_URL)
    assert r.status_code == 200
    body = r.json()

    assert body["export_version"] == 1
    card = body["card"]
    assert card["card_id"] == FC_ORIGINS_1
    assert card["card_key"] == "fc-origins-1"
    assert card["essay_slug"] == ESSAY_A_SLUG
    assert card["essay_title"] == "The Origins of Long-Form Formats"
    assert card["section_id"] == SECTION_ORIGINS_ID
    assert card["section_anchor_slug"] == "origins"
    assert card["section_heading"] == "Origins"
    assert card["question"] == "Who coined the term?"
    assert card["answer"] == "Nobody knows for certain."
    # Section body is the context; the whole essay is not exported.
    assert body["context"]["section_body_markdown"] == "The essay begins with the origins of the format."
    assert "essay" not in body["context"]


def test_export_package_unknown_id_404(client):
    r = client.get(f"/api/essaycards/flashcards/{UNKNOWN_ID}/exploration-package")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_export_package_malformed_id_404(client):
    r = client.get("/api/essaycards/flashcards/not-a-uuid/exploration-package")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_export_does_not_touch_review_state(client, db_conn):
    with db_conn.cursor() as cur:
        cur.execute(
            "select last_reviewed_at, next_due_at from essaycards.flashcard_review_state where flashcard_id = %s",
            (FC_ORIGINS_1,),
        )
        before = cur.fetchone()
    client.get(PKG_URL)
    with db_conn.cursor() as cur:
        cur.execute(
            "select last_reviewed_at, next_due_at from essaycards.flashcard_review_state where flashcard_id = %s",
            (FC_ORIGINS_1,),
        )
        after = cur.fetchone()
    assert before == after


def test_export_package_serializes_awkward_text(client, db_conn):
    tricky_q = 'He asked, "what is *the self*?"\nLine two — em dash, quote: "x"'
    tricky_a = "Answer with `code`, Ünicode: café, emoji 🧠, and a backslash \\ plus \"quotes\"."
    with db_conn.cursor() as cur:
        cur.execute(
            "update essaycards.flashcards set question = %s, answer = %s where id = %s",
            (tricky_q, tricky_a, FC_ORIGINS_1),
        )
        db_conn.commit()
    r = client.get(PKG_URL)
    assert r.status_code == 200
    assert r.json()["card"]["question"] == tricky_q
    assert r.json()["card"]["answer"] == tricky_a


# ── Discussion import (save_discussion only) ────────────────────────────────────

def test_save_discussion_creates_row_with_snapshots(client, db_conn):
    r = client.post(IMPORT_URL, json={"actions": [_discussion()]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["applied"] is True
    assert body["revisions"] == []
    assert body["created_cards"] == []

    with db_conn.cursor() as cur:
        cur.execute(
            "select * from essaycards.flashcard_discussions where card_id = %s",
            (FC_ORIGINS_1,),
        )
        rows = cur.fetchall()
    assert len(rows) == 1
    row = rows[0]
    assert str(row["id"]) == body["discussion_id"]
    assert row["question_at_time"] == "Who coined the term?"
    assert row["answer_at_time"] == "Nobody knows for certain."
    assert str(row["section_id_at_time"]) == SECTION_ORIGINS_ID
    assert row["exploration_question"] == "Is consciousness basically the self for Husserl?"
    assert row["resolution"].startswith("Consciousness and the transcendental ego")
    assert row["knowledge_gap"] == "I conflated two ideas."


def test_save_discussion_knowledge_gap_may_be_null(client, db_conn):
    r = client.post(IMPORT_URL, json={"actions": [_discussion(knowledge_gap=None)]})
    assert r.status_code == 200, r.text
    with db_conn.cursor() as cur:
        cur.execute(
            "select knowledge_gap from essaycards.flashcard_discussions where card_id = %s",
            (FC_ORIGINS_1,),
        )
        assert cur.fetchone()["knowledge_gap"] is None


def test_save_discussion_accepts_bare_action_object(client, db_conn):
    r = client.post(IMPORT_URL, json=_discussion())
    assert r.status_code == 200, r.text
    with db_conn.cursor() as cur:
        cur.execute("select count(*) as n from essaycards.flashcard_discussions")
        assert cur.fetchone()["n"] == 1


def test_dry_run_previews_without_writing(client, db_conn):
    r = client.post(DRY_URL, json={"actions": [_discussion()]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["dry_run"] is True
    assert body["applied"] is False
    assert body["preview"]["save_discussion"]["card_key"] == "fc-origins-1"
    assert body["preview"]["save_discussion"]["snapshot"]["question_at_time"] == "Who coined the term?"

    with db_conn.cursor() as cur:
        cur.execute("select count(*) as n from essaycards.flashcard_discussions")
        assert cur.fetchone()["n"] == 0


def test_import_requires_save_discussion(client):
    payload = {"actions": [{
        "type": "update_card",
        "card_id": FC_ORIGINS_1,
        "changes": {"question": "Better?"},
        "reason": "clarity",
    }]}
    r = client.post(IMPORT_URL, json=payload)
    assert r.status_code == 400
    assert "exactly one save_discussion" in r.json()["error"]["message"]


def test_import_rejects_unknown_action_type(client):
    payload = {"actions": [_discussion(), {"type": "delete_everything", "card_id": FC_ORIGINS_1}]}
    r = client.post(IMPORT_URL, json=payload)
    assert r.status_code == 400
    msg = r.json()["error"]["message"]
    assert "unknown action type" in msg
    assert "delete_everything" in msg


def test_import_rejects_unparsable_json(client):
    r = client.post(IMPORT_URL, content=b"{nope", headers={"Content-Type": "application/json"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "not valid JSON" in r.json()["error"]["message"]


def test_import_error_message_is_copy_pasteable(client):
    r = client.post(IMPORT_URL, json={"actions": [_discussion(), {
        "type": "update_card", "card_id": FC_ORIGINS_1, "changes": {}, "reason": "x",
    }]})
    assert r.status_code == 400
    msg = r.json()["error"]["message"]
    assert msg.startswith("EssayCards could not import this exploration result.")
    assert "Nothing was saved." in msg
    assert "send the complete EssayCards return package again." in msg


def test_import_unknown_card_id_404_writes_nothing(client, db_conn):
    r = client.post(IMPORT_URL, json={"actions": [_discussion(card_id=UNKNOWN_ID)]})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"
    with db_conn.cursor() as cur:
        cur.execute("select count(*) as n from essaycards.flashcard_discussions")
        assert cur.fetchone()["n"] == 0


# ── update_card ────────────────────────────────────────────────────────────────

def _update_q(card_id=FC_ORIGINS_1):
    return {
        "type": "update_card",
        "card_id": card_id,
        "changes": {"question": "Who is credited with coining the term, if anyone?"},
        "reason": "The original 'Who coined the term?' is ambiguous in standalone review.",
    }


def test_update_card_updates_live_card_and_keeps_history(client, db_conn):
    r = client.post(IMPORT_URL, json={"actions": [_discussion(), _update_q()]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["revisions"]) == 1
    assert body["revisions"][0]["changed_fields"] == ["question"]

    with db_conn.cursor() as cur:
        cur.execute("select question, answer from essaycards.flashcards where id = %s", (FC_ORIGINS_1,))
        card = cur.fetchone()
        assert card["question"] == "Who is credited with coining the term, if anyone?"
        assert card["answer"] == "Nobody knows for certain."  # untouched

        cur.execute("select * from essaycards.flashcard_revisions where card_id = %s", (FC_ORIGINS_1,))
        rev = cur.fetchone()
        assert rev["old_question"] == "Who coined the term?"
        assert rev["new_question"] == "Who is credited with coining the term, if anyone?"
        assert rev["old_answer"] == "Nobody knows for certain."
        assert rev["new_answer"] == "Nobody knows for certain."
        assert rev["reason"].startswith("The original")
        assert str(rev["source_discussion_id"]) == body["discussion_id"]


def test_update_card_answer_only_leaves_question(client, db_conn):
    payload = {"actions": [_discussion(), {
        "type": "update_card",
        "card_id": FC_ORIGINS_1,
        "changes": {"answer": "The coinage is undocumented; no single figure is credited."},
        "reason": "Old answer was too terse to be a useful recall target.",
    }]}
    r = client.post(IMPORT_URL, json=payload)
    assert r.status_code == 200, r.text
    with db_conn.cursor() as cur:
        cur.execute("select question, answer from essaycards.flashcards where id = %s", (FC_ORIGINS_1,))
        card = cur.fetchone()
        assert card["question"] == "Who coined the term?"
        assert card["answer"].startswith("The coinage is undocumented")
        cur.execute("select old_question, new_question from essaycards.flashcard_revisions where card_id = %s", (FC_ORIGINS_1,))
        rev = cur.fetchone()
        assert rev["old_question"] == rev["new_question"] == "Who coined the term?"


def test_edited_away_question_not_in_due_queue(client):
    client.post(IMPORT_URL, json={"actions": [_discussion(), _update_q()]})
    # fc-origins-1 is a new card, so scope the queue to its essay (a focus
    # session) — the unscoped review queue only carries established cards.
    due = client.get(f"/api/essaycards/flashcards/due?essay_id={ESSAY_A_ID}")
    questions = [row["question"] for row in due.json()["rows"]]
    assert "Who coined the term?" not in questions
    assert "Who is credited with coining the term, if anyone?" in questions


def test_update_card_requires_reason(client):
    payload = {"actions": [_discussion(), {
        "type": "update_card", "card_id": FC_ORIGINS_1, "changes": {"question": "New?"},
    }]}
    r = client.post(IMPORT_URL, json=payload)
    assert r.status_code == 400
    assert '"reason" is required' in r.json()["error"]["message"]


def test_update_card_rejects_non_whitelisted_field(client):
    payload = {"actions": [_discussion(), {
        "type": "update_card", "card_id": FC_ORIGINS_1,
        "changes": {"section_id": SECTION_STRUCTURE_ID}, "reason": "move it",
    }]}
    r = client.post(IMPORT_URL, json=payload)
    assert r.status_code == 400
    assert "may only contain" in r.json()["error"]["message"]


def test_update_card_rejects_empty_changes(client):
    payload = {"actions": [_discussion(), {
        "type": "update_card", "card_id": FC_ORIGINS_1, "changes": {}, "reason": "x",
    }]}
    r = client.post(IMPORT_URL, json=payload)
    assert r.status_code == 400
    assert "non-empty object" in r.json()["error"]["message"]


def test_dry_run_update_card_shows_old_and_new(client, db_conn):
    r = client.post(DRY_URL, json={"actions": [_discussion(), _update_q()]})
    assert r.status_code == 200
    upd = r.json()["preview"]["update_card"][0]
    assert upd["old"]["question"] == "Who coined the term?"
    assert upd["new"]["question"] == "Who is credited with coining the term, if anyone?"
    assert upd["reason"].startswith("The original")
    with db_conn.cursor() as cur:
        cur.execute("select count(*) as n from essaycards.flashcard_revisions")
        assert cur.fetchone()["n"] == 0
        cur.execute("select question from essaycards.flashcards where id = %s", (FC_ORIGINS_1,))
        assert cur.fetchone()["question"] == "Who coined the term?"


# ── create_card ───────────────────────────────────────────────────────────────

def _create(section_id=SECTION_ORIGINS_ID, anchor="origins"):
    action = {
        "type": "create_card",
        "section_id": section_id,
        "question": "How does the distinction between stream and ego cash out?",
        "answer": "The ego is the pole of acts; the stream is the acts themselves.",
    }
    if anchor is not None:
        action["section_anchor_slug"] = anchor
    return action


def test_create_card_adds_card_with_review_state(client, db_conn):
    r = client.post(IMPORT_URL, json={"actions": [_discussion(), _create()]})
    assert r.status_code == 200, r.text
    new_id = r.json()["created_cards"][0]["id"]
    new_key = r.json()["created_cards"][0]["card_key"]
    assert new_key.startswith("disc-")

    with db_conn.cursor() as cur:
        cur.execute("select section_id, essay_id, card_key from essaycards.flashcards where id = %s", (new_id,))
        row = cur.fetchone()
        assert str(row["section_id"]) == SECTION_ORIGINS_ID
        cur.execute("select count(*) as n from essaycards.flashcard_review_state where flashcard_id = %s", (new_id,))
        assert cur.fetchone()["n"] == 1


def test_create_card_no_reason_required(client):
    r = client.post(IMPORT_URL, json={"actions": [_discussion(), _create()]})
    assert r.status_code == 200


def test_create_card_source_card_unchanged(client, db_conn):
    client.post(IMPORT_URL, json={"actions": [_discussion(), _create()]})
    with db_conn.cursor() as cur:
        cur.execute("select question, answer from essaycards.flashcards where id = %s", (FC_ORIGINS_1,))
        card = cur.fetchone()
    assert card["question"] == "Who coined the term?"
    assert card["answer"] == "Nobody knows for certain."


def test_create_card_unknown_section_404_writes_nothing(client, db_conn):
    r = client.post(IMPORT_URL, json={"actions": [_discussion(), _create(section_id=UNKNOWN_ID, anchor=None)]})
    assert r.status_code == 404
    with db_conn.cursor() as cur:
        cur.execute("select count(*) as n from essaycards.flashcard_discussions")
        assert cur.fetchone()["n"] == 0


def test_create_card_anchor_mismatch_rejected(client):
    r = client.post(IMPORT_URL, json={"actions": [_discussion(), _create(anchor="structure")]})
    assert r.status_code == 400
    assert "does not match section_id" in r.json()["error"]["message"]


# ── Combined imports ──────────────────────────────────────────────────────────

def test_combined_discussion_update_create(client, db_conn):
    payload = {"actions": [_discussion(), _update_q(), _create()]}
    r = client.post(IMPORT_URL, json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["discussion_id"]
    assert len(body["revisions"]) == 1
    assert len(body["created_cards"]) == 1

    with db_conn.cursor() as cur:
        cur.execute("select source_discussion_id from essaycards.flashcard_revisions where card_id = %s", (FC_ORIGINS_1,))
        assert str(cur.fetchone()["source_discussion_id"]) == body["discussion_id"]
        cur.execute("select count(*) as n from essaycards.flashcards where section_id = %s", (SECTION_ORIGINS_ID,))
        # 2 fixture cards in 'origins' + 1 new
        assert cur.fetchone()["n"] == 3


def test_combined_rolls_back_entirely_when_one_action_fails(client, db_conn):
    payload = {"actions": [_discussion(), _update_q(), _create(section_id=UNKNOWN_ID, anchor=None)]}
    r = client.post(IMPORT_URL, json=payload)
    assert r.status_code == 404

    with db_conn.cursor() as cur:
        cur.execute("select count(*) as n from essaycards.flashcard_discussions")
        assert cur.fetchone()["n"] == 0
        cur.execute("select count(*) as n from essaycards.flashcard_revisions")
        assert cur.fetchone()["n"] == 0
        cur.execute("select question from essaycards.flashcards where id = %s", (FC_ORIGINS_1,))
        assert cur.fetchone()["question"] == "Who coined the term?"


def test_two_update_cards_same_id_rejected(client):
    payload = {"actions": [
        _discussion(),
        _update_q(),
        {"type": "update_card", "card_id": FC_ORIGINS_1, "changes": {"answer": "x y z"}, "reason": "also this"},
    ]}
    r = client.post(IMPORT_URL, json=payload)
    assert r.status_code == 400
    assert "more than one update_card" in r.json()["error"]["message"]
