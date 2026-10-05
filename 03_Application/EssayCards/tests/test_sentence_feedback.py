"""
EssayCards — sentence splitting and sentence feedback endpoints
(Sprint13_ReviewStatsSentenceFeedback). Function names map to scenarios in
Sprint13_ReviewStatsSentenceFeedback/10_test_spec.md. World: tests/fixtures.sql
"Sprint13" block (essay S, sections fix-sent-*).
"""

ESSAY = "ea00000b-0000-0000-0000-00000000000b"
PLAIN = "ec000012-0000-0000-0000-000000000012"
LINK = "ec000013-0000-0000-0000-000000000013"
NUGGET = "ec000014-0000-0000-0000-000000000014"
CODE = "ec000015-0000-0000-0000-000000000015"
FEEDBACK = "ec000016-0000-0000-0000-000000000016"


def _sentences(client, section_id, essay=ESSAY):
    r = client.get(f"/api/essaycards/essays/{essay}/sentences")
    assert r.status_code == 200
    return [row for row in r.json()["rows"] if row["section_id"] == section_id]


def _feedback(client, essay=ESSAY):
    r = client.get(f"/api/essaycards/essays/{essay}/sentence-feedback")
    assert r.status_code == 200
    return r.json()["rows"]


def _patch(client, section_id, index, text, flag, value):
    return client.patch(
        f"/api/essaycards/sections/{section_id}/sentence-feedback",
        json={"sentence_index": index, "sentence_text": text, "flag": flag, "value": value},
    )


def _fb_row(client, section_id, index):
    return next((r for r in _feedback(client) if r["section_id"] == section_id and r["sentence_index"] == index), None)


# ── splitting ────────────────────────────────────────────────────────────────

def test_sentence_splitting_plain_prose_splits_at_sentence_boundaries(client):
    rows = _sentences(client, PLAIN)
    assert [r["text"] for r in rows] == ["The sky is blue.", "The grass is green.", "Is that surprising?"]
    assert [r["sentence_index"] for r in rows] == [0, 1, 2]


def test_sentence_splitting_markdown_link_is_not_split_at_its_internal_period(client):
    rows = _sentences(client, LINK)
    assert len(rows) == 2
    assert rows[0]["text"] == "See [source](http://example.com/a.b) for details on this."


def test_sentence_splitting_nugget_reference_is_not_split(client):
    rows = _sentences(client, NUGGET)
    assert len(rows) == 2
    assert "[[nugget:some-key]]" in rows[0]["text"]


def test_sentence_splitting_fenced_code_content_is_excluded(client):
    rows = _sentences(client, CODE)
    assert rows, "prose sentences must still be returned"
    assert not any("x = 1" in r["text"] or "```" in r["text"] for r in rows)
    assert rows[-1]["text"] == "After the code."


def test_sentences_unknown_essay_is_not_found(client):
    r = client.get("/api/essaycards/essays/00000000-0000-0000-0000-00000000dead/sentences")
    assert r.status_code == 404


# ── feedback list ────────────────────────────────────────────────────────────

def test_sentence_feedback_list_empty_when_nothing_is_marked(client):
    r = client.get("/api/essaycards/essays/ea000001-0000-0000-0000-000000000001/sentence-feedback")
    assert r.status_code == 200
    assert r.json()["rows"] == []


def test_sentence_feedback_list_only_marked_sentences_appear(client):
    rows = _feedback(client)
    assert [(r["sentence_index"], r["is_difficult"], r["is_thumbs_up"]) for r in rows] == [
        (0, True, False),
        (1, False, True),
    ]
    assert all(r["section_id"] == FEEDBACK for r in rows)


# ── PATCH ────────────────────────────────────────────────────────────────────

def test_marking_difficult_then_thumbs_up_on_same_sentence_yields_one_row_with_both_flags(client):
    assert _patch(client, FEEDBACK, 2, "Gamma is third.", "difficult", True).status_code == 200
    r = _patch(client, FEEDBACK, 2, "Gamma is third.", "thumbs_up", True)
    assert r.status_code == 200
    assert r.json() == {"section_id": FEEDBACK, "sentence_index": 2, "is_difficult": True, "is_thumbs_up": True}

    matching = [x for x in _feedback(client) if x["sentence_index"] == 2]
    assert len(matching) == 1
    assert matching[0]["is_difficult"] is True and matching[0]["is_thumbs_up"] is True


def test_clearing_the_only_true_flag_deletes_the_row(client):
    r = _patch(client, FEEDBACK, 0, "Alpha is first.", "difficult", False)
    assert r.status_code == 200
    assert _fb_row(client, FEEDBACK, 0) is None


def test_clearing_one_flag_leaves_the_other_flag_and_the_row_intact(client):
    _patch(client, FEEDBACK, 0, "Alpha is first.", "thumbs_up", True)  # now both
    r = _patch(client, FEEDBACK, 0, "Alpha is first.", "difficult", False)
    assert r.status_code == 200
    row = _fb_row(client, FEEDBACK, 0)
    assert row is not None
    assert row["is_difficult"] is False and row["is_thumbs_up"] is True


def test_sentence_feedback_out_of_range_sentence_index_is_rejected(client):
    r = _patch(client, FEEDBACK, 99, "Whatever.", "difficult", True)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_sentence_feedback_sentence_text_mismatch_is_rejected(client):
    r = _patch(client, FEEDBACK, 2, "Not the live sentence.", "difficult", True)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert _fb_row(client, FEEDBACK, 2) is None


def test_sentence_feedback_unknown_section_is_not_found(client):
    r = _patch(client, "00000000-0000-0000-0000-00000000dead", 0, "x", "difficult", True)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_sentence_feedback_invalid_flag_value_is_rejected(client):
    r = _patch(client, FEEDBACK, 2, "Gamma is third.", "loved", True)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
