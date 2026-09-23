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

compute_next_due_at and VALID_GRADES are UNCHANGED by Sprint10_DualSchedulerAB
(binding invariant — see Sprint10_DualSchedulerAB/10_architecture.json
§contracts.invariants). Sprint10 adds, below the original formula, a second
scheduling algorithm (FSRS, via the `fsrs` PyPI package) as a wrapper that
never edits this function's logic, plus the permanent 50/50 experiment
assignment mechanism. Both ClassicScheduler and FSRSScheduler write exactly
next_due_at/review_interval through the existing flashcard_review_state
columns — FSRS's own stability/difficulty/state is a SEPARATE, additional
concept (essaycards.fsrs_card_state) and is never confused with or
substituted for review_interval.
"""

import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

import fsrs

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


# ── Sprint10_DualSchedulerAB — scheduler dispatch seam ──────────────────────


class SchedulerResult(NamedTuple):
    """Common return shape for both scheduler adapters below.

    next_due_at / review_interval are the ONLY values review_flashcard writes
    through the existing flashcard_review_state columns — identical for both
    schedulers. extra_state is scheduler-private (None for Classic; FSRS's
    stability/difficulty/state/step/last_review_at/raw_state for FSRS) and is
    persisted separately, never through review_interval.
    """

    next_due_at: datetime
    review_interval: timedelta
    extra_state: dict | None


class ClassicScheduler:
    """Thin pass-through to the unchanged compute_next_due_at. Ignores
    existing_state entirely — Classic persists no state beyond the existing
    three flashcard_review_state columns."""

    def review(
        self,
        grade: str,
        last_reviewed_at: datetime | None,
        now: datetime,
        existing_state: dict | None = None,
    ) -> SchedulerResult:
        next_due_at = compute_next_due_at(grade, last_reviewed_at, now)
        return SchedulerResult(next_due_at, next_due_at - now, None)


# Module-level fsrs.Scheduler(desired_retention=0.9), library-default
# parameters/learning_steps/relearning_steps (FSRS-6). Constructed once at
# import time and safely reused across concurrent requests: confirmed against
# the installed fsrs==6.3.2 source that Scheduler.review_card is a pure
# function of its (card, rating, review_datetime) arguments — it returns a
# NEW Card object and never mutates the Card passed in, and the Scheduler
# instance itself carries no per-call mutable state (only its immutable
# construction-time config: parameters/desired_retention/learning_steps/
# relearning_steps/maximum_interval/enable_fuzzing). Verified interactively
# per 10_architecture.json §deferrals.application_implementer before relying
# on the singleton under FastAPI's concurrent request handling.
_FSRS_SCHEDULER = fsrs.Scheduler(desired_retention=0.9)

# Direct 1:1 name match — no numeric or semantic translation.
_GRADE_TO_FSRS_RATING: dict[str, "fsrs.Rating"] = {
    "again": fsrs.Rating.Again,
    "hard": fsrs.Rating.Hard,
    "good": fsrs.Rating.Good,
    "easy": fsrs.Rating.Easy,
}


class FSRSScheduler:
    """Loads or creates an fsrs.Card, drives the module-level fsrs.Scheduler,
    and returns next_due_at/review_interval (through the SAME interface
    Classic uses) plus FSRS's own memory state as extra_state."""

    def review(
        self,
        grade: str,
        last_reviewed_at: datetime | None,
        now: datetime,
        existing_state: dict | None = None,
    ) -> SchedulerResult:
        # R-CON-AL-06: `now` is a representation conversion of the single
        # Postgres `select now()` read already used by review_flashcard — not
        # a second time source. py-fsrs raises ValueError on a naive
        # datetime, so every datetime handed to it is normalized to exactly
        # timezone.utc first.
        now_utc = now.astimezone(timezone.utc)

        card = (
            fsrs.Card.from_dict(existing_state["raw_state"])
            if existing_state
            else fsrs.Card()
        )
        rating = _GRADE_TO_FSRS_RATING[grade]
        new_card, _log = _FSRS_SCHEDULER.review_card(card, rating, review_datetime=now_utc)

        next_due_at = new_card.due
        review_interval = next_due_at - now_utc
        extra_state = {
            "stability": new_card.stability,
            "difficulty": new_card.difficulty,
            "fsrs_state": int(new_card.state),
            "step": new_card.step,
            "last_review_at": new_card.last_review,
            "raw_state": new_card.to_dict(),
        }
        return SchedulerResult(next_due_at, review_interval, extra_state)


# Closed, fixed vocabulary (R-CON-AL-01/03) — exactly these four values. The
# CHECK constraint in schema.sql is the actual enforcement point; this set is
# wired into decide_scheduler_assignment as an active defensive assertion, so
# it is a real guard rather than dead code.
_SCHEDULER_ASSIGNMENT_REASONS = frozenset({
    "new_card_random",
    "migrated_never_reviewed_random",
    "legacy_retained_classic",
    "assignment_disabled_classic",
})

# Written into flashcard_review_state.experiment_version at every assignment
# (new-card and migration). Canonical source for this literal — schema.sql's
# column DEFAULT and both migration UPDATEs must stay in sync with it; a
# future version bump updates all three occurrences together.
EXPERIMENT_VERSION = "sprint10_v1"


def _experiment_enabled() -> bool:
    """Read fresh from os.environ on EVERY call — never cached at import —
    so tests can monkeypatch ESSAYCARDS_FSRS_EXPERIMENT_ENABLED per-test."""
    raw = os.environ.get("ESSAYCARDS_FSRS_EXPERIMENT_ENABLED", "true")
    return raw.strip().lower() not in ("false", "0", "no", "off", "")


def decide_scheduler_assignment(
    flashcard_id: str,
    migrated_never_reviewed: bool = False,
) -> tuple[str, str]:
    """
    Decide a flashcard's PERMANENT scheduler assignment. Called exactly once
    per card, at creation (the existing `if was_inserted:` gate at all three
    insertion call sites) or by the one-time migration backfill in
    schema.sql. Never called on update/re-ingest/regeneration, and no
    endpoint request body anywhere accepts a scheduler field — this is
    exclusively a server-side side effect.

    Kill switch disabled -> ('classic', 'assignment_disabled_classic')
    unconditionally. Otherwise a stable hash of flashcard_id decides between
    'classic'/'fsrs' (naturally balanced ~50/50 in expectation, deterministic
    for the same id, no stored RNG seed), with reason 'new_card_random' for a
    genuinely new card or 'migrated_never_reviewed_random' for a pre-existing
    but never-reviewed card assigned at migration time.
    """
    if not _experiment_enabled():
        reason = "assignment_disabled_classic"
        assert reason in _SCHEDULER_ASSIGNMENT_REASONS
        return "classic", reason

    digest = hashlib.sha256(str(flashcard_id).encode("utf-8")).digest()
    scheduler = "classic" if digest[0] % 2 == 0 else "fsrs"
    reason = "migrated_never_reviewed_random" if migrated_never_reviewed else "new_card_random"
    assert reason in _SCHEDULER_ASSIGNMENT_REASONS
    return scheduler, reason
