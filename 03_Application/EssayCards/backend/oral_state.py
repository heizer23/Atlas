"""
Oral pass rule and oral-state transitions (Sprint14_SectionProgressionAndRevalidation).

Single home of:
  - the pass rule (SCORE_MAX, PASS_THRESHOLD_PERCENT, is_passing_score)
  - section_oral_state / essay_oral_state GUIDED transitions

No HTTP, no request parsing. The caller owns the transaction (these
functions only issue statements against `cur`). Traffic-light colors are
never stored here — they are derived in backend/progress.py.

Sprint16_RecallFSRS: unguided attempts no longer pass through here — they are
FSRS-scheduled recall reviews (backend/recall.py). The unguided_* columns and the
unguided-essay failure cascade are retired; legacy values remain as history and
seed recall_state once (backend/migrate_recall_state.py).

Time authority (R-CON-AL-06): *_passed_at = the attempt's examined_at
(external, supplied by the examiner reply); unguided_invalidated_at = server
now(). Transitions apply in server import order, not examined_at order.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

SCORE_MAX = 6
PASS_THRESHOLD_PERCENT = 70


def is_passing_score(score: int) -> bool:
    """Integer arithmetic: score/SCORE_MAX*100 >= PASS_THRESHOLD_PERCENT. On 0-6 that is score >= 5."""
    return score * 100 >= PASS_THRESHOLD_PERCENT * SCORE_MAX


def scoring_echo() -> dict:
    """The pass rule as echoed into export packages, so prompts never hard-code it."""
    return {
        "score_max": SCORE_MAX,
        "pass_threshold_percent": PASS_THRESHOLD_PERCENT,
        "min_passing_score": min(sc for sc in range(SCORE_MAX + 1) if is_passing_score(sc)),
    }


def score_percent(score: int) -> float:
    """Response echo only — never used for the verdict."""
    return round(score / SCORE_MAX * 100, 1)


def apply_section_attempt(
    cur: Any, section_id: str, exam_type: str, score: int, passed: bool, examined_at: datetime
) -> list[dict[str, Any]]:
    """
    Upsert section_oral_state for one section-scope attempt. A failing attempt
    only updates *_latest_score. Guided pass is sticky. Returns effects.
    """
    cur.execute(
        "insert into essaycards.section_oral_state (section_id) values (%s) on conflict (section_id) do nothing",
        (section_id,),
    )
    cur.execute(
        "select guided_passed, unguided_passed from essaycards.section_oral_state "
        "where section_id = %s for update",
        (section_id,),
    )
    prior = cur.fetchone()
    effects: list[dict[str, Any]] = []

    if exam_type == "guided":
        if passed:
            cur.execute(
                """
                update essaycards.section_oral_state
                set guided_passed = true, guided_pass_source = 'exam', guided_passed_at = %s,
                    guided_latest_score = %s, updated_at = now()
                where section_id = %s
                """,
                (examined_at, score, section_id),
            )
            if not prior["guided_passed"]:
                effects.append({"effect": "section_guided_unlocked", "section_id": str(section_id)})
        else:
            cur.execute(
                "update essaycards.section_oral_state set guided_latest_score = %s, updated_at = now() "
                "where section_id = %s",
                (score, section_id),
            )
    return effects


def apply_essay_attempt(
    cur: Any, essay_id: str, exam_type: str, score: int, passed: bool, examined_at: datetime
) -> list[dict[str, Any]]:
    """
    Upsert essay_oral_state for one essay-scope attempt. Prior state is read
    via insert-if-absent then SELECT ... FOR UPDATE so two concurrent failing
    imports cascade once. A failing unguided attempt made while
    unguided_passed was true runs the FAILURE CASCADE; otherwise a failure
    only records the latest score.
    """
    cur.execute(
        "insert into essaycards.essay_oral_state (essay_id) values (%s) on conflict (essay_id) do nothing",
        (essay_id,),
    )
    cur.execute(
        "select guided_passed, unguided_passed from essaycards.essay_oral_state "
        "where essay_id = %s for update",
        (essay_id,),
    )
    prior = cur.fetchone()
    effects: list[dict[str, Any]] = []

    if exam_type == "guided":
        if passed:
            cur.execute(
                """
                update essaycards.essay_oral_state
                set guided_passed = true, guided_passed_at = %s, guided_latest_score = %s, updated_at = now()
                where essay_id = %s
                """,
                (examined_at, score, essay_id),
            )
            effects.append({"effect": "essay_guided_passed", "essay_id": str(essay_id)})
        else:
            cur.execute(
                "update essaycards.essay_oral_state set guided_latest_score = %s, updated_at = now() "
                "where essay_id = %s",
                (score, essay_id),
            )
    return effects
