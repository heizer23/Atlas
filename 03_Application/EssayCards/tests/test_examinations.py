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

# Nuggets (Sprint09_Nuggets) — fixture essay F ('essay-f-nuggets', ea000006) /
# section F1 (ec000007, anchor 'f-nuggets') references fix-nugget-cogito
# (ee000001).
ESSAY_F_ID = "ea000006-0000-0000-0000-000000000006"
ESSAY_F_SLUG = "essay-f-nuggets"
SECTION_F1_ID = "ec000007-0000-0000-0000-000000000007"
SECTION_F1_ANCHOR = "f-nuggets"
NUGGET_COGITO_ID = "ee000001-0000-0000-0000-000000000001"


def _history_url(section_id: str) -> str:
    return f"/api/essaycards/sections/{section_id}/examinations"


def _section_version(client, anchor_slug: str) -> str:
    detail = client.get(f"/api/essaycards/essays/{ESSAY_A_ID}")
    section = next(s for s in detail.json()["rows"][0]["sections"] if s["anchor_slug"] == anchor_slug)
    return section["updated_at"]


# ── Export package ──────────────────────────────────────────────────────────────

def test_export_package_shape_and_last_examination(client):
    r = client.get(EXPORT_URL, params={"exam_type": "guided", "scope": "essay"})
    assert r.status_code == 200
    body = r.json()

    assert body["essay_id"] == ESSAY_A_ID
    assert body["essay_slug"] == ESSAY_A_SLUG
    assert body["essay_title"] == "The Origins of Long-Form Formats"
    assert body["exam_type"] == "guided"

    sections = {s["anchor_slug"]: s for s in body["sections"]}
    assert set(sections.keys()) == {"origins", "structure"}

    origins = sections["origins"]
    assert origins["heading"] == "Origins"
    assert origins["body_markdown"] == "The essay begins with the origins of the format."
    assert origins["section_version"]
    assert {c["id"] for c in origins["flashcards"]} == {"fc-origins-1", "fc-origins-2"}
    # Most recent of the two fixture examinations (score 4), not the older one (score 3)
    # — both fixture rows default to exam_type='guided' via the column DEFAULT.
    assert origins["last_examination"]["score"] == 4
    assert origins["last_examination"]["feedback"] == "Clear improvement since last time."

    structure = sections["structure"]
    assert structure["last_examination"] is None


def test_export_package_not_found(client):
    r = client.get(
        "/api/essaycards/essays/00000000-0000-0000-0000-000000000000/examination-package",
        params={"exam_type": "guided", "scope": "essay"},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_examination_package_requires_exam_type_query_param(client):
    """Scenario: missing/invalid exam_type on GET .../examination-package is
    VALIDATION_ERROR (not FastAPI's default 422 shape)."""
    r_missing = client.get(EXPORT_URL)
    assert r_missing.status_code == 400
    assert r_missing.json()["error"]["code"] == "VALIDATION_ERROR"

    r_invalid = client.get(EXPORT_URL, params={"exam_type": "bogus"})
    assert r_invalid.status_code == 400
    assert r_invalid.json()["error"]["code"] == "VALIDATION_ERROR"


def test_examination_package_unguided_never_includes_last_examination(client):
    """Scenario: exam_type=unguided always returns last_examination: null per
    section, even when guided history exists."""
    r = client.get(EXPORT_URL, params={"exam_type": "unguided", "scope": "essay"})
    assert r.status_code == 200
    body = r.json()
    assert body["exam_type"] == "unguided"
    for section in body["sections"]:
        assert section["last_examination"] is None


def test_examination_package_guided_uses_only_guided_history_for_calibration(client):
    """Scenario: exam_type=guided's last_examination reflects only prior
    guided-type exams, never unguided ones — essay-j-mixed-exam-types' section
    1 has a guided exam (score 4) and a later unguided exam (score 3); guided
    export must surface the guided score, not the more recent unguided one."""
    r = client.get(
        "/api/essaycards/essays/ea00000a-0000-0000-0000-00000000000a/examination-package",
        params={"exam_type": "guided", "scope": "essay"},
    )
    assert r.status_code == 200
    section = next(s for s in r.json()["sections"] if s["anchor_slug"] == "j-section-1")
    assert section["last_examination"]["score"] == 4


# ── Import — success ─────────────────────────────────────────────────────────────

def test_import_stores_new_result_without_overwriting_history(client, db_conn):
    section_version = _section_version(client, "origins")

    payload = {
        "results": [
            {
                "scope": "section",
                "essay_slug": ESSAY_A_SLUG,
                "section_anchor_slug": "origins",
                "section_version": section_version,
                # Far-future fixed date so this import is always the most
                # recent examination of this section regardless of the
                # fixtures' now()-relative timestamps or actual wall-clock
                # time (pre-existing test; unrelated to this sprint).
                "examined_at": "2030-01-01T00:00:00Z",
                "question": "Explain the origins a third time.",
                "answer_transcript": "An even more integrated account.",
                "score": 5,
                "feedback": "Deep understanding now.",
                "exam_type": "guided",
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
                "scope": "section",
                "essay_slug": ESSAY_A_SLUG,
                "section_anchor_slug": "origins",
                "section_version": _section_version(client, "origins"),
                "examined_at": "2026-08-28T14:30:00Z",
                "question": "Q1",
                "answer_transcript": "A1",
                "score": 3,
                "feedback": None,
                "exam_type": "guided",
            },
            {
                "scope": "section",
                "essay_slug": ESSAY_A_SLUG,
                "section_anchor_slug": "structure",
                "section_version": _section_version(client, "structure"),
                "examined_at": "2026-08-28T14:31:00Z",
                "question": "Q2",
                "answer_transcript": "A2",
                "score": 2,
                "exam_type": "unguided",
            },
        ]
    }

    r = client.post(IMPORT_URL, json=payload)
    assert r.status_code == 200
    assert r.json()["imported"] == 2

    history = client.get(_history_url(SECTION_STRUCTURE_ID))
    assert len(history.json()["rows"]) == 1
    assert history.json()["rows"][0]["score"] == 2
    assert history.json()["rows"][0]["exam_type"] == "unguided"


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
                "scope": "section",
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
                "scope": "section",
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
                "scope": "section",
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
                "scope": "section",
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
                "scope": "section",
                "essay_slug": "does-not-exist",
                "section_anchor_slug": "origins",
                "section_version": "2026-01-01T00:00:00Z",
                "examined_at": "2026-08-28T14:30:00Z",
                "question": "Q",
                "answer_transcript": "A",
                "score": 3,
                "exam_type": "guided",
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
                "scope": "section",
                "essay_slug": ESSAY_A_SLUG,
                "section_anchor_slug": "does-not-exist",
                "section_version": "2026-01-01T00:00:00Z",
                "examined_at": "2026-08-28T14:30:00Z",
                "question": "Q",
                "answer_transcript": "A",
                "score": 3,
                "exam_type": "guided",
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
                "scope": "section",
                "essay_slug": ESSAY_A_SLUG,
                "section_anchor_slug": "structure",
                "section_version": _section_version(client, "structure"),
                "examined_at": "2026-08-28T14:30:00Z",
                "question": "Q",
                "answer_transcript": "A",
                "score": 3,
                "exam_type": "guided",
            },
            {
                "scope": "section",
                "essay_slug": ESSAY_A_SLUG,
                "section_anchor_slug": "does-not-exist",
                "section_version": "2026-01-01T00:00:00Z",
                "examined_at": "2026-08-28T14:31:00Z",
                "question": "Q2",
                "answer_transcript": "A2",
                "score": 2,
                "exam_type": "guided",
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


def test_import_examinations_requires_exam_type_per_result(client):
    """Scenario: a result missing exam_type is rejected VALIDATION_ERROR,
    whole batch fails."""
    payload = {
        "results": [
            {
                "scope": "section",
                "essay_slug": ESSAY_A_SLUG,
                "section_anchor_slug": "structure",
                "section_version": _section_version(client, "structure"),
                "examined_at": "2026-08-28T14:30:00Z",
                "question": "Q", "answer_transcript": "A", "score": 3,
            }
        ]
    }
    r = client.post(IMPORT_URL, json=payload)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_import_examinations_rejects_invalid_exam_type_value(client):
    """Scenario: exam_type outside ('guided','unguided') is rejected."""
    payload = {
        "results": [
            {
                "scope": "section",
                "essay_slug": ESSAY_A_SLUG,
                "section_anchor_slug": "structure",
                "section_version": _section_version(client, "structure"),
                "examined_at": "2026-08-28T14:30:00Z",
                "question": "Q", "answer_transcript": "A", "score": 3,
                "exam_type": "bogus",
            }
        ]
    }
    r = client.post(IMPORT_URL, json=payload)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_section_examinations_history_includes_exam_type(client):
    """Scenario: GET /sections/{id}/examinations rows carry exam_type —
    fixture section origins has two 'guided' examinations (the column
    DEFAULT), so both history rows must read exam_type='guided'."""
    r = client.get(_history_url(SECTION_ORIGINS_ID))
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert len(rows) == 2
    assert all(row["exam_type"] == "guided" for row in rows)


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


# ── Nugget versions (Sprint09_Nuggets) ────────────────────────────────────────

def _f1_section_version(client):
    detail = client.get(f"/api/essaycards/essays/{ESSAY_F_ID}")
    section = next(s for s in detail.json()["rows"][0]["sections"] if s["id"] == SECTION_F1_ID)
    return section["updated_at"]


def test_examination_package_includes_nugget_versions_per_section(client):
    """Scenario: Examination package includes nugget_versions per section."""
    r = client.get(f"/api/essaycards/essays/{ESSAY_F_ID}/examination-package", params={"exam_type": "guided", "scope": "essay"})
    assert r.status_code == 200
    body = r.json()
    section = next(s for s in body["sections"] if s["section_id"] == SECTION_F1_ID)

    nugget_row = client.get(f"/api/essaycards/nuggets/{NUGGET_COGITO_ID}").json()["rows"][0]
    assert section["nugget_versions"]["fix-nugget-cogito"] == nugget_row["updated_at"]


def test_examination_import_stores_nugget_versions_verbatim(client, db_conn):
    """Scenario: Examination import stores nugget_versions verbatim."""
    payload = {
        "results": [
            {
                "scope": "section",
                "essay_slug": ESSAY_F_SLUG,
                "section_anchor_slug": SECTION_F1_ANCHOR,
                "section_version": _f1_section_version(client),
                "examined_at": "2026-08-28T14:30:00Z",
                "question": "Q", "answer_transcript": "A", "score": 4,
                "exam_type": "guided",
                "nugget_versions": {"fix-nugget-cogito": "2026-01-01T00:00:00Z"},
            }
        ]
    }
    r = client.post(IMPORT_URL, json=payload)
    assert r.status_code == 200, r.text

    with db_conn.cursor() as cur:
        cur.execute(
            "select nugget_versions_at from essaycards.section_examinations "
            "where section_id = %s order by created_at desc limit 1",
            (SECTION_F1_ID,),
        )
        row = cur.fetchone()
        assert row["nugget_versions_at"] == {"fix-nugget-cogito": "2026-01-01T00:00:00Z"}


def test_examination_import_without_nugget_versions_stores_null(client, db_conn):
    """Scenario: Examination import without nugget_versions stores null."""
    payload = {
        "results": [
            {
                "scope": "section",
                "essay_slug": ESSAY_F_SLUG,
                "section_anchor_slug": SECTION_F1_ANCHOR,
                "section_version": _f1_section_version(client),
                "examined_at": "2026-08-28T14:30:00Z",
                "question": "Q", "answer_transcript": "A", "score": 4,
                "exam_type": "guided",
            }
        ]
    }
    r = client.post(IMPORT_URL, json=payload)
    assert r.status_code == 200, r.text

    with db_conn.cursor() as cur:
        cur.execute(
            "select nugget_versions_at from essaycards.section_examinations "
            "where section_id = %s order by created_at desc limit 1",
            (SECTION_F1_ID,),
        )
        assert cur.fetchone()["nugget_versions_at"] is None


def test_nugget_freshness_flags_none_recorded_skips_check():
    """Scenario: nugget_freshness_flags with no recorded versions skips the check."""
    from backend.examinations import nugget_freshness_flags

    assert nugget_freshness_flags(None, {"a": "t1"}) == []


def test_nugget_freshness_flags_detects_changed_and_missing_keys():
    """Scenario: nugget_freshness_flags flags changed and missing keys, not matching ones."""
    from backend.examinations import nugget_freshness_flags

    recorded = {"a": "t1", "b": "t2"}
    current = {"a": "t1", "b": "t2-changed", "c": "t3"}
    assert nugget_freshness_flags(recorded, current) == ["b", "c"]
