"""
StoryReader — HTTP-level tests for the stories/versions/annotations/export
API. Uses the `client` fixture from conftest.py (Starlette TestClient, no
real server needed). Traceability: each function name maps to a scenario in
Sprint01_Core/10_test_spec.md.
"""

# Fixture ids (tests/fixtures.sql)
LIGHTHOUSE_ID = "aa000001-0000-0000-0000-000000000001"
TIDEPOOL_ID   = "aa000002-0000-0000-0000-000000000002"

ANN_V1_OLD    = "ac000001-0000-0000-0000-000000000001"
ANN_V2_FIRST  = "ac000002-0000-0000-0000-000000000002"
ANN_V2_SECOND = "ac000003-0000-0000-0000-000000000003"

BASE = "/api/storyreader"


def _get_version_content(client, story_id, version):
    r = client.get(f"{BASE}/stories/{story_id}/versions/{version}")
    assert r.status_code == 200
    return r.json()["rows"][0]


# ── Story list ──────────────────────────────────────────────────────────────

def test_story_list_empty_state(client, db_conn):
    with db_conn.cursor() as cur:
        cur.execute("delete from storyreader.stories")

    r = client.get(f"{BASE}/stories")
    assert r.status_code == 200
    body = r.json()
    assert body["rows"] == []


def test_story_list_marked_passage_count_reflects_latest_version_only(client):
    r = client.get(f"{BASE}/stories")
    assert r.status_code == 200
    rows = {row["id"]: row for row in r.json()["rows"]}

    lighthouse = rows[LIGHTHOUSE_ID]
    assert lighthouse["latest_version"] == 2
    assert lighthouse["marked_passage_count"] == 2


# ── Story detail ────────────────────────────────────────────────────────────

def test_story_detail_version_list_for_switcher(client):
    r = client.get(f"{BASE}/stories/{LIGHTHOUSE_ID}")
    assert r.status_code == 200
    row = r.json()["rows"][0]
    assert row["versions"] == [1, 2]


def test_story_detail_unknown_story(client):
    r = client.get(f"{BASE}/stories/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


# ── Version content ─────────────────────────────────────────────────────────

def test_version_content_default_resolves_to_latest(client):
    row = _get_version_content(client, LIGHTHOUSE_ID, "latest")
    assert row["version"] == 2
    assert row["paragraphs"][0]["text"].startswith("First paragraph")


def test_version_content_explicit_old_version_remains_readable(client):
    row = _get_version_content(client, LIGHTHOUSE_ID, 1)
    assert row["version"] == 1
    assert row["paragraphs"][0]["text"].startswith("Old paragraph")


def test_version_content_unknown_version_number(client):
    r = client.get(f"{BASE}/stories/{LIGHTHOUSE_ID}/versions/7")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_version_content_malformed_version_segment(client):
    r = client.get(f"{BASE}/stories/{LIGHTHOUSE_ID}/versions/not-a-number")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


# ── Annotations list ─────────────────────────────────────────────────────────

def test_annotations_list_reading_order(client, db_conn):
    # Layer a second paragraph-1 annotation on top of the base fixtures so
    # this version has three annotations: paragraph 0, and two in paragraph 1
    # at different char offsets — per the scenario's Given.
    with db_conn.cursor() as cur:
        cur.execute(
            """
            insert into storyreader.annotations
                (id, story_id, version, paragraph_index, char_start, char_end, selected_text, reaction)
            values
                ('ac000009-0000-0000-0000-000000000009', %s, 2, 1, 7, 16, 'paragraph', 'neutral')
            """,
            (LIGHTHOUSE_ID,),
        )

    r = client.get(f"{BASE}/stories/{LIGHTHOUSE_ID}/versions/2/annotations")
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert len(rows) == 3
    keys = [(row["paragraph_index"], row["char_start"]) for row in rows]
    assert keys == sorted(keys)
    assert keys[0][0] == 0
    assert keys[1][0] == 1 and keys[2][0] == 1
    assert keys[1][1] < keys[2][1]


def test_annotations_list_no_implicit_latest(client):
    r = client.get(f"{BASE}/stories/{LIGHTHOUSE_ID}/versions/latest/annotations")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


# ── Create annotation ─────────────────────────────────────────────────────────

def test_create_annotation_new_span(client):
    content = _get_version_content(client, LIGHTHOUSE_ID, 2)
    para1_text = content["paragraphs"][1]["text"]
    # paragraph 1 already carries fix-ann-v2-second at [0:6) — pick a
    # disjoint span further along the same paragraph.
    start, end = 20, 30
    selected = para1_text[start:end]

    r = client.post(f"{BASE}/annotations", json={
        "story_id": LIGHTHOUSE_ID,
        "version": 2,
        "paragraph_index": 1,
        "char_start": start,
        "char_end": end,
        "selected_text": selected,
        "context_before": para1_text[:start],
        "context_after": para1_text[end:end + 50],
        "reaction": "positive",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["reaction"] == "positive"
    assert body["selected_text"] == selected
    assert body["id"]


def test_create_annotation_reaction_changed_at_same_exact_span(client):
    r = client.post(f"{BASE}/annotations", json={
        "story_id": LIGHTHOUSE_ID,
        "version": 2,
        "paragraph_index": 0,
        "char_start": 0,
        "char_end": 5,
        "selected_text": "First",
        "context_before": "",
        "context_after": "",
        "reaction": "unclear",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == ANN_V2_FIRST
    assert body["reaction"] == "unclear"
    assert body["created_at"] is not None
    assert body["updated_at"] is not None


def test_create_annotation_selected_text_must_match_true_substring(client):
    r = client.post(f"{BASE}/annotations", json={
        "story_id": LIGHTHOUSE_ID,
        "version": 2,
        "paragraph_index": 0,
        "char_start": 0,
        "char_end": 5,
        "selected_text": "Wrong",
        "context_before": "",
        "context_after": "",
        "reaction": "positive",
    })
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_annotation_invalid_reaction_rejected(client):
    r = client.post(f"{BASE}/annotations", json={
        "story_id": LIGHTHOUSE_ID,
        "version": 2,
        "paragraph_index": 0,
        "char_start": 10,
        "char_end": 15,
        "selected_text": "graph",
        "context_before": "",
        "context_after": "",
        "reaction": "meh",
    })
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_annotation_char_end_not_after_char_start(client):
    r = client.post(f"{BASE}/annotations", json={
        "story_id": LIGHTHOUSE_ID,
        "version": 2,
        "paragraph_index": 0,
        "char_start": 5,
        "char_end": 5,
        "selected_text": "",
        "context_before": "",
        "context_after": "",
        "reaction": "positive",
    })
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_annotation_unknown_story_or_version(client):
    r = client.post(f"{BASE}/annotations", json={
        "story_id": "00000000-0000-0000-0000-000000000000",
        "version": 1,
        "paragraph_index": 0,
        "char_start": 0,
        "char_end": 3,
        "selected_text": "abc",
        "context_before": "",
        "context_after": "",
        "reaction": "positive",
    })
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


# ── Delete annotation ─────────────────────────────────────────────────────────

def test_delete_annotation_toggle_off_removes_the_row(client):
    r = client.delete(f"{BASE}/annotations/{ANN_V2_SECOND}")
    assert r.status_code == 204

    r2 = client.get(f"{BASE}/stories/{LIGHTHOUSE_ID}/versions/2/annotations")
    ids = [row["id"] for row in r2.json()["rows"]]
    assert ANN_V2_SECOND not in ids


def test_delete_annotation_unknown_id(client):
    r = client.delete(f"{BASE}/annotations/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


# ── Export ──────────────────────────────────────────────────────────────────

def test_export_self_contained_json_for_codex(client):
    r = client.get(f"{BASE}/stories/{LIGHTHOUSE_ID}/versions/2/annotations/export")
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == "lighthouse"
    assert body["version"] == 2
    assert body["annotation_count"] == 2
    assert len(body["annotations"]) == 2
    for ann in body["annotations"]:
        assert ann["reaction"] in ("positive", "negative", "neutral", "unclear")
        assert "id" not in ann
        assert "story_id" not in ann


def test_export_empty_version_is_valid_not_an_error(client):
    r = client.get(f"{BASE}/stories/{LIGHTHOUSE_ID}/versions/1/annotations/export")
    assert r.status_code == 200
    body = r.json()
    # fix-ann-v1-old exists on version 1 — use tidepool's un-annotated absence
    # instead is unnecessary; the scenario just requires a valid zero case, so
    # exercise it directly against a version with no annotations at all.
    assert body["version"] == 1


def test_export_empty_version_zero_annotations(client, db_conn):
    with db_conn.cursor() as cur:
        cur.execute("delete from storyreader.annotations where story_id = %s and version = 1", (LIGHTHOUSE_ID,))

    r = client.get(f"{BASE}/stories/{LIGHTHOUSE_ID}/versions/1/annotations/export")
    assert r.status_code == 200
    body = r.json()
    assert body["annotation_count"] == 0
    assert body["annotations"] == []


def test_export_unknown_version(client):
    r = client.get(f"{BASE}/stories/{LIGHTHOUSE_ID}/versions/9/annotations/export")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"
