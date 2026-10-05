"""
Revalidation primitives (Sprint14_SectionProgressionAndRevalidation).

A failed unguided full-essay oral (while the essay was Violet) flags every
reviewed card of that essay with flashcard_review_state.needs_revalidation.
A flagged card is checked once through POST /flashcards/{id}/review:
  - correct   -> flag cleared, FSRS state untouched, audit row 'preserved'
  - incorrect -> flag cleared, normal FSRS failure path, audit row 'failed'

This module holds the grade rule, the flag/unflag statements and the audit
insert. It is imported by backend/oral_state.py and backend/routers/flashcards.py
and imports neither. The caller owns the transaction.
"""

from __future__ import annotations

from typing import Any

# Grades treated as an INCORRECT revalidation answer; every other valid grade
# (hard / good / easy) counts as correct. Single definition.
REVALIDATION_FAIL_GRADES = ("again",)


def is_revalidation_correct(grade: str) -> bool:
    return grade not in REVALIDATION_FAIL_GRADES


def flag_essay_cards_for_revalidation(cur: Any, essay_id: str) -> int:
    """
    needs_revalidation = true for every card of the essay that has been
    reviewed at least once. Touches no other column (FSRS state, due dates,
    intervals and timestamps are deliberately left alone). Returns the number
    of cards flagged.
    """
    cur.execute(
        """
        update essaycards.flashcard_review_state frs
        set needs_revalidation = true
        from essaycards.flashcards f
        where f.id = frs.flashcard_id
          and f.essay_id = %s
          and frs.last_reviewed_at is not null
        """,
        (essay_id,),
    )
    return cur.rowcount


def clear_revalidation_flag(cur: Any, flashcard_id: str) -> None:
    """Clear the flag for one card. Writes no other column."""
    cur.execute(
        "update essaycards.flashcard_review_state set needs_revalidation = false where flashcard_id = %s",
        (flashcard_id,),
    )


def record_revalidation_event(cur: Any, flashcard_id: str, essay_id: str, grade: str, outcome: str) -> None:
    """Append one revalidation_events row; checked_at defaults to server now()."""
    cur.execute(
        """
        insert into essaycards.revalidation_events (flashcard_id, essay_id, grade, outcome)
        values (%s, %s, %s, %s)
        """,
        (flashcard_id, essay_id, grade, outcome),
    )
