"""
EssayCards — pytest tests for Sprint08_QuestionLevelsAndStructure:
GET /essays/{essay_id}/questions, GET /essays/{essay_id}/export,
POST /flashcards/upsert, and GET /flashcards/{flashcard_id}/export.

Traceability: each function name maps to an invariant in
Sprint08_QuestionLevelsAndStructure/00_draft.md.
"""

UNKNOWN_ID = "00000000-0000-0000-0000-000000000000"


from tests.helpers import unlock_essay_sections


def _mk_essay(client, slug, sections):
    """Ingest an essay from [(heading, anchor_slug, [(card_id, q, a), ...]), ...].
    Returns (essay_id, {anchor_slug: section_id}, questions_rows) — questions_rows
    is the GET .../questions response right after ingest, for tests that just
    need a baseline snapshot."""
    payload = {
        "title": slug, "slug": slug,
        "sections": [
            {
                "heading": heading, "anchor_slug": anchor, "body_markdown": f"body {anchor}",
                "cards": [{"id": cid, "q": q, "a": a} for cid, q, a in cards],
            }
            for heading, anchor, cards in sections
        ],
    }
    r = client.post("/api/essaycards/essays/ingest", json=payload)
    assert r.status_code == 200, r.text
    eid = r.json()["essay_id"]
    unlock_essay_sections(eid)  # Sprint14: freshly ingested cards start locked

    detail = client.get(f"/api/essaycards/essays/{eid}").json()["rows"][0]
    section_ids = {s["anchor_slug"]: s["id"] for s in detail["sections"]}
    questions = client.get(f"/api/essaycards/essays/{eid}/questions").json()["rows"]
    return eid, section_ids, questions


def test_existing_card_defaults_to_level_2(client):
    """Migration invariant: a card ingested without any level concept gets
    the schema default (2 — 'building/explanatory'), not null or an error."""
    eid, sections, _ = _mk_essay(client, "lvl-default", [
        ("Intro", "lvl-default-intro", [("ld-c1", "q1", "a1")]),
    ])
    rows = client.get(f"/api/essaycards/essays/{eid}/questions").json()["rows"]
    assert len(rows) == 1
    assert rows[0]["level"] == 2


def test_question_overview_orders_by_section_then_level(client):
    eid, sections, _ = _mk_essay(client, "overview-essay", [
        ("First", "overview-first", [("ov-a", "qa", "aa"), ("ov-b", "qb", "ab")]),
        ("Second", "overview-second", [("ov-c", "qc", "ac")]),
    ])
    # Bump ov-b to level 1, ov-a stays level 2 (default) — level should sort
    # ascending WITHIN "First" regardless of insertion order.
    client.post("/api/essaycards/flashcards/upsert", json={
        "essay_slug": "overview-essay", "section_id": sections["overview-first"],
        "card": {"id": "ov-b", "level": 1, "q": "qb", "a": "ab"},
    })

    rows = client.get(f"/api/essaycards/essays/{eid}/questions").json()["rows"]
    seq = [(r["section_anchor_slug"], r["level"]) for r in rows]
    assert seq == [
        ("overview-first", 1),   # ov-b, bumped to level 1
        ("overview-first", 2),   # ov-a, still default level 2
        ("overview-second", 2),  # ov-c
    ]


def test_question_overview_essay_not_found(client):
    r = client.get(f"/api/essaycards/essays/{UNKNOWN_ID}/questions")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_question_overview_empty_essay_returns_no_rows(client):
    eid, _, _ = _mk_essay(client, "empty-questions", [
        ("Stub", "empty-stub", []),
    ])
    r = client.get(f"/api/essaycards/essays/{eid}/questions")
    assert r.status_code == 200
    assert r.json()["rows"] == []


# ── POST /flashcards/upsert — update ────────────────────────────────────────

def test_upsert_updates_one_card_without_touching_neighbors_or_prose(client):
    """Core invariant: editing card A must not change card B, section prose,
    section order, or another essay."""
    eid, sections, _ = _mk_essay(client, "edit-essay", [
        ("One", "edit-one", [("ea-1", "qa1", "aa1"), ("ea-2", "qa2", "aa2")]),
        ("Two", "edit-two", [("eb-1", "qb1", "ab1")]),
    ])
    other_eid, other_sections, _ = _mk_essay(client, "unrelated-essay", [
        ("Only", "unrelated-only", [("un-1", "qu1", "au1")]),
    ])
    other_before = client.get(f"/api/essaycards/essays/{other_eid}").json()["rows"][0]
    other_questions_before = client.get(f"/api/essaycards/essays/{other_eid}/questions").json()["rows"]

    r = client.post("/api/essaycards/flashcards/upsert", json={
        "essay_slug": "edit-essay", "section_id": sections["edit-one"],
        "card": {"id": "ea-1", "level": 3, "q": "REVISED q", "a": "REVISED a"},
    })
    assert r.status_code == 200, r.text
    assert r.json()["created"] is False

    detail = client.get(f"/api/essaycards/essays/{eid}").json()["rows"][0]
    assert [s["anchor_slug"] for s in detail["sections"]] == ["edit-one", "edit-two"]
    assert next(s for s in detail["sections"] if s["anchor_slug"] == "edit-one")["body_markdown"] == "body edit-one"
    assert next(s for s in detail["sections"] if s["anchor_slug"] == "edit-two")["body_markdown"] == "body edit-two"

    rows = client.get(f"/api/essaycards/essays/{eid}/questions").json()["rows"]
    edited = next(r for r in rows if r["question"] == "REVISED q")
    assert edited["answer"] == "REVISED a"
    assert edited["level"] == 3

    neighbor = next(r for r in rows if r["section_anchor_slug"] == "edit-one" and r["question"] != "REVISED q")
    assert neighbor["question"] == "qa2" and neighbor["answer"] == "aa2" and neighbor["level"] == 2

    other_neighbor = next(r for r in rows if r["section_anchor_slug"] == "edit-two")
    assert other_neighbor["question"] == "qb1"

    # Another essay entirely: byte-for-byte untouched.
    other_after = client.get(f"/api/essaycards/essays/{other_eid}").json()["rows"][0]
    assert other_after == other_before
    other_questions_after = client.get(f"/api/essaycards/essays/{other_eid}/questions").json()["rows"]
    assert other_questions_after == other_questions_before


def test_upsert_level_change_touches_only_level(client):
    eid, sections, _ = _mk_essay(client, "level-change-essay", [
        ("One", "lc-one", [("lc-1", "q1", "a1")]),
    ])
    client.post("/api/essaycards/flashcards/upsert", json={
        "essay_slug": "level-change-essay", "section_id": sections["lc-one"],
        "card": {"id": "lc-1", "level": 2, "q": "q1", "a": "a1"},
    })

    r = client.post("/api/essaycards/flashcards/upsert", json={
        "essay_slug": "level-change-essay", "section_id": sections["lc-one"],
        "card": {"id": "lc-1", "level": 1, "q": "q1", "a": "a1"},
    })
    assert r.status_code == 200, r.text
    assert r.json()["level"] == 1

    row = client.get(f"/api/essaycards/essays/{eid}/questions").json()["rows"][0]
    assert row["level"] == 1
    assert row["question"] == "q1" and row["answer"] == "a1"


def test_upsert_preserves_review_history(client, db_conn):
    """After a level/content edit, the card's review-state row (last_reviewed_at,
    next_due_at, review_interval) must be byte-for-byte unchanged."""
    eid, sections, _ = _mk_essay(client, "history-essay", [
        ("One", "hist-one", [("hist-1", "q1", "a1")]),
    ])
    flashcard_id = client.get(f"/api/essaycards/essays/{eid}/questions").json()["rows"][0]["id"]

    review = client.post(f"/api/essaycards/flashcards/{flashcard_id}/review", json={"grade": "good"})
    assert review.status_code == 200, review.text

    with db_conn.cursor() as cur:
        cur.execute(
            "select last_reviewed_at, next_due_at, review_interval "
            "from essaycards.flashcard_review_state where flashcard_id = %s",
            (flashcard_id,),
        )
        before = dict(cur.fetchone())

    r = client.post("/api/essaycards/flashcards/upsert", json={
        "essay_slug": "history-essay", "section_id": sections["hist-one"],
        "card": {"id": "hist-1", "level": 1, "q": "REVISED", "a": "REVISED"},
    })
    assert r.status_code == 200, r.text

    with db_conn.cursor() as cur:
        cur.execute(
            "select last_reviewed_at, next_due_at, review_interval "
            "from essaycards.flashcard_review_state where flashcard_id = %s",
            (flashcard_id,),
        )
        after = dict(cur.fetchone())

    assert before == after


# ── POST /flashcards/upsert — create ────────────────────────────────────────

def test_upsert_creates_new_question_with_auto_id_preserves_everything_else(client):
    eid, sections, _ = _mk_essay(client, "add-question-essay", [
        ("One", "aq-one", [("aq-1", "q1", "a1")]),
        ("Two", "aq-two", [("aq-2", "q2", "a2")]),
    ])
    before_rows = client.get(f"/api/essaycards/essays/{eid}/questions").json()["rows"]
    before_ids = {r["id"] for r in before_rows}

    r = client.post("/api/essaycards/flashcards/upsert", json={
        "essay_slug": "add-question-essay", "section_id": sections["aq-one"],
        "card": {"level": 1, "q": "NEW question", "a": "NEW answer"},
    })
    assert r.status_code == 200, r.text
    assert r.json()["created"] is True
    new_card_id = r.json()["card_id"]
    assert new_card_id  # auto-generated, non-empty

    rows = client.get(f"/api/essaycards/essays/{eid}/questions").json()["rows"]
    assert len(rows) == 3
    new_row = next(r for r in rows if r["question"] == "NEW question")
    assert new_row["level"] == 1
    assert new_row["section_anchor_slug"] == "aq-one"

    # Every pre-existing question row (by id) is present and unchanged.
    for row in before_rows:
        matching = next(r for r in rows if r["id"] == row["id"])
        assert matching == row

    detail = client.get(f"/api/essaycards/essays/{eid}").json()["rows"][0]
    assert [s["anchor_slug"] for s in detail["sections"]] == ["aq-one", "aq-two"]


def test_upsert_explicit_new_id_creates_card(client):
    eid, sections, _ = _mk_essay(client, "explicit-id-essay", [
        ("One", "ei-one", [("ei-existing", "q1", "a1")]),
    ])
    r = client.post("/api/essaycards/flashcards/upsert", json={
        "essay_slug": "explicit-id-essay", "section_id": sections["ei-one"],
        "card": {"id": "ei-brand-new", "level": 2, "q": "q2", "a": "a2"},
    })
    assert r.status_code == 200, r.text
    assert r.json()["created"] is True
    assert r.json()["card_id"] == "ei-brand-new"

    rows = client.get(f"/api/essaycards/essays/{eid}/questions").json()["rows"]
    assert len(rows) == 2


# ── POST /flashcards/upsert — safety rails ──────────────────────────────────

def test_upsert_rejects_moving_card_to_different_section(client):
    eid, sections, _ = _mk_essay(client, "move-guard-essay", [
        ("One", "mg-one", [("mg-1", "q1", "a1")]),
        ("Two", "mg-two", []),
    ])
    r = client.post("/api/essaycards/flashcards/upsert", json={
        "essay_slug": "move-guard-essay", "section_id": sections["mg-two"],
        "card": {"id": "mg-1", "level": 2, "q": "hijack", "a": "hijack"},
    })
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"

    # Card is completely untouched.
    row = client.get(f"/api/essaycards/essays/{eid}/questions").json()["rows"][0]
    assert row["question"] == "q1"
    assert row["section_anchor_slug"] == "mg-one"


def test_upsert_essay_slug_not_found(client):
    r = client.post("/api/essaycards/flashcards/upsert", json={
        "essay_slug": "no-such-essay-slug", "section_id": UNKNOWN_ID,
        "card": {"id": "x", "level": 2, "q": "q", "a": "a"},
    })
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_upsert_section_not_found(client):
    eid, sections, _ = _mk_essay(client, "no-section-essay", [("One", "ns-one", [])])
    r = client.post("/api/essaycards/flashcards/upsert", json={
        "essay_slug": "no-section-essay", "section_id": UNKNOWN_ID,
        "card": {"id": "x", "level": 2, "q": "q", "a": "a"},
    })
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_upsert_section_belongs_to_different_essay(client):
    _, sections_a, _ = _mk_essay(client, "cross-essay-a", [("One", "ca-one", [])])
    eid_b, _, _ = _mk_essay(client, "cross-essay-b", [("One", "cb-one", [])])
    r = client.post("/api/essaycards/flashcards/upsert", json={
        "essay_slug": "cross-essay-b", "section_id": sections_a["ca-one"],
        "card": {"id": "x", "level": 2, "q": "q", "a": "a"},
    })
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert client.get(f"/api/essaycards/essays/{eid_b}/questions").json()["rows"] == []


def test_upsert_missing_level_rejected(client):
    _, sections, _ = _mk_essay(client, "missing-level-essay", [("One", "ml-one", [])])
    r = client.post("/api/essaycards/flashcards/upsert", json={
        "essay_slug": "missing-level-essay", "section_id": sections["ml-one"],
        "card": {"id": "x", "q": "q", "a": "a"},
    })
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_upsert_zero_level_rejected(client):
    _, sections, _ = _mk_essay(client, "zero-level-essay", [("One", "zl-one", [])])
    r = client.post("/api/essaycards/flashcards/upsert", json={
        "essay_slug": "zero-level-essay", "section_id": sections["zl-one"],
        "card": {"id": "x", "level": 0, "q": "q", "a": "a"},
    })
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_upsert_high_level_accepted(client):
    """Not upper-bounded — level 7 is a valid (if unconventional) value."""
    _, sections, _ = _mk_essay(client, "high-level-essay", [("One", "hl-one", [])])
    r = client.post("/api/essaycards/flashcards/upsert", json={
        "essay_slug": "high-level-essay", "section_id": sections["hl-one"],
        "card": {"id": "x", "level": 7, "q": "q", "a": "a"},
    })
    assert r.status_code == 200, r.text
    assert r.json()["level"] == 7


# ── GET /flashcards/{id}/export + AI roundtrip ──────────────────────────────

def test_export_question_includes_context_and_card(client):
    eid, sections, _ = _mk_essay(client, "export-q-essay", [
        ("One", "eq-one", [("eq-1", "q1", "a1")]),
    ])
    flashcard_id = client.get(f"/api/essaycards/essays/{eid}/questions").json()["rows"][0]["id"]

    r = client.get(f"/api/essaycards/flashcards/{flashcard_id}/export")
    assert r.status_code == 200
    pkg = r.json()

    assert pkg["essay_slug"] == "export-q-essay"
    assert pkg["section_anchor_slug"] == "eq-one"
    assert pkg["section_body_markdown"] == "body eq-one"
    # nugget_id is additive (Sprint09_Nuggets, R-CON-BP-04) — null for a card
    # with no nugget assignment.
    assert pkg["card"] == {"id": "eq-1", "level": 2, "q": "q1", "a": "a1", "nugget_id": None}


def test_export_question_not_found(client):
    r = client.get(f"/api/essaycards/flashcards/{UNKNOWN_ID}/export")
    assert r.status_code == 404


def test_single_question_ai_roundtrip_ignores_corrupted_context(client):
    """The critical invariant: export a question, edit q/a/level AND
    maliciously alter the read-only context fields (as a careless AI reply
    might, by echoing an edited version of everything it saw) — reimporting
    that full blob must change ONLY the card; section prose must be
    untouched, because POST /upsert has no field to write it to."""
    eid, sections, _ = _mk_essay(client, "roundtrip-q-essay", [
        ("One", "rtq-one", [("rtq-1", "q1", "a1")]),
    ])
    flashcard_id = client.get(f"/api/essaycards/essays/{eid}/questions").json()["rows"][0]["id"]

    pkg = client.get(f"/api/essaycards/flashcards/{flashcard_id}/export").json()
    pkg["section_body_markdown"] = "MALICIOUSLY CORRUPTED PROSE"
    pkg["section_heading"] = "CORRUPTED HEADING"
    pkg["essay_title"] = "CORRUPTED TITLE"
    pkg["card"]["q"] = "REVISED question"
    pkg["card"]["a"] = "REVISED answer"
    pkg["card"]["level"] = 3

    r = client.post("/api/essaycards/flashcards/upsert", json=pkg)
    assert r.status_code == 200, r.text

    rows = client.get(f"/api/essaycards/essays/{eid}/questions").json()["rows"]
    assert len(rows) == 1
    assert rows[0]["question"] == "REVISED question"
    assert rows[0]["answer"] == "REVISED answer"
    assert rows[0]["level"] == 3

    detail = client.get(f"/api/essaycards/essays/{eid}").json()["rows"][0]
    assert detail["title"] == "roundtrip-q-essay"
    section = detail["sections"][0]
    assert section["heading"] == "One"
    assert section["body_markdown"] == "body rtq-one"


# ── GET /essays/{essay_id}/export (single-essay export) ────────────────────

def test_export_essay_returns_full_ingest_shaped_payload(client):
    eid, sections, _ = _mk_essay(client, "export-essay-full", [
        ("One", "eef-one", [("eef-1", "q1", "a1")]),
        ("Two", "eef-two", [("eef-2", "q2", "a2")]),
    ])
    r = client.get(f"/api/essaycards/essays/{eid}/export")
    assert r.status_code == 200
    pkg = r.json()
    assert pkg["title"] == "export-essay-full"
    assert pkg["slug"] == "export-essay-full"
    assert "focus_section_id" not in pkg
    assert [s["anchor_slug"] for s in pkg["sections"]] == ["eef-one", "eef-two"]
    assert pkg["sections"][0]["cards"] == [{"id": "eef-1", "q": "q1", "a": "a1"}]


def test_export_essay_not_found(client):
    r = client.get(f"/api/essaycards/essays/{UNKNOWN_ID}/export")
    assert r.status_code == 404


def test_essay_export_then_reimport_leaves_other_essay_untouched(client):
    eid_a, _, _ = _mk_essay(client, "roundtrip-essay-a", [
        ("One", "rea-one", [("rea-1", "q1", "a1")]),
    ])
    eid_b, _, _ = _mk_essay(client, "roundtrip-essay-b", [
        ("One", "reb-one", [("reb-1", "q1", "a1")]),
    ])
    b_before = client.get(f"/api/essaycards/essays/{eid_b}").json()["rows"][0]
    b_questions_before = client.get(f"/api/essaycards/essays/{eid_b}/questions").json()["rows"]

    pkg = client.get(f"/api/essaycards/essays/{eid_a}/export").json()
    pkg["sections"][0]["body_markdown"] = "REVISED body one"

    r = client.post("/api/essaycards/essays/ingest", json=pkg)
    assert r.status_code == 200, r.text

    a_after = client.get(f"/api/essaycards/essays/{eid_a}").json()["rows"][0]
    assert a_after["sections"][0]["body_markdown"] == "REVISED body one"

    b_after = client.get(f"/api/essaycards/essays/{eid_b}").json()["rows"][0]
    assert b_after == b_before
    b_questions_after = client.get(f"/api/essaycards/essays/{eid_b}/questions").json()["rows"]
    assert b_questions_after == b_questions_before
