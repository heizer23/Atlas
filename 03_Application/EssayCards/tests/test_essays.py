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
#
# The export carries EVERY section of the essay (not just the requested one),
# in current order, because POST /essays/ingest assigns order_index from a
# submitted section's position in the "sections" array — a payload with only
# the target section would always land it at order_index 0, silently
# reordering the essay for any section past the first. See export_section's
# docstring in backend/routers/essays.py.

def _mk_essay_sections(client, slug, headings, **extra):
    """Ingest an essay with one cardless section per heading, in order.
    Returns (essay_id, [section_id, ...]) in that same order."""
    payload = {
        "title": slug, "slug": slug,
        "sections": [
            {"heading": h, "anchor_slug": f"{slug}-{h.lower()}", "body_markdown": f"body {h}", "cards": []}
            for h in headings
        ],
        **extra,
    }
    r = client.post("/api/essaycards/essays/ingest", json=payload)
    assert r.status_code == 200, r.text
    eid = r.json()["essay_id"]
    detail = client.get(f"/api/essaycards/essays/{eid}").json()["rows"][0]
    by_heading = {s["heading"]: s["id"] for s in detail["sections"]}
    return eid, [by_heading[h] for h in headings]


def test_export_section_returns_ingest_shaped_payload(client):
    """The export package is directly postable to POST /essays/ingest: it
    carries the essay-level fields plus every section (each with its cards),
    in order, and `focus_section_id` naming the requested one."""
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
    assert pkg["focus_section_id"] == section["id"]

    assert len(pkg["sections"]) == 1  # essay-essay only has one section
    exported = pkg["sections"][0]
    assert exported["section_id"] == section["id"]
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


def test_export_includes_every_section_in_order(client):
    eid, section_ids = _mk_essay_sections(client, "multi-sec", ["A", "B", "C"])

    r = client.get(f"/api/essaycards/essays/{eid}/sections/{section_ids[1]}/export")
    assert r.status_code == 200
    pkg = r.json()

    assert pkg["focus_section_id"] == section_ids[1]
    assert [s["anchor_slug"] for s in pkg["sections"]] == ["multi-sec-a", "multi-sec-b", "multi-sec-c"]
    assert [s["section_id"] for s in pkg["sections"]] == section_ids


def test_export_then_reingest_updates_only_that_section(client):
    """Round trip: export, edit the target section's body/cards, re-post the
    WHOLE returned payload through the existing whole-essay ingest endpoint
    (as the frontend does via IngestView) — only that section changes; the
    essay's other section and metadata are untouched."""
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
    target = next(s for s in pkg["sections"] if s["anchor_slug"] == "rt-one")
    target["body_markdown"] = "REVISED body one"
    target["cards"][0]["a"] = "REVISED a1"

    r2 = client.post("/api/essaycards/essays/ingest", json=pkg)
    assert r2.status_code == 200, r2.text
    assert r2.json()["sections_updated"] == 2  # both entries in the payload upsert, only one's content changed
    assert r2.json()["cards_updated"] == 1

    detail2 = client.get(f"/api/essaycards/essays/{eid}").json()["rows"][0]
    assert detail2["category"] == "Art"
    assert detail2["sort_index"] == 7
    assert len(detail2["sections"]) == 2

    updated_one = next(s for s in detail2["sections"] if s["anchor_slug"] == "rt-one")
    assert updated_one["body_markdown"] == "REVISED body one"
    untouched_two = next(s for s in detail2["sections"] if s["anchor_slug"] == "rt-two")
    assert untouched_two["body_markdown"] == "body two"


def test_export_then_reingest_preserves_order_for_non_first_section(client):
    """Regression test for the order_index bug: editing the SECOND (or later)
    section via export/reimport must not move it to the front. Before the
    export package carried every section (not just the target), reimporting
    a single-section payload always assigned order_index 0 — the array
    position within that payload — silently promoting any non-first section
    to first."""
    eid, section_ids = _mk_essay_sections(client, "ord-essay", ["A", "B", "C"])

    pkg = client.get(f"/api/essaycards/essays/{eid}/sections/{section_ids[1]}/export").json()
    target = next(s for s in pkg["sections"] if s["section_id"] == section_ids[1])
    target["body_markdown"] = "REVISED B"

    r = client.post("/api/essaycards/essays/ingest", json=pkg)
    assert r.status_code == 200, r.text

    detail = client.get(f"/api/essaycards/essays/{eid}").json()["rows"][0]
    ordered = sorted(detail["sections"], key=lambda s: s["order_index"])
    assert [s["anchor_slug"] for s in ordered] == ["ord-essay-a", "ord-essay-b", "ord-essay-c"]
    assert next(s for s in ordered if s["anchor_slug"] == "ord-essay-b")["body_markdown"] == "REVISED B"


def test_insert_flow_splices_new_section_at_correct_position(client):
    """Simulates the frontend's "Insert section after" flow: export the
    target section's full package, splice a new section object into the
    array right after the target (as the frontend does client-side), reimport
    the whole array. The new section lands between its intended neighbors and
    every existing section keeps its content and relative order."""
    eid, section_ids = _mk_essay_sections(client, "ins-essay", ["A", "B", "C"])

    pkg = client.get(f"/api/essaycards/essays/{eid}/sections/{section_ids[0]}/export").json()
    idx = next(i for i, s in enumerate(pkg["sections"]) if s["section_id"] == section_ids[0])
    pkg["sections"].insert(idx + 1, {
        "heading": "New Middle", "anchor_slug": "ins-essay-new",
        "body_markdown": "brand new section", "cards": [{"id": "ins-new-c1", "q": "q", "a": "a"}],
    })

    r = client.post("/api/essaycards/essays/ingest", json=pkg)
    assert r.status_code == 200, r.text
    assert r.json()["sections_created"] == 1
    assert r.json()["sections_updated"] == 3

    detail = client.get(f"/api/essaycards/essays/{eid}").json()["rows"][0]
    ordered = sorted(detail["sections"], key=lambda s: s["order_index"])
    assert [s["anchor_slug"] for s in ordered] == [
        "ins-essay-a", "ins-essay-new", "ins-essay-b", "ins-essay-c",
    ]
    new_section = next(s for s in ordered if s["anchor_slug"] == "ins-essay-new")
    assert new_section["body_markdown"] == "brand new section"
