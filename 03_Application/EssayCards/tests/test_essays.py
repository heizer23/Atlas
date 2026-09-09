"""
EssayCards — pytest tests for GET /essays and GET /essays/{essay_id}.

Traceability: each function name maps to a scenario in
Sprint01_Core/10_test_spec.md. Fixture IDs are defined in tests/fixtures.sql.
"""

from datetime import datetime, timezone

# ── Fixture IDs (stable references to fixtures.sql) ───────────────────────────
ESSAY_A_ID = "ea000001-0000-0000-0000-000000000001"
SECTION_A2_ID = "ec000002-0000-0000-0000-000000000002"  # essay A / "structure" — never examined in fixtures
UNKNOWN_ID = "00000000-0000-0000-0000-000000000000"


def _mk_essay(client, slug, n_cards, **extra):
    """Ingest an essay with n_cards freshly-open (new, interval 0) cards.
    Returns its essay_id."""
    payload = {
        "title": slug, "slug": slug,
        "sections": [{
            "heading": "S", "anchor_slug": f"{slug}-s", "body_markdown": "b",
            "cards": [{"id": f"{slug}-c{i}", "q": f"q{i}", "a": f"a{i}"} for i in range(n_cards)],
        }],
        **extra,
    }
    r = client.post("/api/essaycards/essays/ingest", json=payload)
    assert r.status_code == 200, r.text
    return r.json()["essay_id"]


def _overview_row(client, essay_id):
    return next(r for r in client.get("/api/essaycards/essays").json()["rows"] if r["id"] == essay_id)


def test_list_essays_returns_dataset(client):
    """Scenario: List essays returns Dataset."""
    r = client.get("/api/essaycards/essays")
    assert r.status_code == 200
    body = r.json()
    assert body["meta"]["object_type"] == "essay"
    assert len(body["rows"]) >= 1

    row = body["rows"][0]
    for field in ("id", "title", "slug", "category", "sort_index", "status",
                  "progress_total", "progress_established", "open_count",
                  "oral_score", "oral_date"):
        assert field in row

    # All fixture essays are uncategorized (category null, sort_index 0), so the
    # (category nulls last, sort_index, created_at) ordering falls back to
    # created_at asc.
    created_ats = [row["created_at"] for row in body["rows"]]
    assert created_ats == sorted(created_ats)


def test_list_essays_grouped_by_category_and_sort_index(client):
    """Essays ingested with category/sort_index come back ordered
    (category asc nulls last, sort_index asc), which is what the overview page
    groups on."""
    def ingest(title, slug, category, sort_index):
        payload = {
            "title": title,
            "slug": slug,
            "sort_index": sort_index,
            "sections": [
                {"heading": "S", "anchor_slug": f"{slug}-s", "body_markdown": "b", "cards": []}
            ],
        }
        if category is not None:
            payload["category"] = category
        assert client.post("/api/essaycards/essays/ingest", json=payload).status_code == 200

    ingest("Philo Two", "cat-philo-2", "Philosophy", 2)
    ingest("Art One", "cat-art-1", "Art", 1)
    ingest("Philo One", "cat-philo-1", "Philosophy", 1)
    ingest("Loose", "cat-loose", None, 0)

    rows = client.get("/api/essaycards/essays").json()["rows"]
    seq = [(r["category"], r["sort_index"], r["slug"]) for r in rows
           if r["slug"].startswith("cat-")]
    assert seq == [
        ("Art", 1, "cat-art-1"),
        ("Philosophy", 1, "cat-philo-1"),
        ("Philosophy", 2, "cat-philo-2"),
        (None, 0, "cat-loose"),
    ]


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


# ── Overview knowledge indicators ────────────────────────────────────────────

def test_overview_progress_and_open_counts(client):
    """progress_total = every card; progress_established = review_interval >= 24h
    (regardless of open); open_count = next_due_at <= now() (regardless of
    established)."""
    eid = _mk_essay(client, "prog-essay", 3)

    due = client.get(f"/api/essaycards/flashcards/due?essay_id={eid}").json()["rows"]
    assert len(due) == 3  # all three start new + open

    # `easy` on a never-reviewed card -> interval 1 day -> established, and
    # next_due moves out so it is no longer open.
    client.post(f"/api/essaycards/flashcards/{due[0]['flashcard_id']}/review", json={"grade": "easy"})

    row = _overview_row(client, eid)
    assert row["status"] == "complete"
    assert row["progress_total"] == 3
    assert row["progress_established"] == 1
    assert row["open_count"] == 2
    assert row["oral_score"] is None and row["oral_date"] is None


def test_overview_planned_essay_with_no_cards(client):
    eid = _mk_essay(client, "planned-essay", 0, status="planned")
    row = _overview_row(client, eid)
    assert row["status"] == "planned"
    assert row["progress_total"] == 0
    assert row["progress_established"] == 0
    assert row["open_count"] == 0
    assert row["oral_score"] is None and row["oral_date"] is None


def test_overview_oral_score_requires_every_section_examined(client, db_conn):
    """Fixture essay A has two sections; only 'origins' has examinations, so the
    essay-level oral score/date are null until 'structure' is examined too."""
    row = _overview_row(client, ESSAY_A_ID)
    assert row["oral_score"] is None
    assert row["oral_date"] is None

    with db_conn.cursor() as cur:
        cur.execute(
            """
            insert into essaycards.section_examinations
              (essay_id, section_id, section_version_at, examined_at,
               question, answer_transcript, score)
            values (%s, %s, now(), now() - interval '10 days', 'q', 'a', 5)
            """,
            (ESSAY_A_ID, SECTION_A2_ID),
        )

    row = _overview_row(client, ESSAY_A_ID)
    # latest per section: origins -> se-origins-2 score 4; structure -> score 5.
    assert row["oral_score"] == round((4 + 5) / 2 / 6 * 100)  # 75
    # exam date = the OLDEST of the per-section latest examinations: structure's
    # now() - 10 days (which precedes origins' now() - 2 days).
    age_days = (datetime.now(timezone.utc) - datetime.fromisoformat(row["oral_date"])).days
    assert 9 <= age_days <= 11


# ── GET /essays/{essay_id}/sections/{section_id}/export ─────────────────────

def test_export_section_returns_ingest_shaped_payload(client):
    """The export package is directly postable to POST /essays/ingest: it
    carries the essay-level fields plus a single-element sections list for
    the requested section, with its cards."""
    eid = _mk_essay(client, "export-essay", 2, category="Philosophy", sort_index=3)
    detail = client.get(f"/api/essaycards/essays/{eid}").json()["rows"][0]
    section = detail["sections"][0]

    r = client.get(f"/api/essaycards/essays/{eid}/sections/{section['id']}/export")
    assert r.status_code == 200
    pkg = r.json()

    assert pkg["title"] == "export-essay"
    assert pkg["slug"] == "export-essay"
    assert pkg["category"] == "Philosophy"
    assert pkg["sort_index"] == 3
    assert pkg["status"] == "complete"
    assert pkg["section_id"] == section["id"]

    assert len(pkg["sections"]) == 1
    exported = pkg["sections"][0]
    assert exported["heading"] == section["heading"]
    assert exported["anchor_slug"] == section["anchor_slug"]
    assert exported["body_markdown"] == section["body_markdown"]
    assert {c["id"] for c in exported["cards"]} == {"export-essay-c0", "export-essay-c1"}
    assert {c["q"] for c in exported["cards"]} == {"q0", "q1"}


def test_export_section_essay_not_found(client):
    r = client.get(f"/api/essaycards/essays/{UNKNOWN_ID}/sections/{UNKNOWN_ID}/export")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_export_section_section_not_found(client):
    eid = _mk_essay(client, "export-essay-2", 0)
    r = client.get(f"/api/essaycards/essays/{eid}/sections/{UNKNOWN_ID}/export")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_export_then_reingest_updates_only_that_section(client):
    """Round trip: export a section, edit its body/cards, re-post it through
    the existing whole-essay ingest endpoint (as the frontend does via
    IngestView) — only that section changes; the essay's other section and
    metadata are untouched."""
    payload = {
        "title": "roundtrip-essay", "slug": "roundtrip-essay",
        "category": "Art", "sort_index": 7,
        "sections": [
            {"heading": "One", "anchor_slug": "rt-one", "body_markdown": "body one",
             "cards": [{"id": "rt-c1", "q": "q1", "a": "a1"}]},
            {"heading": "Two", "anchor_slug": "rt-two", "body_markdown": "body two", "cards": []},
        ],
    }
    r = client.post("/api/essaycards/essays/ingest", json=payload)
    assert r.status_code == 200, r.text
    eid = r.json()["essay_id"]

    detail = client.get(f"/api/essaycards/essays/{eid}").json()["rows"][0]
    section_one = next(s for s in detail["sections"] if s["anchor_slug"] == "rt-one")

    pkg = client.get(f"/api/essaycards/essays/{eid}/sections/{section_one['id']}/export").json()
    pkg["sections"][0]["body_markdown"] = "REVISED body one"
    pkg["sections"][0]["cards"][0]["a"] = "REVISED a1"

    r2 = client.post("/api/essaycards/essays/ingest", json=pkg)
    assert r2.status_code == 200, r2.text
    assert r2.json()["sections_updated"] == 1
    assert r2.json()["cards_updated"] == 1

    detail2 = client.get(f"/api/essaycards/essays/{eid}").json()["rows"][0]
    assert detail2["category"] == "Art"
    assert detail2["sort_index"] == 7
    assert len(detail2["sections"]) == 2  # "rt-two" untouched, not dropped

    updated_one = next(s for s in detail2["sections"] if s["anchor_slug"] == "rt-one")
    assert updated_one["body_markdown"] == "REVISED body one"
    untouched_two = next(s for s in detail2["sections"] if s["anchor_slug"] == "rt-two")
    assert untouched_two["body_markdown"] == "body two"
