"""
EssayCards — ingestion tests.

Calls backend.ingest.ingest() directly against fixture markdown files under
tests/fixtures_md/ (no HTTP). Traceability: each function name maps to a
scenario in Sprint01_Core/10_test_spec.md.
"""

import os

import pytest

from backend.ingest import IngestionError, ingest

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures_md")


def _path(name: str) -> str:
    return os.path.join(FIXTURES_DIR, name)


def _essay_count(db_conn, slug: str) -> int:
    with db_conn.cursor() as cur:
        cur.execute("select count(*) as n from essaycards.essays where slug = %s", (slug,))
        return cur.fetchone()["n"]


# ── Ingestion — creates essay, sections, and flashcards due immediately ───────

def test_ingest_creates_essay_sections_and_cards(db_conn):
    summary = ingest(_path("well_formed.md"), db_conn)

    assert summary.essay_created is True
    assert summary.sections_created == 2
    assert summary.flashcards_created == 3

    with db_conn.cursor() as cur:
        cur.execute("select id, title from essaycards.essays where slug = 'test-essay'")
        essay = cur.fetchone()
        assert essay is not None
        assert essay["title"] == "Test Essay"

        cur.execute(
            "select heading, anchor_slug, order_index, body_markdown from essaycards.essay_sections "
            "where essay_id = %s order by order_index asc",
            (essay["id"],),
        )
        sections = cur.fetchall()
        assert len(sections) == 2
        assert sections[0]["anchor_slug"] == "first"
        assert sections[0]["order_index"] == 0
        assert sections[1]["anchor_slug"] == "second"
        assert sections[1]["order_index"] == 1
        assert "```flashcards" not in sections[0]["body_markdown"]
        assert "```flashcards" not in sections[1]["body_markdown"]

        cur.execute(
            "select f.card_key, f.question, f.answer, f.created_at, rs.last_reviewed_at, rs.next_due_at "
            "from essaycards.flashcards f "
            "join essaycards.flashcard_review_state rs on rs.flashcard_id = f.id "
            "where f.essay_id = %s order by f.card_key",
            (essay["id"],),
        )
        cards = cur.fetchall()
        assert [c["card_key"] for c in cards] == ["fc-test-1", "fc-test-2", "fc-test-3"]
        for c in cards:
            assert c["last_reviewed_at"] is None
            assert c["next_due_at"] == c["created_at"]


# ── Ingestion — re-ingesting an unchanged file preserves review state ─────────

def test_reingest_preserves_review_state(db_conn):
    ingest(_path("well_formed.md"), db_conn)

    with db_conn.cursor() as cur:
        cur.execute("select id from essaycards.flashcards where card_key = 'fc-test-1'")
        flashcard_id = cur.fetchone()["id"]
        cur.execute(
            "update essaycards.flashcard_review_state "
            "set last_reviewed_at = now() - interval '10 minutes', next_due_at = now() + interval '30 minutes' "
            "where flashcard_id = %s",
            (flashcard_id,),
        )
        cur.execute(
            "select last_reviewed_at, next_due_at from essaycards.flashcard_review_state where flashcard_id = %s",
            (flashcard_id,),
        )
        before = cur.fetchone()

    summary = ingest(_path("well_formed.md"), db_conn)
    assert summary.essay_created is False
    assert summary.flashcards_updated == 3
    assert summary.flashcards_created == 0

    with db_conn.cursor() as cur:
        cur.execute(
            "select last_reviewed_at, next_due_at from essaycards.flashcard_review_state where flashcard_id = %s",
            (flashcard_id,),
        )
        after = cur.fetchone()

    assert after["last_reviewed_at"] == before["last_reviewed_at"]
    assert after["next_due_at"] == before["next_due_at"]


# ── Ingestion — re-ingesting edited text updates content only ─────────────────

def test_reingest_updates_changed_text_only(db_conn):
    ingest(_path("well_formed.md"), db_conn)

    with db_conn.cursor() as cur:
        cur.execute("select id from essaycards.flashcards where card_key = 'fc-test-1'")
        flashcard_id = cur.fetchone()["id"]
        cur.execute(
            "update essaycards.flashcard_review_state "
            "set last_reviewed_at = now() - interval '10 minutes', next_due_at = now() + interval '30 minutes' "
            "where flashcard_id = %s",
            (flashcard_id,),
        )
        cur.execute(
            "select last_reviewed_at, next_due_at from essaycards.flashcard_review_state where flashcard_id = %s",
            (flashcard_id,),
        )
        before = cur.fetchone()

    ingest(_path("well_formed_edited.md"), db_conn)

    with db_conn.cursor() as cur:
        cur.execute(
            "select question, question <> '' as has_question from essaycards.flashcards where id = %s",
            (flashcard_id,),
        )
        card = cur.fetchone()
        cur.execute(
            "select last_reviewed_at, next_due_at from essaycards.flashcard_review_state where flashcard_id = %s",
            (flashcard_id,),
        )
        after = cur.fetchone()

    assert card["question"] == "Question one, edited?"
    assert after["last_reviewed_at"] == before["last_reviewed_at"]
    assert after["next_due_at"] == before["next_due_at"]


# ── Ingestion — missing anchor slug aborts with no rows written ───────────────

def test_ingest_missing_anchor_rejected(db_conn):
    with pytest.raises(IngestionError):
        ingest(_path("missing_anchor.md"), db_conn)

    assert _essay_count(db_conn, "missing-anchor-essay") == 0


# ── Ingestion — malformed flashcards YAML aborts with no rows written ─────────

def test_ingest_malformed_flashcards_yaml_rejected(db_conn):
    with pytest.raises(IngestionError):
        ingest(_path("malformed_cards_missing_answer.md"), db_conn)

    assert _essay_count(db_conn, "malformed-cards-essay") == 0


# ── Ingestion — multiple flashcards blocks in one section aborts ──────────────

def test_ingest_multiple_flashcards_blocks_rejected(db_conn):
    with pytest.raises(IngestionError):
        ingest(_path("multiple_flashcards_blocks.md"), db_conn)

    assert _essay_count(db_conn, "multi-fence-essay") == 0


# ── Ingestion — duplicate card id within file aborts ───────────────────────────

def test_ingest_duplicate_card_key_rejected(db_conn):
    with pytest.raises(IngestionError):
        ingest(_path("duplicate_card_key.md"), db_conn)

    assert _essay_count(db_conn, "dup-card-essay") == 0


# ── Ingestion — duplicate anchor_slug within file aborts (design review §Recommended Improvements) ──

def test_ingest_duplicate_anchor_slug_rejected(db_conn):
    with pytest.raises(IngestionError):
        ingest(_path("duplicate_anchor_slug.md"), db_conn)

    assert _essay_count(db_conn, "dup-anchor-essay") == 0
