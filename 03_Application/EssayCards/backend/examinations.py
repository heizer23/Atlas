"""
Oral-examination round trip — validation and DB core shared by
backend/routers/examinations.py.

Two directions, mirroring the export/import shape already established by
backend/ingest.py + backend/routers/essays.py::ingest_essay for the markdown/
JSON essay round trip:

  build_export_package(cur, essay_id)
      Reads an essay's current sections, flashcards, and (derived, read-only)
      latest examination per section into a single self-contained dict — no
      DB writes. Used by GET /essays/{essay_id}/examination-package.

  validate_import_body(body) -> (results, error_response)
      Full structural + semantic validation of an import payload, before any
      database access — same all-or-nothing precedent as
      essays.py::_validate_ingest_body. Returns parsed result dicts or an
      ApiError VALIDATION_ERROR response.

  import_results(conn, results) -> (rows, error_response)
      Resolves each result's essay_slug/section_anchor_slug to ids (rejecting
      the whole batch with NOT_FOUND if any pair doesn't exist), then inserts
      one row per result. Append-only: never updates or deletes an existing
      section_examinations row.

section_examinations is append-only by design (00_draft-equivalent decision,
see schema.sql comment) — "current understanding" of a section is always the
latest row, never a separately stored field.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from platform_errorhandling import api_error

_SLUG_LIKE_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


# ── Export ────────────────────────────────────────────────────────────────────

def build_export_package(cur: Any, essay_id: str) -> dict[str, Any] | None:
    """
    Returns the export package dict, or None if essay_id does not exist.
    Read-only — issues no writes.
    """
    cur.execute(
        "select id, title, slug from essaycards.essays where id = %s",
        (essay_id,),
    )
    essay_row = cur.fetchone()
    if not essay_row:
        return None

    cur.execute(
        """
        select id, anchor_slug, heading, order_index, body_markdown, updated_at
        from essaycards.essay_sections
        where essay_id = %s
        order by order_index asc
        """,
        (essay_id,),
    )
    section_rows = cur.fetchall()

    cur.execute(
        "select id, section_id, card_key, question, answer from essaycards.flashcards where essay_id = %s",
        (essay_id,),
    )
    cards_by_section: dict[str, list[dict[str, str]]] = {}
    for card in cur.fetchall():
        cards_by_section.setdefault(str(card["section_id"]), []).append({
            "id": card["card_key"],
            "q": card["question"],
            "a": card["answer"],
        })

    cur.execute(
        """
        select distinct on (section_id) section_id, examined_at, score, feedback
        from essaycards.section_examinations
        where essay_id = %s
        order by section_id, examined_at desc
        """,
        (essay_id,),
    )
    last_exam_by_section: dict[str, dict[str, Any]] = {
        str(row["section_id"]): {
            "examined_at": row["examined_at"].isoformat(),
            "score": row["score"],
            "feedback": row["feedback"],
        }
        for row in cur.fetchall()
    }

    sections = []
    for s in section_rows:
        section_id = str(s["id"])
        sections.append({
            "section_id": section_id,
            "anchor_slug": s["anchor_slug"],
            "heading": s["heading"],
            "body_markdown": s["body_markdown"],
            "section_version": s["updated_at"].isoformat(),
            "flashcards": cards_by_section.get(section_id, []),
            "last_examination": last_exam_by_section.get(section_id),
        })

    return {
        "essay_id": str(essay_row["id"]),
        "essay_slug": essay_row["slug"],
        "essay_title": essay_row["title"],
        "sections": sections,
    }


# ── Import validation ────────────────────────────────────────────────────────

def _parse_timestamp(value: Any) -> datetime | None:
    """
    Parses an ISO-8601 timestamp with an explicit UTC offset. A timezone-naive
    string (no offset, no trailing Z) is rejected — R-CON-AL-06 time authority:
    without this check, a naive value would be handed to psycopg2 and
    interpreted using the database connection's implicit session timezone
    rather than an explicitly declared one, silently shifting the stored
    instant depending on server configuration.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None
    return dt


def validate_import_body(body: Any) -> tuple[list[dict[str, Any]] | None, Any]:
    """
    Returns (results, None) on success, or (None, JSONResponse) with an
    ApiError VALIDATION_ERROR on the first violation found. Never touches
    the database.
    """
    if not isinstance(body, dict):
        return None, api_error("VALIDATION_ERROR", "Request body must be a JSON object")

    results_raw = body.get("results")
    if not isinstance(results_raw, list) or not results_raw:
        return None, api_error("VALIDATION_ERROR", "results is required and must be a non-empty list")

    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(results_raw):
        if not isinstance(entry, dict):
            return None, api_error("VALIDATION_ERROR", f"results[{idx}] must be an object")

        essay_slug = entry.get("essay_slug")
        if not isinstance(essay_slug, str) or not essay_slug.strip():
            return None, api_error(
                "VALIDATION_ERROR", f"results[{idx}].essay_slug is required and must be a non-empty string"
            )
        essay_slug = essay_slug.strip()

        section_anchor_slug = entry.get("section_anchor_slug")
        if not isinstance(section_anchor_slug, str) or not section_anchor_slug.strip():
            return None, api_error(
                "VALIDATION_ERROR",
                f"results[{idx}].section_anchor_slug is required and must be a non-empty string",
            )
        section_anchor_slug = section_anchor_slug.strip()

        section_version_raw = entry.get("section_version")
        section_version = _parse_timestamp(section_version_raw)
        if section_version is None:
            return None, api_error(
                "VALIDATION_ERROR",
                f"results[{idx}].section_version is required and must be an ISO-8601 timestamp",
            )

        examined_at_raw = entry.get("examined_at")
        examined_at = _parse_timestamp(examined_at_raw)
        if examined_at is None:
            return None, api_error(
                "VALIDATION_ERROR",
                f"results[{idx}].examined_at is required and must be an ISO-8601 timestamp",
            )

        question = entry.get("question")
        if not isinstance(question, str) or not question.strip():
            return None, api_error(
                "VALIDATION_ERROR", f"results[{idx}].question is required and must be a non-empty string"
            )

        answer_transcript = entry.get("answer_transcript")
        if not isinstance(answer_transcript, str) or not answer_transcript.strip():
            return None, api_error(
                "VALIDATION_ERROR", f"results[{idx}].answer_transcript is required and must be a non-empty string"
            )

        score = entry.get("score")
        if not isinstance(score, int) or isinstance(score, bool) or not (0 <= score <= 6):
            return None, api_error(
                "VALIDATION_ERROR", f"results[{idx}].score is required and must be an integer between 0 and 6"
            )

        feedback = entry.get("feedback")
        if feedback is not None and not isinstance(feedback, str):
            return None, api_error("VALIDATION_ERROR", f"results[{idx}].feedback must be a string or null")

        results.append({
            "essay_slug": essay_slug,
            "section_anchor_slug": section_anchor_slug,
            "section_version": section_version,
            "examined_at": examined_at,
            "question": question,
            "answer_transcript": answer_transcript,
            "score": score,
            "feedback": feedback,
        })

    return results, None


# ── Import DB core ────────────────────────────────────────────────────────────

def import_results(cur: Any, results: list[dict[str, Any]]) -> tuple[list[dict[str, Any]] | None, Any]:
    """
    Resolves every result's (essay_slug, section_anchor_slug) to ids first —
    if any pair doesn't exist, the whole batch is rejected with NOT_FOUND and
    no row is inserted. Only then inserts one row per result.

    Caller owns the transaction (commit/rollback) — this function only issues
    statements against `cur`.
    """
    resolved: list[dict[str, Any]] = []
    for idx, r in enumerate(results):
        cur.execute(
            "select id from essaycards.essays where slug = %s",
            (r["essay_slug"],),
        )
        essay_row = cur.fetchone()
        if not essay_row:
            return None, api_error(
                "NOT_FOUND", f"results[{idx}]: no essay found with slug '{r['essay_slug']}'", status=404
            )

        cur.execute(
            "select id from essaycards.essay_sections where essay_id = %s and anchor_slug = %s",
            (essay_row["id"], r["section_anchor_slug"]),
        )
        section_row = cur.fetchone()
        if not section_row:
            return None, api_error(
                "NOT_FOUND",
                f"results[{idx}]: no section '{r['section_anchor_slug']}' found in essay '{r['essay_slug']}'",
                status=404,
            )

        resolved.append({**r, "essay_id": essay_row["id"], "section_id": section_row["id"]})

    inserted: list[dict[str, Any]] = []
    for r in resolved:
        cur.execute(
            """
            insert into essaycards.section_examinations
                (essay_id, section_id, section_version_at, examined_at, question, answer_transcript, score, feedback)
            values (%s, %s, %s, %s, %s, %s, %s, %s)
            returning id, essay_id, section_id, examined_at, score
            """,
            (
                r["essay_id"], r["section_id"], r["section_version"], r["examined_at"],
                r["question"], r["answer_transcript"], r["score"], r["feedback"],
            ),
        )
        row = cur.fetchone()
        inserted.append({
            "id": str(row["id"]),
            "essay_id": str(row["essay_id"]),
            "section_id": str(row["section_id"]),
            "examined_at": row["examined_at"].isoformat(),
            "score": row["score"],
        })

    return inserted, None
