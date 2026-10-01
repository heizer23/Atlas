"""
EssayCards — unit tests for backend.scheduling.

Pure function tests: no HTTP, no DB.

Sprint12_FSRSAndUXOverhaul removes every Classic/compute_next_due_at/
decide_scheduler_assignment scenario (that code no longer exists — FSRS is
the sole scheduler) and adds unit coverage for the new
estimate_initial_fsrs_state legacy-migration-approximation function.
"""

from datetime import datetime, timedelta, timezone

import fsrs
import pytest

from backend.scheduling import FSRSScheduler, estimate_initial_fsrs_state

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_fsrs_scheduler_review_maps_ratings_correctly():
    """Scenario: FSRS rating mapping. Each grade drives the corresponding
    fsrs.Rating by name into review_card — observable via the resulting
    interval/stability increasing monotonically Again < Hard < Good < Easy
    for a fresh card, exactly as the library's own rating semantics dictate."""
    results = {
        grade: FSRSScheduler().review(grade, None, NOW)
        for grade in ("again", "hard", "good", "easy")
    }
    intervals = [results[g].review_interval for g in ("again", "hard", "good", "easy")]
    assert intervals == sorted(intervals)
    assert intervals[0] < intervals[-1]

    stabilities = [results[g].extra_state["stability"] for g in ("again", "hard", "good", "easy")]
    assert stabilities == sorted(stabilities)


def test_fsrs_scheduler_review_fresh_card_when_no_existing_state():
    """Scenario: FSRS scheduler starts a fresh Card when existing_state is
    None — library defaults (Learning state) for a card's first-ever review,
    no error from the absence of prior state."""
    result = FSRSScheduler().review("good", None, NOW, existing_state=None)
    assert result.extra_state["fsrs_state"] == int(fsrs.State.Learning)
    assert result.extra_state["stability"] is not None
    assert result.extra_state["difficulty"] is not None
    assert result.extra_state["last_review_at"] == NOW
    assert result.extra_state["raw_state"]["card_id"] is not None


def test_fsrs_scheduler_review_loads_existing_state_from_raw_state():
    """Scenario: FSRS scheduler reconstructs from raw_state and produces
    state that reflects prior history, not a fresh card."""
    first = FSRSScheduler().review("good", None, NOW)
    existing_state = {"raw_state": first.extra_state["raw_state"]}

    later = NOW + timedelta(days=1)
    continued = FSRSScheduler().review("good", NOW, later, existing_state)

    fresh_at_later = FSRSScheduler().review("good", None, later, None)

    # A card with one prior "good" review has higher stability than a
    # freshly-created card reviewed "good" for the first time at the same
    # instant — genuine continuation, not a reset.
    assert continued.extra_state["stability"] > fresh_at_later.extra_state["stability"]
    assert continued.review_interval != fresh_at_later.review_interval


def test_fsrs_scheduler_review_normalizes_naive_and_nonutc_datetimes_to_utc():
    """Scenario: FSRS datetime handling is timezone-correct. Every datetime
    handed to py-fsrs is normalized to exactly timezone.utc first (R-CON-AL-06
    representation conversion of the single Postgres now() read), so a
    differently-offset tz-aware `now` still succeeds and produces a UTC due
    date."""
    offset_now = NOW.astimezone(timezone(timedelta(hours=5)))
    assert offset_now.tzinfo != timezone.utc  # constructed with a non-UTC offset

    result = FSRSScheduler().review("good", None, offset_now)
    assert result.next_due_at.tzinfo == timezone.utc
    # Same instant in time regardless of the input's original offset.
    assert result.next_due_at == FSRSScheduler().review("good", None, NOW).next_due_at


def test_fsrs_relearning_transitions_state_and_uses_relearning_step():
    """Scenario: FSRS relearning. Grading 'again' on a card already in the
    Review state (graduated) produces Relearning with a short relearning-step
    interval."""
    t = NOW
    existing_state = None
    result = None
    for _ in range(8):
        result = FSRSScheduler().review("good", t if existing_state else None, t, existing_state)
        existing_state = {"raw_state": result.extra_state["raw_state"]}
        t = result.next_due_at
        if result.extra_state["fsrs_state"] == int(fsrs.State.Review):
            break
    assert result.extra_state["fsrs_state"] == int(fsrs.State.Review)

    relearn = FSRSScheduler().review("again", t, t + timedelta(hours=1), existing_state)
    assert relearn.extra_state["fsrs_state"] == int(fsrs.State.Relearning)
    assert relearn.review_interval < timedelta(hours=1)


# ── Sprint12_FSRSAndUXOverhaul — estimate_initial_fsrs_state ────────────────

def test_estimate_initial_fsrs_state_established_card_yields_review_state():
    """Scenario: a card with review_interval >= 24h yields fsrs_state=2
    (Review), step=null."""
    state = estimate_initial_fsrs_state(timedelta(days=10), NOW - timedelta(days=10))
    assert state["fsrs_state"] == 2
    assert state["step"] is None
    assert state["last_review_at"] == NOW - timedelta(days=10)


def test_estimate_initial_fsrs_state_learning_card_yields_learning_state():
    """Scenario: a card with review_interval < 24h yields fsrs_state=1
    (Learning), step=0."""
    state = estimate_initial_fsrs_state(timedelta(hours=2), NOW - timedelta(hours=2))
    assert state["fsrs_state"] == 1
    assert state["step"] == 0


def test_estimate_initial_fsrs_state_stability_increases_with_longer_interval():
    """Scenario: a longer review_interval yields a larger synthesized
    stability, monotonically."""
    short = estimate_initial_fsrs_state(timedelta(days=1), NOW - timedelta(days=1))
    medium = estimate_initial_fsrs_state(timedelta(days=10), NOW - timedelta(days=10))
    long = estimate_initial_fsrs_state(timedelta(days=90), NOW - timedelta(days=90))
    assert short["stability"] < medium["stability"] < long["stability"]


def test_estimate_initial_fsrs_state_stability_is_positive_for_very_short_interval():
    """A very short (near-zero) review_interval must never invert to a
    non-positive stability — the implementation floors it at the library's
    own STABILITY_MIN."""
    state = estimate_initial_fsrs_state(timedelta(seconds=5), NOW - timedelta(seconds=5))
    assert state["stability"] > 0


def test_estimate_initial_fsrs_state_raw_state_round_trips_through_card_from_dict():
    """Scenario: the synthesized raw_state can be loaded by fsrs.Card.from_dict
    without error and used for a subsequent real review."""
    state = estimate_initial_fsrs_state(timedelta(days=5), NOW - timedelta(days=5))
    card = fsrs.Card.from_dict(state["raw_state"])
    assert card.stability == pytest.approx(state["stability"])
    assert card.difficulty == pytest.approx(state["difficulty"])
    assert int(card.state) == state["fsrs_state"]

    # Usable for a subsequent real review — no error, continuation not a reset.
    result = FSRSScheduler().review("good", state["last_review_at"], NOW, {"raw_state": state["raw_state"]})
    assert result.next_due_at > NOW


def test_estimate_initial_fsrs_state_never_touches_due_date_inputs():
    """The function is pure and read-only with respect to its inputs — it
    never mutates/returns next_due_at/review_interval/last_reviewed_at as
    targets, only uses them as inputs (DUE DATES PRESERVED)."""
    review_interval = timedelta(days=3)
    last_reviewed_at = NOW - timedelta(days=3)
    state = estimate_initial_fsrs_state(review_interval, last_reviewed_at)
    assert review_interval == timedelta(days=3)  # untouched
    assert last_reviewed_at == NOW - timedelta(days=3)  # untouched
    assert state["last_review_at"] == last_reviewed_at
