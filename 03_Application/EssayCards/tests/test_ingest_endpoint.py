"""
EssayCards — HTTP-level pytest tests for POST /api/essaycards/essays/ingest.

Distinct from tests/test_ingest.py, which tests backend.ingest.ingest()
directly against markdown fixture files (unaffected by this sprint).

Traceability: each function name maps to a scenario in
Sprint02_JsonIngestion/10_test_spec.md. Fixture IDs are defined in
tests/fixtures.sql (unchanged this sprint — the existing essay
'origins-of-long-form-formats' with sections 'origins'/'structure' and card
'fc-origins-1' is sufficient to exercise every scenario below).
"""

INGEST_URL = "/api/essaycards/essays/ingest"

ESSAY_A_ID = "ea000001-0000-0000-0000-000000000001"
ESSAY_A_SLUG = "origins-of-long-form-formats"


def _essay_by_slug(db_conn, slug):
    with db_conn.cursor() as cur:
        cur.execute("select id, title, slug from essaycards.essays where slug = %s", (slug,))
        return cur.fetchone()


# ── Ingest — creates a new essay via JSON ──────────────────────────────────────

def test_ingest_json_creates_new_essay(client, db_conn):
    payload = {
        "title": "New Essay Via JSON",
        "slug": "new-essay-via-json",
        "sections": [
            {
                "heading": "First Section",
                "anchor_slug": "first-section",
                "body_markdown": "Some intro text.",
                "cards": [
                    {"id": "new-card-1", "q": "Question one?", "a": "Answer one."},
                    {"id": "new-card-2", "q": "Question two?", "a": "Answer two."},
                ],
            }
        ],
    }

    r = client.post(INGEST_URL, json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == "new-essay-via-json"
    assert body["sections_created"] == 1
    assert body["sections_updated"] == 0
    assert body["cards_created"] == 2
    assert body["cards_updated"] == 0
    essay_id = body["essay_id"]
    assert essay_id

    detail = client.get(f"/api/essaycards/essays/{essay_id}")
    assert detail.status_code == 200
    row = detail.json()["rows"][0]
    assert len(row["sections"]) == 1
    section = row["sections"][0]
    assert section["anchor_slug"] == "first-section"

    with db_conn.cursor() as cur:
        cur.execute(
            "select f.card_key, rs.last_reviewed_at, rs.next_due_at, f.created_at "
            "from essaycards.flashcards f "
            "join essaycards.flashcard_review_state rs on rs.flashcard_id = f.id "
            "where f.essay_id = %s order by f.card_key",
            (essay_id,),
        )
        cards = cur.fetchall()
        assert [c["card_key"] for c in cards] == ["new-card-1", "new-card-2"]
        for c in cards:
            assert c["last_reviewed_at"] is None
            assert c["next_due_at"] == c["created_at"]


# ── Ingest — upserts onto an existing essay by slug, preserves review state ───

def test_ingest_json_upserts_onto_existing_essay_preserves_review_state(client, db_conn):
    with db_conn.cursor() as cur:
        cur.execute(
            "select id from essaycards.flashcards where card_key = 'fc-origins-1'"
        )
        flashcard_id = cur.fetchone()["id"]
        cur.execute(
            "select last_reviewed_at, next_due_at from essaycards.flashcard_review_state "
            "where flashcard_id = %s",
            (flashcard_id,),
        )
        before = cur.fetchone()

    payload = {
        "title": "The Origins of Long-Form Formats",
        "slug": ESSAY_A_SLUG,
        "sections": [
            {
                "heading": "Origins",
                "anchor_slug": "origins",
                "body_markdown": "The essay begins with the origins of the format.",
                "cards": [
                    {"id": "fc-origins-1", "q": "Who first coined the term (updated)?", "a": "Still nobody knows."},
                    {"id": "brand-new-card", "q": "A new question?", "a": "A new answer."},
                ],
            }
        ],
    }

    r = client.post(INGEST_URL, json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["essay_id"] == ESSAY_A_ID
    assert body["sections_updated"] == 1
    assert body["cards_updated"] >= 1
    assert body["cards_created"] >= 1

    with db_conn.cursor() as cur:
        cur.execute(
            "select question from essaycards.flashcards where card_key = 'fc-origins-1'"
        )
        assert cur.fetchone()["question"] == "Who first coined the term (updated)?"

        cur.execute(
            "select last_reviewed_at, next_due_at from essaycards.flashcard_review_state "
            "where flashcard_id = %s",
            (flashcard_id,),
        )
        after = cur.fetchone()

    assert after["last_reviewed_at"] == before["last_reviewed_at"]
    assert after["next_due_at"] == before["next_due_at"]


# ── Ingest — order_index follows payload array order ───────────────────────────

def test_ingest_json_order_index_follows_payload_array_order(client):
    payload = {
        "title": "The Origins of Long-Form Formats",
        "slug": ESSAY_A_SLUG,
        "sections": [
            {
                "heading": "Structure",
                "anchor_slug": "structure",
                "body_markdown": "This section discusses structure.",
                "cards": [],
            },
            {
                "heading": "Origins",
                "anchor_slug": "origins",
                "body_markdown": "The essay begins with the origins of the format.",
                "cards": [],
            },
        ],
    }

    r = client.post(INGEST_URL, json=payload)
    assert r.status_code == 200
    essay_id = r.json()["essay_id"]

    detail = client.get(f"/api/essaycards/essays/{essay_id}")
    sections = {s["anchor_slug"]: s["order_index"] for s in detail.json()["rows"][0]["sections"]}
    assert sections["structure"] == 0
    assert sections["origins"] == 1


# ── Ingest — rejects a malformed payload before any write (all-or-nothing) ────

def test_ingest_json_rejects_malformed_payload_writes_nothing(client, db_conn):
    payload = {
        "title": "Rollback Test",
        "slug": "rollback-test",
        "sections": [
            {
                "heading": "Valid One",
                "anchor_slug": "valid-one",
                "body_markdown": "",
                "cards": [],
            },
            {
                "heading": "Valid Two",
                "anchor_slug": "valid-two",
                "body_markdown": "",
                "cards": [],
            },
            {
                "heading": "Invalid — missing anchor_slug",
                "body_markdown": "",
                "cards": [],
            },
        ],
    }

    r = client.post(INGEST_URL, json=payload)
    assert r.status_code == 400
    body = r.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"

    assert _essay_by_slug(db_conn, "rollback-test") is None
    with db_conn.cursor() as cur:
        cur.execute(
            "select count(*) as n from essaycards.essay_sections where anchor_slug in ('valid-one', 'valid-two')"
        )
        assert cur.fetchone()["n"] == 0


# ── Ingest — rejects duplicate anchor_slug within payload ─────────────────────

def test_ingest_json_rejects_duplicate_anchor_slug_in_payload(client):
    payload = {
        "title": "Dup Anchor",
        "slug": "dup-anchor-json",
        "sections": [
            {"heading": "One", "anchor_slug": "dup", "body_markdown": "", "cards": []},
            {"heading": "Two", "anchor_slug": "dup", "body_markdown": "", "cards": []},
        ],
    }

    r = client.post(INGEST_URL, json=payload)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


# ── Ingest — rejects duplicate card id within payload ──────────────────────────

def test_ingest_json_rejects_duplicate_card_id_in_payload(client):
    payload = {
        "title": "Dup Card",
        "slug": "dup-card-json",
        "sections": [
            {
                "heading": "One",
                "anchor_slug": "one",
                "body_markdown": "",
                "cards": [{"id": "dup-card", "q": "Q1", "a": "A1"}],
            },
            {
                "heading": "Two",
                "anchor_slug": "two",
                "body_markdown": "",
                "cards": [{"id": "dup-card", "q": "Q2", "a": "A2"}],
            },
        ],
    }

    r = client.post(INGEST_URL, json=payload)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


# ── Ingest — rejects a card id colliding with an existing card in a different section ─

def test_ingest_json_rejects_card_id_collision_with_different_existing_section(client, db_conn):
    payload = {
        "title": "The Origins of Long-Form Formats",
        "slug": ESSAY_A_SLUG,
        "sections": [
            {
                "heading": "Structure",
                "anchor_slug": "structure",
                "body_markdown": "This section discusses structure.",
                "cards": [{"id": "fc-origins-1", "q": "Moved question?", "a": "Moved answer."}],
            }
        ],
    }

    r = client.post(INGEST_URL, json=payload)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"

    detail = client.get(f"/api/essaycards/essays/{ESSAY_A_ID}")
    sections = detail.json()["rows"][0]["sections"]
    origins_section_id = next(s["id"] for s in sections if s["anchor_slug"] == "origins")

    with db_conn.cursor() as cur:
        cur.execute("select section_id, question from essaycards.flashcards where card_key = 'fc-origins-1'")
        row = cur.fetchone()
        assert row["section_id"] == origins_section_id
        assert row["question"] == "Who coined the term?"


# ── Ingest — rejects an unparsable JSON body ───────────────────────────────────

def test_ingest_json_rejects_unparsable_json_body(client):
    r = client.post(
        INGEST_URL,
        content=b"{not valid json",
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 400
    body = r.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    # Never FastAPI's default RequestValidationError 422 shape ({"detail": [...]})
    assert "detail" not in body


# ── Ingest — rejects a payload missing a required top-level field ─────────────

def test_ingest_json_rejects_missing_required_top_level_field(client):
    payload = {
        "title": "Missing Slug",
        "sections": [
            {"heading": "One", "anchor_slug": "one", "body_markdown": "", "cards": []},
        ],
    }

    r = client.post(INGEST_URL, json=payload)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


# ── Ingest — rejects an empty sections array ───────────────────────────────────

def test_ingest_json_rejects_empty_sections_array(client):
    payload = {"title": "No Sections", "slug": "no-sections-json", "sections": []}

    r = client.post(INGEST_URL, json=payload)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
