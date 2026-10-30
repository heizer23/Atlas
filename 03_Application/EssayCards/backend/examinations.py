"""
Oral-examination round trip — validation and DB core shared by
backend/routers/examinations.py.

Two directions, mirroring the export/import shape already established by
backend/ingest.py + backend/routers/essays.py::ingest_essay for the markdown/
JSON essay round trip:

  build_export_package(cur, essay_id, exam_type)
      Reads an essay's current sections, flashcards, and (derived, read-only)
      latest examination per section into a single self-contained dict — no
      DB writes. Used by GET /essays/{essay_id}/examination-package.
      Sprint12_FSRSAndUXOverhaul: exam_type ('guided' | 'unguided') is now a
      required parameter. For exam_type='guided', last_examination reflects
      only the latest exam_type='guided' row per section. For
      exam_type='unguided', last_examination is ALWAYS null — "unguided"
      means no calibration context is passed to the LLM, not merely "no
      unguided history exists yet". The package gains a top-level exam_type
      echo.

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

from psycopg2.extras import Json

from backend.oral_state import (
    apply_essay_attempt,
    apply_section_attempt,
    is_passing_score,
    score_percent,
    scoring_echo,
)
from backend.recall import GRADING, apply_recall_review, validate_evidence
from platform_errorhandling import api_error

_SLUG_LIKE_RE = re.compile(r"^[a-zA-Z0-9_-]+$")

# Closed, required, never-defaulted vocabulary (Sprint12_FSRSAndUXOverhaul) —
# same discipline as POST /flashcards/upsert's required card.level (R-CON-AL-04):
# a silently-defaulted exam_type could misclassify an unguided exam as guided
# or vice versa, silently corrupting the guided/unguided learning-progress
# milestones.
VALID_EXAM_TYPES = ("guided", "unguided")

# Sprint14: every oral attempt is either one section or the whole essay.
VALID_SCOPES = ("section", "essay")


# ── Export ────────────────────────────────────────────────────────────────────

def build_export_package(
    cur: Any, essay_id: str, exam_type: str, scope: str = "essay", section_id: str | None = None
) -> dict[str, Any] | None:
    """
    Returns the export package dict, or None if essay_id does not exist or
    (scope='section') section_id is not a section of that essay. Read-only —
    issues no writes. `exam_type` must be 'guided' or 'unguided' and `scope`
    'essay' or 'section' (section_id required iff scope='section'); the router
    validates the combination before this is called.

    Sprint14: scope='section' lists exactly that one section; scope='essay'
    lists every section and (guided only) adds last_essay_examination. A
    scoring echo built from backend.oral_state keeps prompts and verdicts in
    step. exam_type='unguided' keeps every last_examination and
    last_essay_examination null (cold start).
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
    if scope == "section":
        section_rows = [r for r in section_rows if str(r["id"]) == str(section_id)]
        if not section_rows:
            return None

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

    # exam_type='unguided' is a deliberate skip, not a query that happens to
    # return no rows — "unguided" means NO calibration context is ever passed,
    # regardless of whatever unguided history may already exist.
    if exam_type == "guided":
        cur.execute(
            """
            select distinct on (section_id) section_id, examined_at, score, feedback
            from essaycards.section_examinations
            where essay_id = %s and exam_type = 'guided'
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
    else:
        last_exam_by_section = {}

    # Sprint09_Nuggets: per-section nugget_versions ({nugget_key: current
    # nuggets.updated_at ISO8601}) for that section's currently-referenced
    # nuggets — mirrors the existing section_version field. Current
    # references only, computed live at export time.
    cur.execute(
        """
        select sn.section_id, n.nugget_key, n.title, n.body_markdown, n.updated_at
        from essaycards.section_nuggets sn
        join essaycards.nuggets n on n.id = sn.nugget_id
        where sn.section_id in (select id from essaycards.essay_sections where essay_id = %s)
        order by n.nugget_key
        """,
        (essay_id,),
    )
    nugget_versions_by_section: dict[str, dict[str, str]] = {}
    nuggets_by_section: dict[str, list[dict[str, str]]] = {}
    for row in cur.fetchall():
        nuggets_by_section.setdefault(str(row["section_id"]), []).append({
            "nugget_key": row["nugget_key"],
            "title": row["title"],
            "body_markdown": row["body_markdown"],
        })
        nugget_versions_by_section.setdefault(str(row["section_id"]), {})[row["nugget_key"]] = (
            row["updated_at"].isoformat()
        )

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
            "nugget_versions": nugget_versions_by_section.get(section_id, {}),
            # Full text of every nugget the section references, so the examiner
            # has the material behind [[nugget:key]] references. Read-only context.
            "nuggets": nuggets_by_section.get(section_id, []),
        })

    package: dict[str, Any] = {
        "essay_id": str(essay_row["id"]),
        "essay_slug": essay_row["slug"],
        "essay_title": essay_row["title"],
        "exam_type": exam_type,
        "scope": scope,
        **({"recall_grading": GRADING} if exam_type == "unguided" else {"scoring": scoring_echo()}),
        "sections": sections,
    }

    if scope == "essay":
        last_essay_exam = None
        if exam_type == "guided":
            cur.execute(
                """
                select examined_at, score, feedback
                from essaycards.essay_examinations
                where essay_id = %s and exam_type = 'guided'
                order by examined_at desc
                limit 1
                """,
                (essay_id,),
            )
            row = cur.fetchone()
            if row:
                last_essay_exam = {
                    "examined_at": row["examined_at"].isoformat(),
                    "score": row["score"],
                    "feedback": row["feedback"],
                }
        package["last_essay_examination"] = last_essay_exam

    return package


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

        scope = entry.get("scope")
        if scope not in VALID_SCOPES:
            return None, api_error(
                "VALIDATION_ERROR",
                f"results[{idx}].scope is required and must be one of: {', '.join(VALID_SCOPES)}",
            )

        # scope='section': section_anchor_slug required, section_version required.
        # scope='essay': section_anchor_slug must be omitted or null (omitted ==
        # null); section_version / nugget_versions are accepted and IGNORED.
        section_anchor_slug = entry.get("section_anchor_slug")
        section_version = None
        if scope == "section":
            if not isinstance(section_anchor_slug, str) or not section_anchor_slug.strip():
                return None, api_error(
                    "VALIDATION_ERROR",
                    f"results[{idx}].section_anchor_slug is required and must be a non-empty string",
                )
            section_anchor_slug = section_anchor_slug.strip()

            section_version = _parse_timestamp(entry.get("section_version"))
            if section_version is None:
                return None, api_error(
                    "VALIDATION_ERROR",
                    f"results[{idx}].section_version is required and must be an ISO-8601 timestamp",
                )
        elif section_anchor_slug is not None:
            return None, api_error(
                "VALIDATION_ERROR",
                f"results[{idx}].section_anchor_slug must be omitted or null for scope 'essay'",
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

        exam_type = entry.get("exam_type")
        if exam_type not in VALID_EXAM_TYPES:
            return None, api_error(
                "VALIDATION_ERROR",
                f"results[{idx}].exam_type is required and must be one of: {', '.join(VALID_EXAM_TYPES)}",
            )

        # Sprint16: unguided results are recall assessments (rating + evidence,
        # FSRS-scheduled); only guided essay results still carry a 0-6 score.
        score = None
        evidence = None
        if exam_type == "unguided":
            evidence, err = validate_evidence(entry.get("recall"), idx)
            if err is not None:
                return None, err
        else:
            score = entry.get("score")
            if not isinstance(score, int) or isinstance(score, bool) or not (0 <= score <= 6):
                return None, api_error(
                    "VALIDATION_ERROR", f"results[{idx}].score is required and must be an integer between 0 and 6"
                )

        if scope == "section" and exam_type == "guided":
            return None, api_error(
                "VALIDATION_ERROR",
                f"results[{idx}]: guided section orals are guided-learning sessions; import them with POST /guided/import",
            )

        feedback = entry.get("feedback")
        if feedback is not None and not isinstance(feedback, str):
            return None, api_error("VALIDATION_ERROR", f"results[{idx}].feedback must be a string or null")

        # Sprint09_Nuggets: optional per-result nugget_versions
        # (dict[nugget_key, ISO-8601 timestamp string]) — echoed verbatim into
        # section_examinations.nugget_versions_at, never recomputed at import
        # time. Absent or null -> stored SQL null ("predates this feature").
        nugget_versions = entry.get("nugget_versions") if scope == "section" else None
        if nugget_versions is not None:
            if not isinstance(nugget_versions, dict):
                return None, api_error(
                    "VALIDATION_ERROR", f"results[{idx}].nugget_versions, if present, must be an object"
                )
            for k, v in nugget_versions.items():
                if not isinstance(v, str) or not v.strip():
                    return None, api_error(
                        "VALIDATION_ERROR",
                        f"results[{idx}].nugget_versions['{k}'] must be a non-empty string",
                    )

        results.append({
            "scope": scope,
            "passed": is_passing_score(score) if score is not None else None,
            "evidence": evidence,
            "essay_slug": essay_slug,
            "section_anchor_slug": section_anchor_slug,
            "section_version": section_version,
            "examined_at": examined_at,
            "question": question,
            "answer_transcript": answer_transcript,
            "score": score,
            "feedback": feedback,
            "exam_type": exam_type,
            "nugget_versions": nugget_versions,
        })

    return results, None


# ── Import DB core ────────────────────────────────────────────────────────────

def import_results(cur: Any, results: list[dict[str, Any]]) -> tuple[list[dict[str, Any]] | None, Any]:
    """
    Resolves every result's essay_slug (and, for scope='section',
    section_anchor_slug) to ids first — if any does not exist, the whole batch
    is rejected with NOT_FOUND and nothing is written. Then, in ARRAY ORDER,
    inserts each attempt (section_examinations or essay_examinations, with the
    stored `passed` verdict) and applies the oral-state transition
    (oral_state.apply_*). Each returned row carries scope, passed,
    score_percent and effects.

    Caller owns the transaction (commit/rollback) — this function only issues
    statements against `cur`; any failure rolls back every attempt, state
    change, cascade and flag.
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

        section_id = None
        if r["scope"] == "section":
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
            section_id = section_row["id"]

        resolved.append({**r, "essay_id": essay_row["id"], "section_id": section_id})

    inserted: list[dict[str, Any]] = []
    for r in resolved:
        if r["exam_type"] == "unguided":
            applied = apply_recall_review(
                cur, r["scope"], r["essay_id"], r["section_id"], r["evidence"], r["examined_at"],
                r["question"], r["answer_transcript"], r["feedback"],
                r["section_version"], r.get("nugget_versions"),
            )
            inserted.append({
                **applied,
                "scope": r["scope"],
                "exam_type": "unguided",
                "essay_id": str(r["essay_id"]),
                "section_id": str(r["section_id"]) if r["section_id"] else None,
                "examined_at": r["examined_at"].isoformat(),
                "score": None,
                "passed": None,
                "score_percent": None,
            })
            continue
        if r["scope"] == "section":
            nugget_versions = r.get("nugget_versions")
            cur.execute(
                """
                insert into essaycards.section_examinations
                    (essay_id, section_id, section_version_at, examined_at, question, answer_transcript,
                     score, passed, feedback, exam_type, nugget_versions_at)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                returning id, essay_id, section_id, examined_at, score
                """,
                (
                    r["essay_id"], r["section_id"], r["section_version"], r["examined_at"],
                    r["question"], r["answer_transcript"], r["score"], r["passed"], r["feedback"],
                    r["exam_type"],
                    Json(nugget_versions) if nugget_versions is not None else None,
                ),
            )
            row = cur.fetchone()
            effects = apply_section_attempt(
                cur, row["section_id"], r["exam_type"], r["score"], r["passed"], r["examined_at"]
            )
        else:
            cur.execute(
                """
                insert into essaycards.essay_examinations
                    (essay_id, exam_type, examined_at, question, answer_transcript, score, passed, feedback)
                values (%s, %s, %s, %s, %s, %s, %s, %s)
                returning id, essay_id, examined_at, score
                """,
                (
                    r["essay_id"], r["exam_type"], r["examined_at"], r["question"],
                    r["answer_transcript"], r["score"], r["passed"], r["feedback"],
                ),
            )
            row = cur.fetchone()
            effects = apply_essay_attempt(
                cur, row["essay_id"], r["exam_type"], r["score"], r["passed"], r["examined_at"]
            )

        inserted.append({
            "id": str(row["id"]),
            "scope": r["scope"],
            "essay_id": str(row["essay_id"]),
            "section_id": str(r["section_id"]) if r["section_id"] else None,
            "examined_at": row["examined_at"].isoformat(),
            "score": row["score"],
            "passed": r["passed"],
            "score_percent": score_percent(row["score"]),
            "effects": effects,
        })

    return inserted, None


def summarize_cascades(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collects {essay_id, cards_flagged} for every failure cascade that fired in this import."""
    return [
        {"essay_id": e["essay_id"], "cards_flagged": e["cards_flagged"]}
        for row in rows
        for e in row["effects"]
        if e["effect"] == "essay_unguided_failed_cascade"
    ]


# ── Nugget-aware freshness (Sprint09_Nuggets) ────────────────────────────────

def nugget_freshness_flags(recorded: dict[str, str] | None, current: dict[str, str]) -> list[str]:
    """
    Pure comparison helper implementing 00_draft.md §9's freshness rule — no
    DB access. `recorded` is a stored section_examinations.nugget_versions_at
    value (or None); `current` is a freshly computed live nugget_versions
    mapping for the same section (see build_export_package).

    recorded is None -> [] (predates this feature; the nugget-level check is
    skipped gracefully). Otherwise: every key in `current` that is either
    missing from `recorded` or present with a different value is flagged
    ("nugget changed since last exam"); a key present and matching is not
    flagged. Returned sorted for determinism.

    NOT called by any endpoint or UI this sprint — infrastructure only; where
    (if anywhere) this is surfaced is explicitly deferred (see
    10_architecture.json deferred_decisions).
    """
    if recorded is None:
        return []

    return sorted(
        key for key, value in current.items()
        if key not in recorded or recorded[key] != value
    )
