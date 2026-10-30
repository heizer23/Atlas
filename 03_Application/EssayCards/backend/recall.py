"""
Oral recall — independent FSRS-scheduled unguided assessments (Sprint16_RecallFSRS).

Recall is the second learning dimension: guided learning builds understanding
(backend/guided.py, no FSRS), recall is the learner's independent, cold
reconstruction of a section or an essay, maintained by spaced repetition. It is
scheduled with its own FSRS state (recall_state / recall_reviews), fully
separate from flashcard scheduling.

Single home of: the grading rubric (shipped inside unguided export packages so
the prompt cannot drift), import-evidence validation (incl. the critical cap:
prompted recall can never be Good/Easy), the status derivation, the review
transition and the legacy seeding helper. No HTTP. The caller owns the
transaction (statements on `cur`).

Time authority (R-CON-AL-06): scheduling uses the server's `now()`, not the
ChatGPT-supplied examined_at (a model does not reliably know the date); the
latter is stored as evidence only.

Status (derived, never stored):
  not_established  no successful (hard/good/easy) review yet
  due              established AND (next_due_at <= now() OR the last rating was 'again')
  current          established AND not due
A lapse (again) on an established item stays "due" until a successful review;
FSRS still schedules the next interval from the lapse.
"""

from __future__ import annotations

from typing import Any

from psycopg2.extras import Json

from backend.scheduling import recall_scheduler
from platform_errorhandling import api_error

RATINGS = ("again", "hard", "good", "easy")
MAX_FOLLOWUPS = 2

# Shipped in unguided packages as `recall_grading`; frontend/prompts.ts renders
# the rules from it. Keep in step with validate_evidence().
GRADING = {
    "ratings": {
        "easy": "Complete, accurate, fluent reconstruction. Essential material recalled spontaneously. No prompting required.",
        "good": "Essential argument spine and nuggets recalled independently. Minor omissions or hesitation are acceptable. No prompting was needed to retrieve any important missing material.",
        "hard": "An important element was initially omitted; a neutral follow-up question was needed; the learner then recalled the missing material.",
        "again": "An important element could not be recalled even after prompting, or the reconstruction contained a substantial misunderstanding or omission.",
    },
    "critical_rule": "If an important element required a follow-up question to retrieve, the maximum rating is hard. A clarification question about something already recalled independently does not impose this cap.",
    "max_followups": MAX_FOLLOWUPS,
}

# SQL: expects `essaycards.recall_state rs` (may be null-joined).
RECALL_STATUS_SQL = """
case
  when rs.id is null or rs.established_at is null then 'not_established'
  when rs.last_rating = 'again' or rs.next_due_at <= now() then 'due'
  else 'current'
end
"""


# ── Import-evidence validation ───────────────────────────────────────────────

def _str_list(entry: dict[str, Any], key: str, idx: int) -> tuple[list[str] | None, Any]:
    raw = entry.get(key, [])
    if raw is None:
        raw = []
    if not isinstance(raw, list) or any(not isinstance(x, str) or not x.strip() for x in raw):
        return None, api_error(
            "VALIDATION_ERROR", f"results[{idx}].recall.{key} must be a list of non-empty strings"
        )
    return [x.strip() for x in raw], None


def validate_evidence(recall: Any, idx: int) -> tuple[dict[str, Any] | None, Any]:
    """
    Validates results[idx].recall and returns (evidence, None) or (None, ApiError).

    evidence = {rating, independent_elements, prompted_elements, missing_elements,
                misunderstandings, followups_asked}
    Rules (the grading rubric, enforced):
      easy/good  no prompted elements, none missing, no misunderstandings
      hard       >= 1 prompted element (recalled after a follow-up), none missing
      again      >= 1 missing element or misunderstanding
      any        prompted/missing elements imply >= 1 follow-up; followups_asked <= 2
    """
    if not isinstance(recall, dict):
        return None, api_error(
            "VALIDATION_ERROR",
            f"results[{idx}].recall is required for unguided results and must be an object "
            "(rating, independent_elements, prompted_elements, missing_elements, misunderstandings, followups_asked)",
        )
    rating = recall.get("rating")
    if rating not in RATINGS:
        return None, api_error(
            "VALIDATION_ERROR", f"results[{idx}].recall.rating is required and must be one of: {', '.join(RATINGS)}"
        )
    lists: dict[str, list[str]] = {}
    for key in ("independent_elements", "prompted_elements", "missing_elements", "misunderstandings"):
        value, err = _str_list(recall, key, idx)
        if err is not None:
            return None, err
        lists[key] = value  # type: ignore[assignment]

    followups = recall.get("followups_asked", 0)
    if not isinstance(followups, int) or isinstance(followups, bool) or not 0 <= followups <= MAX_FOLLOWUPS:
        return None, api_error(
            "VALIDATION_ERROR",
            f"results[{idx}].recall.followups_asked must be an integer between 0 and {MAX_FOLLOWUPS}",
        )

    prompted, missing, wrong = lists["prompted_elements"], lists["missing_elements"], lists["misunderstandings"]
    if (prompted or missing) and followups < 1:
        return None, api_error(
            "VALIDATION_ERROR",
            f"results[{idx}].recall: prompted/missing elements imply followups_asked >= 1",
        )
    if rating in ("good", "easy") and (prompted or missing or wrong):
        return None, api_error(
            "VALIDATION_ERROR",
            f"results[{idx}].recall: rating '{rating}' is not allowed when an important element needed a follow-up, "
            "was missing, or was misunderstood — prompted recall caps the rating at 'hard'",
        )
    if rating == "hard" and (not prompted or missing):
        return None, api_error(
            "VALIDATION_ERROR",
            f"results[{idx}].recall: rating 'hard' requires at least one prompted element and no missing elements "
            "(an element still missing after prompting is 'again')",
        )
    if rating == "again" and not (missing or wrong):
        return None, api_error(
            "VALIDATION_ERROR",
            f"results[{idx}].recall: rating 'again' requires a missing element or a misunderstanding",
        )
    return {"rating": rating, **lists, "followups_asked": followups}, None


# ── Review transition ────────────────────────────────────────────────────────

def apply_recall_review(
    cur: Any,
    scope: str,
    essay_id: str,
    section_id: str | None,
    evidence: dict[str, Any],
    examined_at: Any,
    question: str,
    answer_transcript: str,
    feedback: str | None,
    section_version: Any = None,
    nugget_versions: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    One recall assessment: lock/create the recall_state row, advance FSRS with
    the server clock, append the recall_reviews row. Returns the response row.
    """
    rating = evidence["rating"]
    key_col, key_val = ("section_id", section_id) if scope == "section" else ("essay_id", essay_id)
    cur.execute(
        f"select * from essaycards.recall_state where scope = %s and {key_col} = %s for update",
        (scope, key_val),
    )
    row = cur.fetchone()
    cur.execute("select now() as now")
    now = cur.fetchone()["now"]

    result = recall_scheduler().review(
        rating, row["last_reviewed_at"] if row else None, now, {"raw_state": row["raw_state"]} if row else None
    )
    was_established = bool(row and row["established_at"])
    successful = rating != "again"
    lapse = was_established and not successful

    if row:
        cur.execute(
            """
            update essaycards.recall_state
            set raw_state = %s, last_rating = %s, last_reviewed_at = %s, next_due_at = %s,
                established_at = coalesce(established_at, case when %s then %s end),
                review_count = review_count + 1, lapse_count = lapse_count + %s, updated_at = now()
            where id = %s
            """,
            (Json(result.extra_state["raw_state"]), rating, now, result.next_due_at,
             successful, now, 1 if lapse else 0, row["id"]),
        )
        state_id = row["id"]
    else:
        cur.execute(
            """
            insert into essaycards.recall_state
                (scope, essay_id, section_id, raw_state, established_at, last_rating, last_reviewed_at,
                 next_due_at, review_count, lapse_count, source)
            values (%s, %s, %s, %s, %s, %s, %s, %s, 1, 0, 'review')
            returning id
            """,
            (scope, essay_id, section_id, Json(result.extra_state["raw_state"]),
             now if successful else None, rating, now, result.next_due_at),
        )
        state_id = cur.fetchone()["id"]

    cur.execute(
        """
        insert into essaycards.recall_reviews
            (recall_state_id, essay_id, section_id, rating, examined_at, reviewed_at, question,
             answer_transcript, feedback, evidence, next_due_at, section_version_at, nugget_versions_at)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        returning id
        """,
        (state_id, essay_id, section_id, rating, examined_at, now, question, answer_transcript,
         feedback, Json(evidence), result.next_due_at, section_version,
         Json(nugget_versions) if nugget_versions is not None else None),
    )
    review_id = cur.fetchone()["id"]

    effect = (
        "recall_lapsed" if lapse
        else "recall_established" if successful and not was_established
        else "recall_reviewed" if successful
        else "recall_not_established"
    )
    return {
        "id": str(review_id),
        "rating": rating,
        "recall_status": "due" if lapse else ("not_established" if not (was_established or successful) else "current"),
        "next_due_at": result.next_due_at.isoformat(),
        "effects": [{"effect": effect, "scope": scope,
                     **({"section_id": str(section_id)} if section_id else {"essay_id": str(essay_id)})}],
    }


def recall_due_sql(extra_where: str = "") -> str:
    """
    One row per DUE recall item (aliases rs, e, s nullable). Columns feed
    GET /recall/due. Ordered most overdue first.
    """
    return f"""
    select rs.id, rs.scope, rs.essay_id, rs.section_id, e.title as essay_title, e.category,
           s.heading as section_heading, s.anchor_slug, rs.last_reviewed_at, rs.next_due_at,
           rs.last_rating, rs.review_count, rs.lapse_count
    from essaycards.recall_state rs
    join essaycards.essays e on e.id = rs.essay_id
    left join essaycards.essay_sections s on s.id = rs.section_id
    where rs.established_at is not null
      and (rs.last_rating = 'again' or rs.next_due_at <= now())
      {extra_where}
    order by rs.next_due_at asc, e.sort_index asc, s.order_index asc nulls first
    """
