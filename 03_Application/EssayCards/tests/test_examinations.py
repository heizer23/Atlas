"""
EssayCards — HTTP-level pytest tests for the oral-examination round trip:
  GET  /api/essaycards/essays/{essay_id}/examination-package
  POST /api/essaycards/examinations/import
  GET  /api/essaycards/sections/{section_id}/examinations

Fixture IDs are defined in tests/fixtures.sql. Essay A
('origins-of-long-form-formats', ea000001) has section 'origins' (ec000001,
two prior examinations se-origins-1/2 — the newer scored 4) and section
'structure' (ec000002, never examined).
"""

ESSAY_A_ID = "ea000001-0000-0000-0000-000000000001"
ESSAY_A_SLUG = "origins-of-long-form-formats"
SECTION_ORIGINS_ID = "ec000001-0000-0000-0000-000000000001"
SECTION_STRUCTURE_ID = "ec000002-0000-0000-0000-000000000002"

EXPORT_URL = f"/api/essaycards/essays/{ESSAY_A_ID}/examination-package"
IMPORT_URL = "/api/essaycards/examinations/import"


def _history_url(section_id: str) -> str:
    return f"/api/essaycards/sections/{section_id}/examinations"


def _section_version(client, anchor_slug: str) -> str:
    detail = client.get(f"/api/essaycards/essays/{ESSAY_A_ID}")
    section = next(s for s in detail.json()["rows"][0]["sections"] if s["anchor_slug"] == anchor_slug)
    return section["updated_at"]


# ── Export package ──────────────────────────────────────────────────────────────

def test_export_package_shape_and_last_examination(client):
    r = client.get(EXPORT_URL)
    assert r.status_code == 200
    body = r.json()

    assert body["essay_id"] == ESSAY_A_ID
    assert body["essay_slug"] == ESSAY_A_SLUG
    assert body["essay_title"] == "The Origins of Long-Form Formats"

    sections = {s["anchor_slug"]: s for s in body["sections"]}
    assert set(sections.keys()) == {"origins", "structure"}

    origins = sections["origins"]
    assert origins["heading"] == "Origins"
    assert origins["body_markdown"] == "The essay begins with the origins of the format."
    assert origins["section_version"]
    assert {c["id"] for c in origins["flashcards"]} == {"fc-origins-1", "fc-origins-2"}
    # Most recent of the two fixture examinations (score 4), not the older one (score 3)
    assert origins["last_examination"]["score"] == 4
    assert origins["last_examination"]["feedback"] == "Clear improvement since last time."

    structure = sections["structure"]
    assert structure["last_examination"] is None


def test_export_package_not_found(client):
    r = client.get("/api/essaycards/essays/00000000-0000-0000-0000-000000000000/examination-package")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


# ── Import — success ─────────────────────────────────────────────────────────────

def test_import_stores_new_result_without_overwriting_history(client, db_conn):
    section_version = _section_version(client, "origins")

    payload = {
        "results": [
            {
                "essay_slug": ESSAY_A_SLUG,
                "section_anchor_slug": "origins",
                "section_version": section_version,
                "examined_at": "2026-08-28T14:30:00Z",
                "question": "Explain the origins a third time.",
                "answer_transcript": "An even more integrated account.",
                "score": 5,
                "feedback": "Deep understanding now.",
            }
        ]
    }

    r = client.post(IMPORT_URL, json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["imported"] == 1
    assert body["results"][0]["score"] == 5
    assert body["results"][0]["section_id"] == SECTION_ORIGINS_ID

    with db_conn.cursor() as cur:
        cur.execute(
            "select count(*) as n from essaycards.section_examinations where section_id = %s",
            (SECTION_ORIGINS_ID,),
        )
        assert cur.fetchone()["n"] == 3  # two fixture rows + this new one, none overwritten

    history = client.get(_history_url(SECTION_ORIGINS_ID))
    assert history.status_code == 200
    rows = history.json()["rows"]
    assert len(rows) == 3
    assert rows[0]["score"] == 5  # most recent first


def test_import_multiple_sections_in_one_batch(client, db_conn):
    payload = {
        "results": [
            {
                "essay_slug": ESSAY_A_SLUG,
                "section_anchor_slug": "origins",
                "section_version": _section_version(client, "origins"),
                "examined_at": "2026-08-28T14:30:00Z",
                "question": "Q1",
                "answer_transcript": "A1",
                "score": 3,
                "feedback": None,
            },
            {
                "essay_slug": ESSAY_A_SLUG,
                "section_anchor_slug": "structure",
                "section_version": _section_version(client, "structure"),
                "examined_at": "2026-08-28T14:31:00Z",
                "question": "Q2",
                "answer_transcript": "A2",
                "score": 2,
            },
        ]
    }

    r = client.post(IMPORT_URL, json=payload)
    assert r.status_code == 200
    assert r.json()["imported"] == 2

    history = client.get(_history_url(SECTION_STRUCTURE_ID))
    assert len(history.json()["rows"]) == 1
    assert history.json()["rows"][0]["score"] == 2


# ── Import — validation failures (all-or-nothing) ──────────────────────────────

def test_import_rejects_missing_results_key(client):
    r = client.post(IMPORT_URL, json={})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_import_rejects_empty_results_list(client):
    r = client.post(IMPORT_URL, json={"results": []})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_import_rejects_unparsable_json_body(client):
    r = client.post(IMPORT_URL, content=b"{not valid json", headers={"Content-Type": "application/json"})
    assert r.status_code == 400
    body = r.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "detail" not in body


def test_import_rejects_score_out_of_range_and_writes_nothing(client, db_conn):
    payload = {
        "results": [
            {
                "essay_slug": ESSAY_A_SLUG,
                "section_anchor_slug": "structure",
                "section_version": _section_version(client, "structure"),
                "examined_at": "2026-08-28T14:30:00Z",
                "question": "Q",
                "answer_transcript": "A",
                "score": 7,
            }
        ]
    }
    r = client.post(IMPORT_URL, json=payload)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"

    with db_conn.cursor() as cur:
        cur.execute(
            "select count(*) as n from essaycards.section_examinations where section_id = %s",
            (SECTION_STRUCTURE_ID,),
        )
        assert cur.fetchone()["n"] == 0


def test_import_rejects_non_integer_score(client):
    payload = {
        "results": [
            {
                "essay_slug": ESSAY_A_SLUG,
                "section_anchor_slug": "structure",
                "section_version": _section_version(client, "structure"),
                "examined_at": "2026-08-28T14:30:00Z",
                "question": "Q",
                "answer_transcript": "A",
                "score": "three",
            }
        ]
    }
    r = client.post(IMPORT_URL, json=payload)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_import_rejects_invalid_timestamp(client):
    payload = {
        "results": [
            {
                "essay_slug": ESSAY_A_SLUG,
                "section_anchor_slug": "structure",
                "section_version": _section_version(client, "structure"),
                "examined_at": "not-a-date",
                "question": "Q",
                "answer_transcript": "A",
                "score": 3,
            }
        ]
    }
    r = client.post(IMPORT_URL, json=payload)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_import_rejects_missing_required_field(client):
    payload = {
        "results": [
            {
                "essay_slug": ESSAY_A_SLUG,
                "section_anchor_slug": "structure",
                "section_version": _section_version(client, "structure"),
                "examined_at": "2026-08-28T14:30:00Z",
                "answer_transcript": "A",
                "score": 3,
            }
        ]
    }
    r = client.post(IMPORT_URL, json=payload)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


# ── Import — unknown essay/section (all-or-nothing across the whole batch) ────

def test_import_rejects_unknown_essay_slug(client, db_conn):
    payload = {
        "results": [
            {
                "essay_slug": "does-not-exist",
                "section_anchor_slug": "origins",
                "section_version": "2026-01-01T00:00:00Z",
                "examined_at": "2026-08-28T14:30:00Z",
                "question": "Q",
                "answer_transcript": "A",
                "score": 3,
            }
        ]
    }
    r = client.post(IMPORT_URL, json=payload)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_import_rejects_unknown_section_anchor_slug(client):
    payload = {
        "results": [
            {
                "essay_slug": ESSAY_A_SLUG,
                "section_anchor_slug": "does-not-exist",
                "section_version": "2026-01-01T00:00:00Z",
                "examined_at": "2026-08-28T14:30:00Z",
                "question": "Q",
                "answer_transcript": "A",
                "score": 3,
            }
        ]
    }
    r = client.post(IMPORT_URL, json=payload)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_import_batch_with_one_unknown_section_writes_nothing(client, db_conn):
    """All-or-nothing across the whole batch: a valid first result must not be
    written if a later result in the same batch fails to resolve."""
    payload = {
        "results": [
            {
                "essay_slug": ESSAY_A_SLUG,
                "section_anchor_slug": "structure",
                "section_version": _section_version(client, "structure"),
                "examined_at": "2026-08-28T14:30:00Z",
                "question": "Q",
                "answer_transcript": "A",
                "score": 3,
            },
            {
                "essay_slug": ESSAY_A_SLUG,
                "section_anchor_slug": "does-not-exist",
                "section_version": "2026-01-01T00:00:00Z",
                "examined_at": "2026-08-28T14:31:00Z",
                "question": "Q2",
                "answer_transcript": "A2",
                "score": 2,
            },
        ]
    }
    r = client.post(IMPORT_URL, json=payload)
    assert r.status_code == 404

    with db_conn.cursor() as cur:
        cur.execute(
            "select count(*) as n from essaycards.section_examinations where section_id = %s",
            (SECTION_STRUCTURE_ID,),
        )
        assert cur.fetchone()["n"] == 0


# ── Section examination history ────────────────────────────────────────────────

def test_section_history_ordered_most_recent_first(client):
    r = client.get(_history_url(SECTION_ORIGINS_ID))
    assert r.status_code == 200
    body = r.json()
    assert body["meta"]["total"] == 2
    rows = body["rows"]
    assert rows[0]["score"] == 4
    assert rows[1]["score"] == 3
    assert rows[0]["examined_at"] > rows[1]["examined_at"]


def test_section_history_empty_for_never_examined_section(client):
    r = client.get(_history_url(SECTION_STRUCTURE_ID))
    assert r.status_code == 200
    body = r.json()
    assert body["meta"]["total"] == 0
    assert body["rows"] == []


def test_section_history_not_found(client):
    r = client.get(_history_url("00000000-0000-0000-0000-000000000000"))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"
