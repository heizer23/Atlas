"""
EssayCards — unit tests for backend.scheduling.

Pure function tests: no HTTP, no DB. Per Sprint01_Core/10_architecture.json
deferrals.test_writer, covers: again flat 5s; hard/good/easy first-time
(null last_reviewed_at) floor-only; hard/good/easy repeat review where
2*elapsed exceeds floor; hard/good/easy repeat review where floor exceeds
2*elapsed.

Sprint10_DualSchedulerAB adds: a boundary/tie-break case for
compute_next_due_at (still unchanged itself), plus unit coverage for
ClassicScheduler, FSRSScheduler, and decide_scheduler_assignment.
"""

from datetime import datetime, timedelta, timezone

import fsrs
import pytest

from backend.scheduling import (
    ClassicScheduler,
    FSRSScheduler,
    compute_next_due_at,
    decide_scheduler_assignment,
)

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

FLOORS = {
    "hard": timedelta(minutes=1),
    "good": timedelta(minutes=20),
    "easy": timedelta(days=1),
}


def test_again_is_flat_five_seconds_regardless_of_last_reviewed_at():
    assert compute_next_due_at("again", None, NOW) == NOW + timedelta(seconds=5)
    assert compute_next_due_at("again", NOW - timedelta(days=3), NOW) == NOW + timedelta(seconds=5)


@pytest.mark.parametrize("grade", ["hard", "good", "easy"])
def test_first_time_review_uses_floor_only(grade):
    result = compute_next_due_at(grade, None, NOW)
    assert result == NOW + FLOORS[grade]


@pytest.mark.parametrize("grade", ["hard", "good", "easy"])
def test_repeat_review_doubles_elapsed_when_it_exceeds_floor(grade):
    # 5 days elapsed comfortably exceeds all three floors (1min / 20min / 1day) once doubled.
    last_reviewed_at = NOW - timedelta(days=5)
    elapsed = NOW - last_reviewed_at
    result = compute_next_due_at(grade, last_reviewed_at, NOW)
    assert result == NOW + 2 * elapsed
    assert 2 * elapsed > FLOORS[grade]


@pytest.mark.parametrize("grade", ["hard", "good", "easy"])
def test_repeat_review_uses_floor_when_it_exceeds_doubled_elapsed(grade):
    last_reviewed_at = NOW - timedelta(seconds=1)
    result = compute_next_due_at(grade, last_reviewed_at, NOW)
    assert result == NOW + FLOORS[grade]
    assert FLOORS[grade] > 2 * (NOW - last_reviewed_at)


def test_invalid_grade_raises_value_error():
    with pytest.raises(ValueError):
        compute_next_due_at("maybe", None, NOW)


@pytest.mark.parametrize("grade", ["hard", "good", "easy"])
def test_floor_crossing_boundary_pins_max_tiebreak(grade):
    """Scenario: Boundary case at the exact floor crossing pins max()'s
    tie-break. elapsed chosen so 2*elapsed == the grade's floor exactly —
    max(floor, 2*elapsed) is deterministic (both operands equal), and the
    result must equal NOW + floor either way."""
    elapsed = FLOORS[grade] / 2
    last_reviewed_at = NOW - elapsed
    assert 2 * elapsed == FLOORS[grade]  # sanity check on the constructed boundary
    result = compute_next_due_at(grade, last_reviewed_at, NOW)
    assert result == NOW + FLOORS[grade]


# ── Sprint10_DualSchedulerAB — ClassicScheduler / FSRSScheduler / assignment ─


@pytest.mark.parametrize("grade", ["again", "hard", "good", "easy"])
def test_classic_scheduler_review_matches_compute_next_due_at(grade):
    """Scenario: ClassicScheduler.review produces identical results to
    calling compute_next_due_at directly, with extra_state always None."""
    last_reviewed_at = NOW - timedelta(days=2)
    expected_next_due_at = compute_next_due_at(grade, last_reviewed_at, NOW)

    result = ClassicScheduler().review(grade, last_reviewed_at, NOW)
    assert result.next_due_at == expected_next_due_at
    assert result.review_interval == expected_next_due_at - NOW
    assert result.extra_state is None

    # existing_state is accepted but ignored — Classic persists no state.
    result_with_state = ClassicScheduler().review(
        grade, last_reviewed_at, NOW, {"raw_state": {"anything": "ignored"}}
    )
    assert result_with_state.next_due_at == expected_next_due_at
    assert result_with_state.extra_state is None


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


def test_decide_scheduler_assignment_disabled_by_kill_switch(monkeypatch):
    """Scenario: Kill switch disables new assignment, defaulting new cards
    to classic. Forces classic with the disabled reason."""
    monkeypatch.setenv("ESSAYCARDS_FSRS_EXPERIMENT_ENABLED", "false")
    scheduler, reason = decide_scheduler_assignment("some-flashcard-id")
    assert (scheduler, reason) == ("classic", "assignment_disabled_classic")


def test_decide_scheduler_assignment_deterministic_for_same_id(monkeypatch):
    """Scenario: Assignment is deterministic — calling
    decide_scheduler_assignment twice for the same id returns the same
    scheduler."""
    monkeypatch.setenv("ESSAYCARDS_FSRS_EXPERIMENT_ENABLED", "true")
    first = decide_scheduler_assignment("00000000-0000-0000-0000-000000000042")
    second = decide_scheduler_assignment("00000000-0000-0000-0000-000000000042")
    assert first == second


def test_decide_scheduler_assignment_approximately_balanced(monkeypatch):
    """Scenario: Assignment across many distinct ids is approximately
    balanced (not exact, but not lopsided)."""
    monkeypatch.setenv("ESSAYCARDS_FSRS_EXPERIMENT_ENABLED", "true")
    counts = {"classic": 0, "fsrs": 0}
    for i in range(500):
        scheduler, reason = decide_scheduler_assignment(f"fixture-id-{i}")
        assert reason == "new_card_random"
        counts[scheduler] += 1
    # Not a stratified sampler (mission-accepted risk) — a generous band is
    # enough to catch a badly broken hash (e.g. always-classic).
    assert 150 <= counts["classic"] <= 350
    assert 150 <= counts["fsrs"] <= 350


def test_decide_scheduler_assignment_migrated_never_reviewed_reason(monkeypatch):
    monkeypatch.setenv("ESSAYCARDS_FSRS_EXPERIMENT_ENABLED", "true")
    _, reason = decide_scheduler_assignment("some-id", migrated_never_reviewed=True)
    assert reason == "migrated_never_reviewed_random"
