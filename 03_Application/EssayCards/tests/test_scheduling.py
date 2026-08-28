"""
EssayCards — unit tests for backend.scheduling.compute_next_due_at.

Pure function tests: no HTTP, no DB. Per Sprint01_Core/10_architecture.json
deferrals.test_writer, covers: again flat 5s; hard/good/easy first-time
(null last_reviewed_at) floor-only; hard/good/easy repeat review where
2*elapsed exceeds floor; hard/good/easy repeat review where floor exceeds
2*elapsed.
"""

from datetime import datetime, timedelta, timezone

import pytest

from backend.scheduling import compute_next_due_at

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
