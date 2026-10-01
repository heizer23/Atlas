"""
EssayCards — pytest tests for GET /essays and GET /essays/{essay_id}.

Traceability: each function name maps to a scenario in
Sprint01_Core/10_test_spec.md and Sprint12_FSRSAndUXOverhaul/10_test_spec.md.
Fixture IDs are defined in tests/fixtures.sql.
"""

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
    for field in (
        "id", "title", "slug", "category", "sort_index", "status",
        "progress_total", "progress_established", "open_count",
        "cards_seen_count", "cards_future_safe_count",
        "milestone_all_cards_seen", "milestone_all_cards_future_safe",
        "milestone_guided_passed", "milestone_unguided_passed",
        "guided_passed_at", "unguided_passed_at", "learning_level",
    ):
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


def test_overview_planned_essay_with_no_cards(client):
    eid = _mk_essay(client, "planned-essay", 0, status="planned")
    row = _overview_row(client, eid)
    assert row["status"] == "planned"
    assert row["progress_total"] == 0
    assert row["progress_established"] == 0
    assert row["open_count"] == 0
    assert row["milestone_all_cards_seen"] is False
    assert row["milestone_all_cards_future_safe"] is False
    assert row["learning_level"] == 0


# ── Learning progress (Sprint12_FSRSAndUXOverhaul) ──────────────────────────
#
# PASS_SCORE_THRESHOLD = 3 (score >= 3 counts as "passed" for milestones 3/4).

def _review(client, flashcard_id, grade="easy"):
    r = client.post(f"/api/essaycards/flashcards/{flashcard_id}/review", json={"grade": grade})
    assert r.status_code == 200, r.text
    return r.json()


def _import_exam(client, essay_slug, section_version, section_anchor_slug, score, exam_type):
    r = client.post("/api/essaycards/examinations/import", json={
        "results": [{
            "essay_slug": essay_slug,
            "section_anchor_slug": section_anchor_slug,
            "section_version": section_version,
            "examined_at": "2026-08-28T14:30:00Z",
            "question": "Q", "answer_transcript": "A",
            "score": score, "exam_type": exam_type,
        }],
    })
    assert r.status_code == 200, r.text


def test_essay_with_zero_cards_has_card_milestones_false_and_level_bounded_by_exam_milestones(client):
    """Scenario: an essay with no cards never satisfies milestones 1/2,
    regardless of any exam state — fixture essay-i-zero-cards has two
    sections, zero cards, and both sections' latest guided examination
    scoring >= 3 (milestone_guided_passed true), but the card milestones must
    stay false and must not contribute to learning_level."""
    essay_id = "ea000009-0000-0000-0000-000000000009"
    row = _overview_row(client, essay_id)
    assert row["progress_total"] == 0
    assert row["milestone_all_cards_seen"] is False
    assert row["milestone_all_cards_future_safe"] is False
    assert row["milestone_guided_passed"] is True
    assert row["milestone_unguided_passed"] is False
    assert row["learning_level"] == 1  # exactly one true milestone (guided)


def test_essay_all_cards_seen_and_future_safe_satisfies_card_milestones(client):
    """Scenario: all cards seen and future-safe satisfies both card
    milestones — cards_seen_count/cards_future_safe_count both equal
    progress_total."""
    eid = _mk_essay(client, "level-cards-essay", 2)
    due = client.get(f"/api/essaycards/flashcards/due?essay_id={eid}").json()["rows"]
    for card in due:
        _review(client, card["flashcard_id"], "easy")  # pushes next_due_at well past +24h

    row = _overview_row(client, eid)
    assert row["milestone_all_cards_seen"] is True
    assert row["milestone_all_cards_future_safe"] is True
    assert row["cards_seen_count"] == row["progress_total"] == 2
    assert row["cards_future_safe_count"] == row["progress_total"]


def test_essay_one_unseen_card_fails_cards_seen_milestone(client):
    """Scenario: one unseen card among many keeps milestone_all_cards_seen
    false and cards_seen_count one less than progress_total."""
    eid = _mk_essay(client, "partial-seen-essay", 3)
    due = client.get(f"/api/essaycards/flashcards/due?essay_id={eid}").json()["rows"]
    for card in due[:2]:
        _review(client, card["flashcard_id"], "easy")

    row = _overview_row(client, eid)
    assert row["milestone_all_cards_seen"] is False
    assert row["cards_seen_count"] == row["progress_total"] - 1 == 2


def test_essay_guided_passed_requires_every_section_at_or_above_threshold(client):
    """Scenario: one section below the score-3 threshold keeps
    guided_passed false even though most sections pass — fixture
    essay-j-mixed-exam-types has section 1's guided exam at score 4 (pass)
    and section 2's at score 2 (fail)."""
    row = _overview_row(client, "ea00000a-0000-0000-0000-00000000000a")
    assert row["milestone_guided_passed"] is False
    assert row["guided_passed_at"] is None


def test_essay_guided_and_unguided_milestones_are_independent(client):
    """Scenario: guided_passed can be false while unguided_passed is true
    for the same essay — fixture essay-j-mixed-exam-types has every section's
    unguided exam passing (3, 5) while one section's guided exam fails."""
    row = _overview_row(client, "ea00000a-0000-0000-0000-00000000000a")
    assert row["milestone_guided_passed"] is False
    assert row["milestone_unguided_passed"] is True
    assert row["unguided_passed_at"] is not None


def test_essay_learning_level_sums_four_independent_milestones_in_any_order(client):
    """Scenario: learning_level equals the count of true milestones
    regardless of which ones are true — constructs an essay hitting level 4
    (every milestone true) via cards + both exam types, not in 1-2-3-4
    order (cards are satisfied first, then unguided, then guided)."""
    eid, slug = _mk_essay_returning_slug(client, "level-4-essay", 2)
    due = client.get(f"/api/essaycards/flashcards/due?essay_id={eid}").json()["rows"]
    for card in due:
        _review(client, card["flashcard_id"], "easy")

    detail = client.get(f"/api/essaycards/essays/{eid}").json()["rows"][0]
    section = detail["sections"][0]
    section_version = section["updated_at"]

    # Unguided passed first (out of the natural 1-2-3-4 order).
    _import_exam(client, slug, section_version, section["anchor_slug"], 5, "unguided")
    row = _overview_row(client, eid)
    assert row["learning_level"] == 3  # seen + future-safe + unguided

    _import_exam(client, slug, section_version, section["anchor_slug"], 4, "guided")
    row = _overview_row(client, eid)
    assert row["learning_level"] == 4
    assert all(row[k] for k in (
        "milestone_all_cards_seen", "milestone_all_cards_future_safe",
        "milestone_guided_passed", "milestone_unguided_passed",
    ))


def _mk_essay_returning_slug(client, slug, n_cards):
    eid = _mk_essay(client, slug, n_cards)
    return eid, slug


def test_get_essay_detail_carries_same_learning_progress_fields_as_list(client):
    """Scenario: GET /essays/{id} returns the same nine learning-progress
    fields, computed identically, as the corresponding GET /essays row."""
    essay_id = "ea00000a-0000-0000-0000-00000000000a"  # essay-j-mixed-exam-types
    list_row = _overview_row(client, essay_id)
    detail_row = client.get(f"/api/essaycards/essays/{essay_id}").json()["rows"][0]

    for key in (
        "cards_seen_count", "cards_future_safe_count",
        "milestone_all_cards_seen", "milestone_all_cards_future_safe",
        "milestone_guided_passed", "milestone_unguided_passed",
        "guided_passed_at", "unguided_passed_at", "learning_level",
    ):
        assert detail_row[key] == list_row[key], key


def test_essay_status_unaffected_by_learning_progress_changes(client):
    """Scenario: essay status is unaffected by this sprint — a planned essay
    still reads status='planned', computed and gated exactly as before."""
    eid = _mk_essay(client, "still-planned-essay", 0, status="planned")
    row = _overview_row(client, eid)
    assert row["status"] == "planned"
    detail = client.get(f"/api/essaycards/essays/{eid}").json()["rows"][0]
    assert detail["status"] == "planned"


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


# ── Nuggets (Sprint09_Nuggets) ─────────────────────────────────────────────────
#
# Fixture essay F ('essay-f-nuggets', ea000006) has main_spine_markdown
# referencing fix-nugget-adequacy (main-spine-only, never in a section) and
# section F1 (ec000007) referencing fix-nugget-cogito + fix-nugget-MixedCase.
# Fixture flashcard fc-nugget-linked (fc000021) in section F1 is linked to
# fix-nugget-cogito; fc-nugget-unlinked (fc000022) in the same section is not.

ESSAY_F_ID = "ea000006-0000-0000-0000-000000000006"
SECTION_F1_ID = "ec000007-0000-0000-0000-000000000007"
NUGGET_COGITO_ID = "ee000001-0000-0000-0000-000000000001"
NUGGET_ADEQUACY_ID = "ee000003-0000-0000-0000-000000000003"
FC_NUGGET_LINKED_ID = "fc000021-0000-0000-0000-000000000021"
FC_NUGGET_UNLINKED_ID = "fc000022-0000-0000-0000-000000000022"


def test_essay_detail_sections_carry_referenced_nuggets(client):
    """Scenario: Essay detail sections carry their referenced nuggets."""
    detail = client.get(f"/api/essaycards/essays/{ESSAY_F_ID}").json()["rows"][0]
    section = next(s for s in detail["sections"] if s["id"] == SECTION_F1_ID)
    assert {"nugget_key": "fix-nugget-cogito", "title": "Cogito"} in section["nuggets"]


def test_questions_rows_carry_section_nuggets(client):
    """Scenario: Question overview rows carry their section's referenced nuggets."""
    rows = client.get(f"/api/essaycards/essays/{ESSAY_F_ID}/questions").json()["rows"]
    f1_rows = [r for r in rows if r["section_id"] == SECTION_F1_ID]
    assert f1_rows
    for row in f1_rows:
        assert {"nugget_key": "fix-nugget-cogito", "title": "Cogito"} in row["section_nuggets"]


def test_questions_rows_carry_nugget_id(client):
    """Scenario: Question overview rows carry each card's current nugget_id."""
    rows = client.get(f"/api/essaycards/essays/{ESSAY_F_ID}/questions").json()["rows"]
    linked = next(r for r in rows if r["id"] == FC_NUGGET_LINKED_ID)
    unlinked = next(r for r in rows if r["id"] == FC_NUGGET_UNLINKED_ID)
    assert linked["nugget_id"] == NUGGET_COGITO_ID
    assert unlinked["nugget_id"] is None


def test_export_section_includes_main_spine_and_focus_section_nuggets(client):
    """Scenario: Section export includes the main spine and focus-section nugget context."""
    r = client.get(f"/api/essaycards/essays/{ESSAY_F_ID}/sections/{SECTION_F1_ID}/export")
    assert r.status_code == 200
    pkg = r.json()

    assert pkg["main_spine_markdown"]
    assert "[[nugget:fix-nugget-adequacy]]" in pkg["main_spine_markdown"]

    cogito = next(n for n in pkg["focus_section_nuggets"] if n["nugget_key"] == "fix-nugget-cogito")
    assert cogito["title"] == "Cogito"
    assert cogito["body_markdown"]


def test_essay_detail_main_spine_nuggets_resolves_main_spine_only_reference(client):
    """Scenario: Essay detail's main_spine_nuggets resolves a main-spine-only reference."""
    detail = client.get(f"/api/essaycards/essays/{ESSAY_F_ID}").json()["rows"][0]
    assert {"nugget_key": "fix-nugget-adequacy", "title": "Adequacy"} in detail["main_spine_nuggets"]
    # Not present via any section's own nuggets field.
    for section in detail["sections"]:
        assert all(n["nugget_key"] != "fix-nugget-adequacy" for n in section["nuggets"])


def test_essay_export_and_section_export_carry_main_spine_nuggets(client):
    """Scenario: Essay export and section export carry main_spine_nuggets."""
    export = client.get(f"/api/essaycards/essays/{ESSAY_F_ID}/export").json()
    assert {"nugget_key": "fix-nugget-adequacy", "title": "Adequacy"} in export["main_spine_nuggets"]

    section_export = client.get(
        f"/api/essaycards/essays/{ESSAY_F_ID}/sections/{SECTION_F1_ID}/export"
    ).json()
    assert {"nugget_key": "fix-nugget-adequacy", "title": "Adequacy"} in section_export["main_spine_nuggets"]
