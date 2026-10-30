"""
EssayCards — Sprint14_SectionProgressionAndRevalidation: oral import and pass
rule (guided essay orals), examination-package scope. Sprint16: the unguided-essay
failure cascade was retired — unguided results are FSRS recall reviews (tests/test_recall.py).

Traceability: each function name maps to a scenario in
Sprint14_SectionProgressionAndRevalidation/10_test_spec.md ("Oral import and
pass rule" and "Failure cascade and revalidation flagging"). Fixture ids are
defined in tests/fixtures.sql (Sprint14 block).
"""

from datetime import datetime

from tests.helpers import run_sql, unlock_essay_sections

IMPORT_URL = "/api/essaycards/examinations/import"
PROGRESS_URL = "/api/essaycards/progress/sections"

# fixture ids
ESSAY_LOCKED = "ea00000c-0000-0000-0000-00000000000c"
SECTION_LOCKED = "ec000017-0000-0000-0000-000000000017"
ESSAY_YELLOW = "ea00000d-0000-0000-0000-00000000000d"
ESSAY_BLUE = "ea000011-0000-0000-0000-000000000011"
ESSAY_VIOLET = "ea000012-0000-0000-0000-000000000012"
SECTION_VIOLET_1 = "ec00001f-0000-0000-0000-00000000001f"
SECTION_VIOLET_2 = "ec000020-0000-0000-0000-000000000020"
SECTION_BLUE_1 = "ec00001d-0000-0000-0000-00000000001d"
VIOLET_REVIEWED_CARDS = {
    "fc000046-0000-0000-0000-000000000046",
    "fc000047-0000-0000-0000-000000000047",
    "fc000048-0000-0000-0000-000000000048",
}
VIOLET_NEVER_REVIEWED_CARD = "fc000049-0000-0000-0000-000000000049"


def _section_version(section_id: str) -> str:
    return run_sql("select updated_at from essaycards.essay_sections where id = %s", (section_id,))[0][
        "updated_at"
    ].isoformat()


GOOD_RECALL = {
    "rating": "good", "independent_elements": ["spine"], "prompted_elements": [],
    "missing_elements": [], "misunderstandings": [], "followups_asked": 0,
}


def _section_result(slug, anchor, section_id, score, exam_type, examined_at="2026-09-01T10:00:00Z"):
    """Unguided results carry recall evidence instead of a score (Sprint16)."""
    entry = {
        "scope": "section", "essay_slug": slug, "section_anchor_slug": anchor,
        "section_version": _section_version(section_id), "examined_at": examined_at,
        "question": "Q", "answer_transcript": "A", "exam_type": exam_type,
    }
    if exam_type == "unguided":
        entry["recall"] = GOOD_RECALL
    else:
        entry["score"] = score
    return entry


def _essay_result(slug, score, exam_type, examined_at="2026-09-01T10:00:00Z", **extra):
    entry = {
        "scope": "essay", "essay_slug": slug, "examined_at": examined_at,
        "question": "Q", "answer_transcript": "A", "exam_type": exam_type, **extra,
    }
    if exam_type == "unguided":
        entry["recall"] = GOOD_RECALL
    else:
        entry["score"] = score
    return entry


def _import(client, *results):
    return client.post(IMPORT_URL, json={"results": list(results)})


def _section_state(client, essay_id, section_id):
    rows = client.get(PROGRESS_URL, params={"essay_id": essay_id}).json()["rows"]
    return next(r for r in rows if r["section_id"] == section_id)


def _essay_row(client, essay_id):
    return next(r for r in client.get("/api/essaycards/essays").json()["rows"] if r["id"] == essay_id)


def _count(sql, params=()):
    return run_sql(sql, params)[0]["n"]


def _mk_essay_with_sections(client, slug, n_sections):
    r = client.post("/api/essaycards/essays/ingest", json={
        "title": slug, "slug": slug,
        "sections": [
            {"heading": f"S{i}", "anchor_slug": f"{slug}-s{i}", "body_markdown": "b", "cards": []}
            for i in range(n_sections)
        ],
    })
    assert r.status_code == 200, r.text
    return r.json()["essay_id"]


# ── Oral import and pass rule ────────────────────────────────────────────────

def test_score_5_of_6_passes_the_70_percent_rule(client):
    r = _import(client, _essay_result("fix-essay-locked", 5, "guided"))
    assert r.status_code == 200, r.text
    res = r.json()["results"][0]
    assert res["passed"] is True
    assert res["score_percent"] == 83.3
    hist = client.get(f"/api/essaycards/essays/{ESSAY_LOCKED}/examinations").json()["rows"]
    assert hist[0]["passed"] is True


def test_score_4_of_6_fails_the_70_percent_rule(client):
    r = _import(client, _essay_result("fix-essay-locked", 4, "guided"))
    assert r.status_code == 200, r.text
    res = r.json()["results"][0]
    assert res["passed"] is False
    assert res["score_percent"] == 66.7
    hist = client.get(f"/api/essaycards/essays/{ESSAY_LOCKED}/examinations").json()["rows"]
    assert len(hist) == 1 and hist[0]["passed"] is False
    assert _essay_row(client, ESSAY_LOCKED)["essay_guided_passed"] is False


def test_unguided_results_carry_recall_evidence_not_a_score(client):
    r = _import(client, _section_result("fix-essay-locked", "fix-locked-1", SECTION_LOCKED, 5, "unguided"))
    assert r.status_code == 200, r.text
    res = r.json()["results"][0]
    assert res["score"] is None and res["passed"] is None and res["rating"] == "good"
    # a numeric-score-only unguided result (the retired format) is rejected with a pointer to `recall`
    old = _section_result("fix-essay-locked", "fix-locked-1", SECTION_LOCKED, 5, "unguided")
    del old["recall"]
    old["score"] = 5
    r = _import(client, old)
    assert r.status_code == 400 and "recall" in r.json()["error"]["message"]


def test_guided_section_result_is_rejected_by_the_exam_import(client):
    r = _import(client, _section_result("fix-essay-locked", "fix-locked-1", SECTION_LOCKED, 5, "guided"))
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert _count("select count(*) as n from essaycards.section_examinations where section_id = %s", (SECTION_LOCKED,)) == 0


def test_section_scope_result_requires_section_anchor_slug(client):
    bad = _section_result("fix-essay-locked", "fix-locked-1", SECTION_LOCKED, 5, "guided")
    del bad["section_anchor_slug"]
    r = _import(client, bad)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert _count("select count(*) as n from essaycards.section_examinations where section_id = %s", (SECTION_LOCKED,)) == 0


def test_essay_scope_result_with_non_null_section_anchor_slug_is_rejected(client):
    r = _import(client, _essay_result("fix-essay-locked", 5, "guided", section_anchor_slug="intro"))
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert _count("select count(*) as n from essaycards.essay_examinations where essay_id = %s", (ESSAY_LOCKED,)) == 0


def test_essay_scope_result_accepts_omitted_and_null_section_anchor_slug_equivalently(client):
    r_omit = _import(client, _essay_result("fix-essay-locked", 5, "guided"))
    r_null = _import(client, _essay_result("fix-essay-locked", 5, "guided", section_anchor_slug=None))
    assert r_omit.status_code == 200 and r_null.status_code == 200
    a, b = r_omit.json()["results"][0], r_null.json()["results"][0]
    for key in ("scope", "passed", "score_percent", "section_id"):
        assert a[key] == b[key]
    assert _count("select count(*) as n from essaycards.essay_examinations where essay_id = %s", (ESSAY_LOCKED,)) == 2


def test_missing_or_invalid_scope_is_rejected(client):
    missing = _essay_result("fix-essay-locked", 5, "guided")
    del missing["scope"]
    invalid = _essay_result("fix-essay-locked", 5, "guided")
    invalid["scope"] = "chapter"
    for bad in (missing, invalid):
        r = _import(client, bad)
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "VALIDATION_ERROR"
        assert "scope" in r.json()["error"]["message"]


def test_batch_import_is_all_or_nothing(client):
    good1 = _section_result("fix-essay-locked", "fix-locked-1", SECTION_LOCKED, 5, "unguided")
    good2 = _essay_result("fix-essay-locked", 5, "guided")
    bad = _section_result("fix-essay-locked", "fix-locked-1", SECTION_LOCKED, 5, "unguided")
    bad["section_anchor_slug"] = "does-not-exist"
    r = _import(client, good1, good2, bad)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"
    assert _count("select count(*) as n from essaycards.recall_reviews where section_id = %s", (SECTION_LOCKED,)) == 0
    assert _count("select count(*) as n from essaycards.recall_state where section_id = %s", (SECTION_LOCKED,)) == 0
    assert _count("select count(*) as n from essaycards.essay_examinations where essay_id = %s", (ESSAY_LOCKED,)) == 0
    assert _count("select count(*) as n from essaycards.section_oral_state where section_id = %s", (SECTION_LOCKED,)) == 0
    assert _count("select count(*) as n from essaycards.essay_oral_state where essay_id = %s", (ESSAY_LOCKED,)) == 0


def test_examination_package_scope_section_contains_only_that_section(client):
    essay_id = _mk_essay_with_sections(client, "pkg-three", 3)
    sections = client.get(f"/api/essaycards/essays/{essay_id}").json()["rows"][0]["sections"]
    second = sections[1]
    r = client.get(
        f"/api/essaycards/essays/{essay_id}/examination-package",
        params={"exam_type": "unguided", "scope": "section", "section_id": second["id"]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert [s["section_id"] for s in body["sections"]] == [second["id"]]
    assert body["scope"] == "section"
    assert "scoring" not in body  # unguided packages carry the recall rubric instead
    assert set(body["recall_grading"]["ratings"]) == {"again", "hard", "good", "easy"}
    assert "maximum rating is hard" in body["recall_grading"]["critical_rule"]
    guided = client.get(
        f"/api/essaycards/essays/{essay_id}/examination-package", params={"exam_type": "guided", "scope": "essay"}
    ).json()
    assert guided["scoring"] == {"score_max": 6, "pass_threshold_percent": 70, "min_passing_score": 5}
    assert "recall_grading" not in guided


def test_examination_package_scope_essay_contains_all_sections_and_last_essay_result(client):
    base = f"/api/essaycards/essays/{ESSAY_YELLOW}/examination-package"
    guided = client.get(base, params={"exam_type": "guided", "scope": "essay"}).json()
    assert len(guided["sections"]) == 2
    assert guided["last_essay_examination"]["score"] == 5
    unguided = client.get(base, params={"exam_type": "unguided", "scope": "essay"}).json()
    assert len(unguided["sections"]) == 2
    assert unguided["last_essay_examination"] is None


def test_examination_package_rejects_invalid_parameter_combinations(client):
    base = f"/api/essaycards/essays/{ESSAY_YELLOW}/examination-package"
    some_section = "ec000018-0000-0000-0000-000000000018"
    for params in (
        {"exam_type": "guided", "scope": "section"},
        {"exam_type": "guided", "scope": "essay", "section_id": some_section},
        {"exam_type": "guided"},
    ):
        r = client.get(base, params=params)
        assert r.status_code == 400, params
        assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    # a section that belongs to another essay
    r = client.get(base, params={"exam_type": "unguided", "scope": "section", "section_id": SECTION_LOCKED})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"
