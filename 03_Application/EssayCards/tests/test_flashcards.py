"""
EssayCards — pytest tests for GET /flashcards/due and
POST /flashcards/{id}/review.

Traceability: each function name maps to a scenario in
Sprint01_Core/10_test_spec.md. Fixture IDs are defined in tests/fixtures.sql.
"""

from datetime import datetime

# ── Fixture IDs (stable references to fixtures.sql) ───────────────────────────
ESSAY_A = "ea000001-0000-0000-0000-000000000001"
ESSAY_B = "ea000002-0000-0000-0000-000000000002"
ESSAY_C = "ea000003-0000-0000-0000-000000000003"  # nothing due
SECTION_A1 = "ec000001-0000-0000-0000-000000000001"  # "origins" — fc-origins-1, fc-origins-2
SECTION_A2 = "ec000002-0000-0000-0000-000000000002"  # "structure" — fc-origins-3, fc-not-due

FC_ORIGINS_1 = "fc000001-0000-0000-0000-000000000001"  # last_reviewed_at=null, due
FC_ORIGINS_2 = "fc000002-0000-0000-0000-000000000002"  # last_reviewed_at=null, due
FC_ORIGINS_3 = "fc000003-0000-0000-0000-000000000003"  # last_reviewed_at=60m ago, due
FC_NOT_DUE   = "fc000004-0000-0000-0000-000000000004"  # next_due_at 1h in the future

UNKNOWN_ID = "00000000-0000-0000-0000-000000000000"


def _parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# ── Due flashcards ─────────────────────────────────────────────────────────────

def test_due_no_params_returns_system_wide(client):
    """Scenario: Due flashcards — no params returns system-wide queue."""
    r = client.get("/api/essaycards/flashcards/due")
    assert r.status_code == 200
    rows = r.json()["rows"]

    essay_ids = {row["essay_id"] for row in rows}
    assert ESSAY_A in essay_ids
    assert ESSAY_B in essay_ids

    due_ats = [row["next_due_at"] for row in rows]
    assert due_ats == sorted(due_ats)

    for row in rows:
        assert row["id"] == row["flashcard_id"]
        for field in ("question", "answer", "essay_id", "section_id", "anchor_slug", "next_due_at"):
            assert field in row


def test_due_scoped_to_essay(client):
    """Scenario: Due flashcards — scoped to essay."""
    r = client.get(f"/api/essaycards/flashcards/due?essay_id={ESSAY_A}")
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert len(rows) > 0
    assert all(row["essay_id"] == ESSAY_A for row in rows)


def test_due_scoped_to_section(client):
    """Scenario: Due flashcards — scoped to essay and section."""
    r = client.get(f"/api/essaycards/flashcards/due?essay_id={ESSAY_A}&section_id={SECTION_A1}")
    assert r.status_code == 200
    rows = r.json()["rows"]
    ids = {row["flashcard_id"] for row in rows}
    assert ids == {FC_ORIGINS_1, FC_ORIGINS_2}
    assert FC_ORIGINS_3 not in ids  # belongs to section A2, not A1


def test_due_section_without_essay_rejected(client):
    """Scenario: Due flashcards — section_id without essay_id is rejected."""
    r = client.get(f"/api/essaycards/flashcards/due?section_id={SECTION_A1}")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_due_excludes_not_yet_due_cards(client):
    """Scenario: Due flashcards — excludes not-yet-due cards."""
    r = client.get(f"/api/essaycards/flashcards/due?essay_id={ESSAY_A}")
    ids = {row["flashcard_id"] for row in r.json()["rows"]}
    assert FC_NOT_DUE not in ids


def test_due_empty_result(client):
    """Scenario: Due flashcards — empty result when nothing due."""
    r = client.get(f"/api/essaycards/flashcards/due?essay_id={ESSAY_C}")
    assert r.status_code == 200
    body = r.json()
    assert body["rows"] == []
    assert body["meta"]["total"] == 0


# ── Review ──────────────────────────────────────────────────────────────────────

def test_review_again_schedules_five_seconds(client):
    """Scenario: Review — grade again schedules five seconds out."""
    r = client.post(f"/api/essaycards/flashcards/{FC_ORIGINS_1}/review", json={"grade": "again"})
    assert r.status_code == 200
    body = r.json()
    last_reviewed = _parse_ts(body["last_reviewed_at"])
    next_due = _parse_ts(body["next_due_at"])
    delta = (next_due - last_reviewed).total_seconds()
    assert 4.5 <= delta <= 5.5


def test_review_good_first_time_uses_floor(client):
    """Scenario: Review — grade good on a never-reviewed card uses the floor."""
    r = client.post(f"/api/essaycards/flashcards/{FC_ORIGINS_2}/review", json={"grade": "good"})
    assert r.status_code == 200
    body = r.json()
    last_reviewed = _parse_ts(body["last_reviewed_at"])
    next_due = _parse_ts(body["next_due_at"])
    delta = (next_due - last_reviewed).total_seconds()
    assert 1190 <= delta <= 1210  # ~20 minutes


def test_review_good_repeat_uses_doubled_elapsed(client):
    """Scenario: Review — grade good on a repeat review doubles elapsed time."""
    r = client.post(f"/api/essaycards/flashcards/{FC_ORIGINS_3}/review", json={"grade": "good"})
    assert r.status_code == 200
    body = r.json()
    last_reviewed = _parse_ts(body["last_reviewed_at"])
    next_due = _parse_ts(body["next_due_at"])
    delta = (next_due - last_reviewed).total_seconds()
    # fixture last_reviewed_at was ~60 minutes before now; 2*60=120min exceeds the 20min floor
    assert 7100 <= delta <= 7300


def test_review_invalid_grade_rejected(client):
    """Scenario: Review — invalid grade rejected.

    Also exercises the manual raw-body validation contract (R-CON-BP-04 correction):
    missing grade key, non-string grade, and out-of-set grade must all return
    ApiError VALIDATION_ERROR (400) — never FastAPI's default 422 shape.
    """
    r = client.post(f"/api/essaycards/flashcards/{FC_ORIGINS_1}/review", json={"grade": "maybe"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"

    r_missing = client.post(f"/api/essaycards/flashcards/{FC_ORIGINS_1}/review", json={})
    assert r_missing.status_code == 400
    assert r_missing.json()["error"]["code"] == "VALIDATION_ERROR"

    r_wrong_type = client.post(f"/api/essaycards/flashcards/{FC_ORIGINS_1}/review", json={"grade": 5})
    assert r_wrong_type.status_code == 400
    assert r_wrong_type.json()["error"]["code"] == "VALIDATION_ERROR"

    r_bad_json = client.post(
        f"/api/essaycards/flashcards/{FC_ORIGINS_1}/review",
        data="not json",
        headers={"Content-Type": "application/json"},
    )
    assert r_bad_json.status_code == 400
    assert r_bad_json.json()["error"]["code"] == "VALIDATION_ERROR"


def test_review_unknown_flashcard_not_found(client):
    """Scenario: Review — unknown flashcard not found."""
    r = client.post(f"/api/essaycards/flashcards/{UNKNOWN_ID}/review", json={"grade": "good"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"
