"""
EssayCards — pytest tests for GET /essays and GET /essays/{essay_id}.

Traceability: each function name maps to a scenario in
Sprint01_Core/10_test_spec.md. Fixture IDs are defined in tests/fixtures.sql.
"""

# ── Fixture IDs (stable references to fixtures.sql) ───────────────────────────
ESSAY_A_ID = "ea000001-0000-0000-0000-000000000001"
UNKNOWN_ID = "00000000-0000-0000-0000-000000000000"


def test_list_essays_returns_dataset(client):
    """Scenario: List essays returns Dataset."""
    r = client.get("/api/essaycards/essays")
    assert r.status_code == 200
    body = r.json()
    assert body["meta"]["object_type"] == "essay"
    assert len(body["rows"]) >= 1

    row = body["rows"][0]
    for field in ("id", "title", "slug"):
        assert field in row

    created_ats = [row["created_at"] for row in body["rows"]]
    assert created_ats == sorted(created_ats)


def test_list_essays_empty(client, db_conn):
    """Scenario: List essays empty."""
    with db_conn.cursor() as cur:
        cur.execute("truncate essaycards.essays cascade")

    r = client.get("/api/essaycards/essays")
    assert r.status_code == 200
    body = r.json()
    assert body["rows"] == []
    assert body["meta"]["total"] == 0


def test_essay_detail_returns_ordered_sections(client):
    """Scenario: Essay detail returns ordered sections."""
    r = client.get(f"/api/essaycards/essays/{ESSAY_A_ID}")
    assert r.status_code == 200
    row = r.json()["rows"][0]

    sections = row["sections"]
    assert len(sections) == 2
    assert [s["order_index"] for s in sections] == sorted(s["order_index"] for s in sections)

    for s in sections:
        for field in ("id", "heading", "anchor_slug", "order_index", "body_markdown"):
            assert field in s
        assert "```flashcards" not in s["body_markdown"]


def test_essay_detail_not_found(client):
    """Scenario: Essay detail not found."""
    r = client.get(f"/api/essaycards/essays/{UNKNOWN_ID}")
    assert r.status_code == 404
    body = r.json()
    assert "error" in body
    assert body["error"]["code"] == "NOT_FOUND"
