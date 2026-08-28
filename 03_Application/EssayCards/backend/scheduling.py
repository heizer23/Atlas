"""
Spaced-repetition scheduling — pure, independently unit-testable logic.

Implements the exact floor/doubling formula from
Sprint01_Core/10_architecture.json §contracts.invariants:

  again              -> next_due_at = now + 5 seconds, flat (no floor/doubling)
  hard / good / easy -> elapsed = null if last_reviewed_at is null else (now - last_reviewed_at)
                        interval = floor if elapsed is null else max(floor, 2 * elapsed)
                        next_due_at = now + interval

No DB or HTTP dependency — this module has no knowledge of flashcards, routers,
or Postgres. Callers (backend/routers/flashcards.py) supply `now` from a single
Postgres `select now()` read (R-CON-AL-06 time authority) and never from the
app server's local clock.
"""

from datetime import datetime, timedelta

VALID_GRADES = frozenset({"again", "hard", "good", "easy"})

_AGAIN_INTERVAL = timedelta(seconds=5)

_FLOORS: dict[str, timedelta] = {
    "hard": timedelta(minutes=1),
    "good": timedelta(minutes=20),
    "easy": timedelta(days=1),
}


def compute_next_due_at(
    grade: str,
    last_reviewed_at: datetime | None,
    now: datetime,
) -> datetime:
    """
    Compute the next_due_at timestamp for a review event.

    `grade` must be one of VALID_GRADES — the caller (the review router) is
    responsible for that validation and returning ApiError VALIDATION_ERROR
    before this function is ever called. This function still raises ValueError
    on an invalid grade as a defensive check, since it is a pure function that
    may be called directly (e.g. from tests) without going through the router.
    """
    if grade not in VALID_GRADES:
        raise ValueError(f"grade must be one of {sorted(VALID_GRADES)}, got {grade!r}")

    if grade == "again":
        return now + _AGAIN_INTERVAL

    floor = _FLOORS[grade]
    if last_reviewed_at is None:
        interval = floor
    else:
        elapsed = now - last_reviewed_at
        interval = max(floor, 2 * elapsed)
    return now + interval
