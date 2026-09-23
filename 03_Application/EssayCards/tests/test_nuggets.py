"""
EssayCards — pytest tests for the nuggets router (Sprint09_Nuggets):
  GET  /api/essaycards/nuggets
  GET  /api/essaycards/nuggets/{id}
  POST /api/essaycards/nuggets/upsert
  GET  /api/essaycards/nuggets/{id}/flashcards
  GET  /api/essaycards/nuggets/{id}/sections
  GET  /api/essaycards/nuggets/authoring-package
  GET  /api/essaycards/nuggets/{id}/generate-flashcards-package

Traceability: each function name maps to a scenario in
Sprint09_Nuggets/10_test_spec.md. Fixture IDs are defined in tests/fixtures.sql.
"""

# ── Fixture IDs (stable references to tests/fixtures.sql) ────────────────────
NUGGET_COGITO = "ee000001-0000-0000-0000-000000000001"
NUGGET_WAX = "ee000002-0000-0000-0000-000000000002"
NUGGET_ADEQUACY = "ee000003-0000-0000-0000-000000000003"
NUGGET_MIXEDCASE = "ee000004-0000-0000-0000-000000000004"

ESSAY_F = "ea000006-0000-0000-0000-000000000006"
ESSAY_G = "ea000007-0000-0000-0000-000000000007"
SECTION_F1 = "ec000007-0000-0000-0000-000000000007"
SECTION_G1 = "ec000008-0000-0000-0000-000000000008"

FC_NUGGET_LINKED = "fc000021-0000-0000-0000-000000000021"

UNKNOWN_ID = "00000000-0000-0000-0000-000000000000"

NUGGETS_URL = "/api/essaycards/nuggets"


# ── GET /nuggets ──────────────────────────────────────────────────────────────

def test_list_nuggets_returns_dataset_ordered_by_title(client):
    r = client.get(NUGGETS_URL)
    assert r.status_code == 200
    body = r.json()
    assert body["meta"]["object_type"] == "nugget"

    titles = [row["title"] for row in body["rows"]]
    assert titles == sorted(titles)

    row = next(row for row in body["rows"] if row["id"] == NUGGET_COGITO)
    for field in ("id", "nugget_key", "title", "created_at", "updated_at"):
        assert field in row
    assert "body_markdown" not in row


def test_list_nuggets_empty_is_valid(client, db_conn):
    with db_conn.cursor() as cur:
        cur.execute("truncate essaycards.nuggets cascade")

    r = client.get(NUGGETS_URL)
    assert r.status_code == 200
    body = r.json()
    assert body["rows"] == []
    assert body["meta"]["total"] == 0


# ── GET /nuggets/{id} ─────────────────────────────────────────────────────────

def test_nugget_detail_includes_body_markdown(client):
    r = client.get(f"{NUGGETS_URL}/{NUGGET_COGITO}")
    assert r.status_code == 200
    row = r.json()["rows"][0]
    assert row["nugget_key"] == "fix-nugget-cogito"
    assert row["title"] == "Cogito"
    assert "body_markdown" in row and row["body_markdown"]


def test_nugget_detail_not_found(client):
    r = client.get(f"{NUGGETS_URL}/{UNKNOWN_ID}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


# ── POST /nuggets/upsert ──────────────────────────────────────────────────────

def test_nugget_upsert_creates_then_updates_by_key(client):
    r1 = client.post(NUGGETS_URL + "/upsert", json={
        "nugget_key": "new-concept", "title": "Draft Title", "body_markdown": "draft body",
    })
    assert r1.status_code == 200, r1.text
    body1 = r1.json()
    assert body1["created"] is True
    new_id = body1["id"]

    r2 = client.post(NUGGETS_URL + "/upsert", json={
        "nugget_key": "new-concept", "title": "Final Title", "body_markdown": "final body",
    })
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2["created"] is False
    assert body2["id"] == new_id
    assert body2["nugget_key"] == "new-concept"

    detail = client.get(f"{NUGGETS_URL}/{new_id}").json()["rows"][0]
    assert detail["title"] == "Final Title"
    assert detail["body_markdown"] == "final body"


def test_nugget_upsert_rejects_missing_key_or_title(client, db_conn):
    r1 = client.post(NUGGETS_URL + "/upsert", json={"title": "No key"})
    assert r1.status_code == 400
    assert r1.json()["error"]["code"] == "VALIDATION_ERROR"

    r2 = client.post(NUGGETS_URL + "/upsert", json={"nugget_key": "blank-title", "title": ""})
    assert r2.status_code == 400
    assert r2.json()["error"]["code"] == "VALIDATION_ERROR"

    with db_conn.cursor() as cur:
        cur.execute("select count(*) as n from essaycards.nuggets where nugget_key = 'blank-title'")
        assert cur.fetchone()["n"] == 0


def test_nugget_upsert_rejects_key_violating_slug_pattern(client, db_conn):
    r = client.post(NUGGETS_URL + "/upsert", json={
        "nugget_key": "not a valid key!", "title": "Bad Key",
    })
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"

    with db_conn.cursor() as cur:
        cur.execute("select count(*) as n from essaycards.nuggets where title = 'Bad Key'")
        assert cur.fetchone()["n"] == 0


# ── GET /nuggets/{id}/flashcards ──────────────────────────────────────────────

def test_nugget_flashcards_lists_linked_cards_no_scheduling_fields(client):
    r = client.get(f"{NUGGETS_URL}/{NUGGET_COGITO}/flashcards")
    assert r.status_code == 200
    body = r.json()
    row = next(row for row in body["rows"] if row["id"] == FC_NUGGET_LINKED)

    for field in ("id", "card_key", "question", "answer", "level", "essay_id", "section_id"):
        assert field in row
    for field in ("next_due_at", "is_new", "is_recent", "scheduled_interval_seconds"):
        assert field not in row


def test_nugget_flashcards_not_found(client):
    r = client.get(f"{NUGGETS_URL}/{UNKNOWN_ID}/flashcards")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


# ── GET /nuggets/{id}/sections ─────────────────────────────────────────────────

def test_nugget_sections_lists_multiple_referencing_sections(client):
    r = client.get(f"{NUGGETS_URL}/{NUGGET_COGITO}/sections")
    assert r.status_code == 200
    body = r.json()
    assert body["meta"]["total"] == 2

    section_ids = {row["section_id"] for row in body["rows"]}
    assert section_ids == {SECTION_F1, SECTION_G1}
    essay_ids = {row["essay_id"] for row in body["rows"]}
    assert essay_ids == {ESSAY_F, ESSAY_G}
    for row in body["rows"]:
        for field in ("section_id", "anchor_slug", "heading", "essay_id", "essay_title", "essay_slug"):
            assert field in row


def test_nugget_sections_not_found(client):
    r = client.get(f"{NUGGETS_URL}/{UNKNOWN_ID}/sections")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


# ── GET /nuggets/authoring-package ────────────────────────────────────────────

def test_authoring_package_existing_nugget_includes_connected_nuggets(client):
    r = client.get(
        f"{NUGGETS_URL}/authoring-package",
        params={"essay_id": ESSAY_F, "section_id": SECTION_F1, "nugget_id": NUGGET_WAX},
    )
    assert r.status_code == 200
    body = r.json()

    assert body["nugget"]["nugget_key"] == "fix-nugget-wax"
    assert body["nugget"]["title"] == "Wax and the Intellect"
    assert body["nugget"]["body_markdown"]
    assert {"nugget_key": "fix-nugget-cogito", "title": "Cogito"} in body["connected_nuggets"]
    assert body["essay"]["main_spine_markdown"]
    assert body["section"]["body_markdown"]


def test_authoring_package_new_nugget_has_null_nugget_and_empty_connected(client):
    r = client.get(
        f"{NUGGETS_URL}/authoring-package",
        params={"essay_id": ESSAY_F, "section_id": SECTION_F1},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["nugget"] is None
    assert body["connected_nuggets"] == []


def test_authoring_package_unresolvable_context_returns_404(client):
    r1 = client.get(
        f"{NUGGETS_URL}/authoring-package",
        params={"essay_id": UNKNOWN_ID, "section_id": SECTION_F1},
    )
    assert r1.status_code == 404
    assert r1.json()["error"]["code"] == "NOT_FOUND"

    r2 = client.get(
        f"{NUGGETS_URL}/authoring-package",
        params={"essay_id": ESSAY_F, "section_id": UNKNOWN_ID},
    )
    assert r2.status_code == 404
    assert r2.json()["error"]["code"] == "NOT_FOUND"

    r3 = client.get(
        f"{NUGGETS_URL}/authoring-package",
        params={"essay_id": ESSAY_F, "section_id": SECTION_F1, "nugget_id": UNKNOWN_ID},
    )
    assert r3.status_code == 404
    assert r3.json()["error"]["code"] == "NOT_FOUND"


# ── GET /nuggets/{id}/generate-flashcards-package ────────────────────────────

def test_generate_flashcards_package_includes_existing_flashcards(client):
    r = client.get(
        f"{NUGGETS_URL}/{NUGGET_COGITO}/generate-flashcards-package",
        params={"essay_id": ESSAY_F, "section_id": SECTION_F1},
    )
    assert r.status_code == 200
    body = r.json()

    assert body["nugget"]["nugget_key"] == "fix-nugget-cogito"
    card_ids = {c["id"] for c in body["existing_flashcards"]}
    assert FC_NUGGET_LINKED in card_ids
    assert body["context"]["essay_slug"] == "essay-f-nuggets"
    assert body["context"]["section_id"] == SECTION_F1


def test_generate_flashcards_package_unresolvable_context_returns_404(client):
    r1 = client.get(
        f"{NUGGETS_URL}/{UNKNOWN_ID}/generate-flashcards-package",
        params={"essay_id": ESSAY_F, "section_id": SECTION_F1},
    )
    assert r1.status_code == 404
    assert r1.json()["error"]["code"] == "NOT_FOUND"

    r2 = client.get(
        f"{NUGGETS_URL}/{NUGGET_COGITO}/generate-flashcards-package",
        params={"essay_id": UNKNOWN_ID, "section_id": SECTION_F1},
    )
    assert r2.status_code == 404
    assert r2.json()["error"]["code"] == "NOT_FOUND"
