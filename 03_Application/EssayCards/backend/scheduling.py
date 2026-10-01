"""
Spaced-repetition scheduling — FSRS-only (Sprint12_FSRSAndUXOverhaul).

Sprint10_DualSchedulerAB introduced FSRS alongside the original floor/doubling
"Classic" formula as a permanent 50/50 A/B experiment. Sprint12 makes FSRS the
SOLE scheduler: ClassicScheduler, compute_next_due_at, decide_scheduler_assignment,
EXPERIMENT_VERSION, _SCHEDULER_ASSIGNMENT_REASONS, _AGAIN_INTERVAL and _FLOORS are
all removed (10_architecture.json internal_flow step 5) — their removal was
verified safe only after the migration (backend/migrate_fsrs_state.py) and the
FSRS review-dispatch/rating-mapping path were confirmed correct by the test
suite (contracts.invariants "VERIFY BEFORE REMOVING DEAD CODE").

VALID_GRADES and SchedulerResult survive unchanged — still meaningful with one
scheduler. FSRSScheduler is unchanged from Sprint10.

New this sprint: DESIRED_RETENTION (a module constant, read once from
ESSAYCARDS_FSRS_DESIRED_RETENTION at import time, default 0.9) and
estimate_initial_fsrs_state — a pure, independently unit-testable function that
synthesizes initial FSRS state for a card with real pre-FSRS review history but
no native FSRS state yet. This is a documented APPROXIMATION, not a
reconstruction of real review history (R-OPS-BP-01) — see its own docstring and
10_architecture.json §contracts.invariants' "LEGACY FSRS-STATE MIGRATION
APPROXIMATION" entry.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

import fsrs

VALID_GRADES = frozenset({"again", "hard", "good", "easy"})

# FSRS desired retention is a server-side setting, not a per-request value
# (10_architecture.json §contracts.invariants) — read ONCE at import time into
# a module constant, used to construct both the module-level fsrs.Scheduler
# singleton below AND (as the SAME value) estimate_initial_fsrs_state's
# stability-inversion math. No UI exposure this sprint.
DESIRED_RETENTION = float(os.environ.get("ESSAYCARDS_FSRS_DESIRED_RETENTION", "0.9"))


class SchedulerResult(NamedTuple):
    """Return shape for FSRSScheduler.review.

    next_due_at / review_interval are the ONLY values review_flashcard writes
    through the existing flashcard_review_state columns. extra_state is FSRS's
    own stability/difficulty/state/step/last_review_at/raw_state, persisted
    separately (essaycards.fsrs_card_state), never through review_interval.
    """

    next_due_at: datetime
    review_interval: timedelta
    extra_state: dict


# Module-level fsrs.Scheduler(desired_retention=DESIRED_RETENTION), library-
# default parameters/learning_steps/relearning_steps (FSRS-6). Constructed once
# at import time and safely reused across concurrent requests: Scheduler.review_card
# is a pure function of its (card, rating, review_datetime) arguments — it
# returns a NEW Card object and never mutates the Card passed in, and the
# Scheduler instance itself carries no per-call mutable state (only its
# immutable construction-time config). Unchanged rationale from Sprint10.
_FSRS_SCHEDULER = fsrs.Scheduler(desired_retention=DESIRED_RETENTION)

# Direct 1:1 name match — no numeric or semantic translation.
_GRADE_TO_FSRS_RATING: dict[str, "fsrs.Rating"] = {
    "again": fsrs.Rating.Again,
    "hard": fsrs.Rating.Hard,
    "good": fsrs.Rating.Good,
    "easy": fsrs.Rating.Easy,
}


class FSRSScheduler:
    """Loads or creates an fsrs.Card, drives the module-level fsrs.Scheduler,
    and returns next_due_at/review_interval plus FSRS's own memory state as
    extra_state. Unchanged from Sprint10_DualSchedulerAB — now the only
    scheduler dispatched to, unconditionally, by every review."""

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


# ── Legacy FSRS-state migration approximation ───────────────────────────────
#
# FSRS-6's own interval<->stability relation, as implemented by
# fsrs.scheduler.Scheduler._next_interval:
#
#     next_interval_days = (stability_days / FACTOR) * (desired_retention**(1/DECAY) - 1)
#
# where FACTOR/DECAY are derived from the Scheduler's own trainable parameter
# vector: DECAY = -parameters[20], FACTOR = 0.9 ** (1 / DECAY) - 1 (confirmed
# by reading the installed fsrs==6.3.2 source, backend/scheduling.py's own
# deferral instruction — NOTE: these are NOT the fixed "19/81" / "-0.5"
# constants from older FSRS releases; FSRS-6's decay is itself one of the
# model's trainable parameters, defaulting to FSRS_DEFAULT_DECAY=0.1542).
# Rather than hand-copy numeric literals that would silently drift from
# whatever parameter vector the module-level _FSRS_SCHEDULER actually uses
# (library defaults here, but a future sprint could pass a trained vector),
# FACTOR/DECAY are read directly off the live Scheduler instance's own
# precomputed attributes — guaranteed identical to the formula it actually
# runs, and automatically correct across a library/parameter version bump.
_FSRS6_DECAY: float = _FSRS_SCHEDULER._DECAY
_FSRS6_FACTOR: float = _FSRS_SCHEDULER._FACTOR

# The library's own minimum stability floor (fsrs.scheduler.STABILITY_MIN),
# applied here so a very short review_interval never inverts to a non-positive
# stability.
_MIN_STABILITY_DAYS: float = fsrs.scheduler.STABILITY_MIN


def estimate_initial_fsrs_state(
    review_interval: timedelta,
    last_reviewed_at: datetime,
    desired_retention: float = DESIRED_RETENTION,
) -> dict:
    """
    Synthesizes initial FSRS state for a flashcard with real pre-FSRS review
    history but no native FSRS state yet — backend/migrate_fsrs_state.py's
    one-time legacy backfill is the sole caller. Pure function, no DB access.

    THIS IS A DOCUMENTED APPROXIMATION, NOT A RECONSTRUCTION of the card's
    true memory state (R-OPS-BP-01) — no complete per-review rating history
    exists anywhere in this schema to replay (review_events is Sprint10-only
    and append-only; nothing predates it). Every field below is inferred from
    the single number this app has always kept: the card's current
    review_interval.

    (a) stability — inverts FSRS-6's own interval-from-stability-and-retention
        formula (see module comment above) using the card's CURRENT
        review_interval as the target interval, floored at
        _MIN_STABILITY_DAYS to avoid a non-positive value for a very short
        interval.
    (b) difficulty — no backward-derivable signal exists (depends on per-review
        grade history this app has never persisted), so it is obtained by
        running the module-level FSRS Scheduler's own review_card ONCE on a
        fresh fsrs.Card() with a neutral Rating.Good — exactly what a
        brand-new card's difficulty becomes after one average review — rather
        than hand-deriving a numeric constant, so it stays correct
        automatically if the installed library version ever changes. The
        bootstrap review is timestamped at the card's own last_reviewed_at
        (not "now", the migration's run time) so the synthesized state is a
        deterministic function of the card's own history alone.
    (c) fsrs_state — 2 (Review) if review_interval >= 24h else 1 (Learning),
        matching this app's existing established/learning threshold.
    (d) step — null for Review-state, 0 for Learning-state.
    (e) last_review_at — the card's existing last_reviewed_at, used as-is,
        never recomputed.
    (f) raw_state — produced by constructing an fsrs.Card with these fields
        and calling its own .to_dict() (never a hand-assembled dict literal),
        so it stays structurally valid for Card.from_dict() on every
        subsequent real review regardless of library internals.

    Never writes next_due_at/review_interval/last_reviewed_at for the card —
    those are read-only inputs here, never targets (DUE DATES PRESERVED).
    """
    last_reviewed_at_utc = last_reviewed_at.astimezone(timezone.utc)

    interval_days = max(review_interval.total_seconds(), 0.0) / 86400.0
    denom = desired_retention ** (1 / _FSRS6_DECAY) - 1
    stability_days = (
        (interval_days * _FSRS6_FACTOR / denom) if denom else _MIN_STABILITY_DAYS
    )
    stability_days = max(stability_days, _MIN_STABILITY_DAYS)

    bootstrap_card, _log = _FSRS_SCHEDULER.review_card(
        fsrs.Card(), fsrs.Rating.Good, review_datetime=last_reviewed_at_utc,
    )
    difficulty = bootstrap_card.difficulty

    fsrs_state = 2 if review_interval >= timedelta(hours=24) else 1
    step = None if fsrs_state == 2 else 0

    card = fsrs.Card(
        state=fsrs.State(fsrs_state),
        step=step,
        stability=stability_days,
        difficulty=difficulty,
        due=last_reviewed_at_utc + review_interval,
        last_review=last_reviewed_at_utc,
    )

    return {
        "stability": stability_days,
        "difficulty": difficulty,
        "fsrs_state": fsrs_state,
        "step": step,
        "last_review_at": last_reviewed_at_utc,
        "raw_state": card.to_dict(),
    }
