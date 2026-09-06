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

ESSAY_D = "ea000004-0000-0000-0000-000000000004"  # stats-horizon essay, all cards future-dated
SECTION_D1 = "ec000005-0000-0000-0000-000000000005"

UNKNOWN_ID = "00000000-0000-0000-0000-000000000000"

STATS_BUCKET_ORDER = [
    "due_now", "within_10_min", "within_1_day",
    "within_7_days", "within_30_days", "beyond_30_days",
]


def _stats_counts(rows: list[dict]) -> dict[str, int]:
    return {row["bucket"]: row["count"] for row in rows}


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


# ── Queue stats ───────────────────────────────────────────────────────────────

def test_stats_system_wide_partitions_all_bands(client):
    """Scenario: Queue stats — no params returns the six system-wide horizon bands."""
    r = client.get("/api/essaycards/flashcards/stats")
    assert r.status_code == 200
    body = r.json()

    assert body["meta"]["object_type"] == "flashcard_queue_stat"
    assert body["meta"]["total"] == 6
    assert [row["bucket"] for row in body["rows"]] == STATS_BUCKET_ORDER
    for row in body["rows"]:
        for field in ("bucket", "label", "count"):
            assert field in row

    counts = _stats_counts(body["rows"])
    assert counts == {
        "due_now": 4,
        "within_10_min": 1,
        "within_1_day": 2,
        "within_7_days": 1,
        "within_30_days": 1,
        "beyond_30_days": 1,
    }
    assert sum(counts.values()) == 10  # every scheduled card lands in exactly one band


def test_stats_scoped_to_essay(client):
    """Scenario: Queue stats — scoped to a single essay."""
    r = client.get(f"/api/essaycards/flashcards/stats?essay_id={ESSAY_D}")
    assert r.status_code == 200
    counts = _stats_counts(r.json()["rows"])
    assert counts == {
        "due_now": 0,
        "within_10_min": 1,
        "within_1_day": 0,
        "within_7_days": 1,
        "within_30_days": 1,
        "beyond_30_days": 1,
    }


def test_stats_scoped_to_section(client):
    """Scenario: Queue stats — scoped to essay and section."""
    r = client.get(f"/api/essaycards/flashcards/stats?essay_id={ESSAY_A}&section_id={SECTION_A1}")
    assert r.status_code == 200
    counts = _stats_counts(r.json()["rows"])
    # section A1 holds fc-origins-1 and fc-origins-2, both already due
    assert counts["due_now"] == 2
    assert sum(counts.values()) == 2


def test_stats_section_without_essay_rejected(client):
    """Scenario: Queue stats — section_id without essay_id is rejected."""
    r = client.get(f"/api/essaycards/flashcards/stats?section_id={SECTION_A1}")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_stats_unknown_scope_is_zero_filled(client):
    """Scenario: Queue stats — empty scope still returns six zero-filled bands."""
    r = client.get(f"/api/essaycards/flashcards/stats?essay_id={UNKNOWN_ID}")
    assert r.status_code == 200
    body = r.json()
    assert [row["bucket"] for row in body["rows"]] == STATS_BUCKET_ORDER
    assert all(row["count"] == 0 for row in body["rows"])
    assert body["meta"]["total"] == 6
