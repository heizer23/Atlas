"""
Guided oral progression — six Socratic learning levels per section.

Guided orals are learning conversations, not exams: the AI recommends, the
LEARNER confirms, and only a confirmed advance moves
section_oral_state.guided_level. No score, no FSRS, no cooldown. Completing
Level 1 sets section_oral_state.guided_passed (the flashcard-unlock flag,
unchanged). Unguided orals remain the authority on mastery.

Single home of: the level specs (shipped inside the export package so the
frontend prompt cannot drift), package building, import validation and the
transition. No HTTP. The caller owns the transaction (statements on `cur`).
"""

from __future__ import annotations

from typing import Any

from psycopg2.extras import Json

from backend.examinations import _parse_timestamp
from platform_errorhandling import api_error

MAX_LEVEL = 6
HISTORY_IN_PACKAGE = 3

VALID_RECOMMENDATIONS = ("advance", "continue")
VALID_DECISIONS = ("advance", "stay")

GUIDED_LEVELS: dict[int, dict[str, str]] = {
    1: {
        "name": "Orientation",
        "expectation": "Understand the argument spine and the nuggets at a basic level. Conceptual difficulties are acceptable.",
        "ai_behavior": "Substantial guidance: explain, correct and rephrase freely, then check the learner's grasp with simple questions.",
        "advance_when": "The learner can follow the spine and state its main steps and nuggets roughly right. Minor imperfections are fine; only a serious misunderstanding of the spine blocks a recommendation.",
    },
    2: {
        "name": "Comprehension",
        "expectation": "Explain the central concepts in your own words.",
        "ai_behavior": "Hints and clarification when the learner is stuck; otherwise ask for their own wording.",
        "advance_when": "The learner explains the central concepts in their own words without leaning on the text's phrasing.",
    },
    3: {
        "name": "Connections",
        "expectation": "Explain how the concepts relate and how they support the argument.",
        "ai_behavior": "Probing questions about relations and support; an occasional hint, never the answer.",
        "advance_when": "The learner explains how concepts relate and why each step supports the argument.",
    },
    4: {
        "name": "Application",
        "expectation": "Apply the concepts to examples and unfamiliar situations.",
        "ai_behavior": "Mostly open questions and new cases; intervene only to correct a serious error.",
        "advance_when": "The learner applies the concepts correctly to cases they have not seen.",
    },
    5: {
        "name": "Critical understanding",
        "expectation": "Explain, defend and critically examine the argument.",
        "ai_behavior": "Minimal guidance: challenge, raise objections, ask the learner to defend and criticise. From here, suggest an unguided oral when appropriate.",
        "advance_when": "The learner defends the argument, states its strongest objections and assesses them.",
    },
    6: {
        "name": "Independence",
        "expectation": "Demonstrate deep, coherent understanding independently.",
        "ai_behavior": "Almost no leading questions. Probe (Nachhaken) every superficial answer: distinguish genuine understanding from merely mentioning terminology. Never supply the answer. Level 6 is optional preparation for an unguided oral.",
        "advance_when": "Level 6 is the last level; completing it records full guided preparation.",
    },
}


def current_level(state: dict[str, Any] | None) -> int:
    """Highest confirmed level. A passed-but-level-0 row (legacy) reads as Level 1."""
    if not state:
        return 0
    return max(int(state.get("guided_level") or 0), 1 if state.get("guided_passed") else 0)


def _load_state(cur: Any, section_id: str, lock: bool = False) -> dict[str, Any] | None:
    cur.execute(
        "select guided_passed, guided_level from essaycards.section_oral_state where section_id = %s"
        + (" for update" if lock else ""),
        (section_id,),
    )
    return cur.fetchone()


# ── Export ────────────────────────────────────────────────────────────────────

def build_guided_package(cur: Any, section_id: str, level: int | None = None) -> tuple[dict[str, Any] | None, str | None]:
    """
    Returns (package, None), (None, None) if the section does not exist, or
    (None, message) if `level` is not allowed. Default level = next level to
    conduct (min(completed + 1, 6)); an explicit level may revisit any level up
    to completed + 1. Read-only.
    """
    cur.execute(
        """
        select s.id, s.anchor_slug, s.heading, s.body_markdown, s.updated_at,
               e.id as essay_id, e.slug as essay_slug, e.title as essay_title, e.main_spine_markdown
        from essaycards.essay_sections s
        join essaycards.essays e on e.id = s.essay_id
        where s.id = %s
        """,
        (section_id,),
    )
    s = cur.fetchone()
    if not s:
        return None, None

    completed = current_level(_load_state(cur, section_id))
    next_level = min(completed + 1, MAX_LEVEL)
    if level is None:
        level = next_level
    elif not 1 <= level <= next_level:
        return None, f"level must be between 1 and {next_level} for this section"

    cur.execute(
        """
        select n.nugget_key, n.title, n.body_markdown, n.updated_at
        from essaycards.section_nuggets sn
        join essaycards.nuggets n on n.id = sn.nugget_id
        where sn.section_id = %s
        order by n.nugget_key
        """,
        (section_id,),
    )
    nugget_rows = cur.fetchall()

    cur.execute(
        """
        select level, session_at, recommendation, learner_decision, advanced_to, demonstrated, gaps
        from essaycards.section_guided_sessions
        where section_id = %s
        order by session_at desc, created_at desc
        limit %s
        """,
        (section_id, HISTORY_IN_PACKAGE),
    )
    recent = cur.fetchall()
    carried = None
    if recent:
        latest = recent[0]
        carried = {
            "from_level": latest["level"],
            "session_at": latest["session_at"].isoformat(),
            "demonstrated": latest["demonstrated"],
            "unresolved_gaps": latest["gaps"],
        }

    return {
        "kind": "guided_session",
        "essay_id": str(s["essay_id"]),
        "essay_slug": s["essay_slug"],
        "essay_title": s["essay_title"],
        "essay_spine_markdown": s["main_spine_markdown"],
        "section": {
            "section_id": str(s["id"]),
            "anchor_slug": s["anchor_slug"],
            "heading": s["heading"],
            "body_markdown": s["body_markdown"],
            "section_version": s["updated_at"].isoformat(),
            "nuggets": [
                {"nugget_key": n["nugget_key"], "title": n["title"], "body_markdown": n["body_markdown"]}
                for n in nugget_rows
            ],
            "nugget_versions": {n["nugget_key"]: n["updated_at"].isoformat() for n in nugget_rows},
        },
        "level": level,
        "max_level": MAX_LEVEL,
        "level_spec": {"level": level, **GUIDED_LEVELS[level]},
        "guided_progress": {
            "completed_level": completed,
            "carried": carried,
            "history": [
                {
                    "level": r["level"],
                    "session_at": r["session_at"].isoformat(),
                    "recommendation": r["recommendation"],
                    "learner_decision": r["learner_decision"],
                    "advanced_to": r["advanced_to"],
                }
                for r in recent
            ],
        },
    }, None


# ── Import validation ─────────────────────────────────────────────────────────

def _text(entry: dict[str, Any], key: str, where: str) -> tuple[str | None, Any]:
    v = entry.get(key)
    if not isinstance(v, str) or not v.strip():
        return None, api_error("VALIDATION_ERROR", f"{where}.{key} is required and must be a non-empty string")
    return v.strip() if key in ("essay_slug", "section_anchor_slug") else v, None


def validate_guided_body(body: Any) -> tuple[dict[str, Any] | None, Any]:
    """(session, None) or (None, ApiError VALIDATION_ERROR). Never touches the DB."""
    if not isinstance(body, dict):
        return None, api_error("VALIDATION_ERROR", "Request body must be a JSON object")
    entry = body.get("guided_session")
    if not isinstance(entry, dict):
        return None, api_error("VALIDATION_ERROR", "guided_session is required and must be an object")
    where = "guided_session"

    decision = body.get("learner_decision")
    if decision not in VALID_DECISIONS:
        return None, api_error(
            "VALIDATION_ERROR", f"learner_decision is required and must be one of: {', '.join(VALID_DECISIONS)}"
        )

    out: dict[str, Any] = {"learner_decision": decision}
    for key in ("essay_slug", "section_anchor_slug", "transcript", "rationale", "demonstrated"):
        out[key], err = _text(entry, key, where)
        if err is not None:
            return None, err

    for key in ("section_version", "session_at"):
        out[key] = _parse_timestamp(entry.get(key))
        if out[key] is None:
            return None, api_error(
                "VALIDATION_ERROR", f"{where}.{key} is required and must be an ISO-8601 timestamp with a UTC offset"
            )

    level = entry.get("level")
    if not isinstance(level, int) or isinstance(level, bool) or not 1 <= level <= MAX_LEVEL:
        return None, api_error("VALIDATION_ERROR", f"{where}.level is required and must be an integer 1-{MAX_LEVEL}")
    out["level"] = level

    rec = entry.get("recommendation")
    if rec not in VALID_RECOMMENDATIONS:
        return None, api_error(
            "VALIDATION_ERROR", f"{where}.recommendation is required and must be one of: {', '.join(VALID_RECOMMENDATIONS)}"
        )
    out["recommendation"] = rec

    gaps_raw = entry.get("gaps", [])
    if not isinstance(gaps_raw, list):
        return None, api_error("VALIDATION_ERROR", f"{where}.gaps must be a list")
    gaps: list[dict[str, Any]] = []
    for i, g in enumerate(gaps_raw):
        if (
            not isinstance(g, dict)
            or not isinstance(g.get("text"), str) or not g["text"].strip()
            or not isinstance(g.get("serious"), bool)
        ):
            return None, api_error(
                "VALIDATION_ERROR", f'{where}.gaps[{i}] must be {{"text": non-empty string, "serious": boolean}}'
            )
        gaps.append({"text": g["text"].strip(), "serious": g["serious"]})
    out["gaps"] = gaps

    # Serious conceptual gaps must prevent an 'advance' recommendation.
    if rec == "advance" and any(g["serious"] for g in gaps):
        return None, api_error(
            "VALIDATION_ERROR",
            f"{where}: recommendation 'advance' contradicts a serious gap; the reply must recommend 'continue'",
        )

    suggested = entry.get("unguided_suggested", False)
    if not isinstance(suggested, bool):
        return None, api_error("VALIDATION_ERROR", f"{where}.unguided_suggested must be a boolean")
    out["unguided_suggested"] = suggested
    return out, None


# ── Import DB core ────────────────────────────────────────────────────────────

def import_guided_session(cur: Any, r: dict[str, Any]) -> tuple[dict[str, Any] | None, Any]:
    """
    Resolve slugs (NOT_FOUND on a miss), enforce sequential levels, append the
    session and apply the learner-confirmed transition. Caller commits/rolls back.
    A level above completed + 1 is a VALIDATION_ERROR; a level at or below the
    completed one is recorded as practice and changes nothing.
    """
    cur.execute(
        """
        select s.id, e.id as essay_id
        from essaycards.essays e
        join essaycards.essay_sections s on s.essay_id = e.id
        where e.slug = %s and s.anchor_slug = %s
        """,
        (r["essay_slug"], r["section_anchor_slug"]),
    )
    sec = cur.fetchone()
    if not sec:
        return None, api_error(
            "NOT_FOUND",
            f"no section '{r['section_anchor_slug']}' found in essay '{r['essay_slug']}'",
            status=404,
        )
    section_id = sec["id"]

    cur.execute(
        "insert into essaycards.section_oral_state (section_id) values (%s) on conflict (section_id) do nothing",
        (section_id,),
    )
    state = _load_state(cur, section_id, lock=True)
    completed = current_level(state)
    level = r["level"]
    if level > completed + 1:
        return None, api_error(
            "VALIDATION_ERROR",
            f"level {level} is not available: guided levels advance sequentially (completed {completed})",
        )

    advances = r["learner_decision"] == "advance" and level == completed + 1
    cur.execute(
        """
        insert into essaycards.section_guided_sessions
            (essay_id, section_id, level, section_version_at, session_at, transcript, recommendation,
             rationale, demonstrated, gaps, unguided_suggested, learner_decision, advanced_to)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        returning id
        """,
        (
            sec["essay_id"], section_id, level, r["section_version"], r["session_at"], r["transcript"],
            r["recommendation"], r["rationale"], r["demonstrated"], Json(r["gaps"]),
            r["unguided_suggested"], r["learner_decision"], level if advances else None,
        ),
    )
    session_id = cur.fetchone()["id"]

    effects: list[dict[str, Any]] = []
    if advances:
        if not state["guided_passed"]:
            cur.execute(
                """
                update essaycards.section_oral_state
                set guided_level = %s, guided_passed = true, guided_pass_source = 'guided_level',
                    guided_passed_at = %s, updated_at = now()
                where section_id = %s
                """,
                (level, r["session_at"], section_id),
            )
            effects.append({"effect": "section_guided_unlocked", "section_id": str(section_id)})
        else:
            cur.execute(
                "update essaycards.section_oral_state set guided_level = %s, updated_at = now() where section_id = %s",
                (level, section_id),
            )
        effects.append({"effect": "section_guided_level_advanced", "section_id": str(section_id), "level": level})

    return {
        "id": str(session_id),
        "section_id": str(section_id),
        "essay_id": str(sec["essay_id"]),
        "level": level,
        "recommendation": r["recommendation"],
        "learner_decision": r["learner_decision"],
        "advanced_to": level if advances else None,
        "completed_level": level if advances else completed,
        "unguided_suggested": r["unguided_suggested"] or (advances and level >= 5),
        "effects": effects,
    }, None
