"""
EssayCards — pytest tests for GET /flashcards/due and
POST /flashcards/{id}/review.

Traceability: each function name maps to a scenario in
Sprint01_Core/10_test_spec.md. Fixture IDs are defined in tests/fixtures.sql.
"""

from datetime import datetime

# ── Fixture IDs (stable references to fixtures.sql) ───────────────────────────
ESSAY_A = "ea000001-0000-0000-0000-000000000001"
ESSAY_B = "ea000002-0000-0000-0000-000000000002"
ESSAY_C = "ea000003-0000-0000-0000-000000000003"  # nothing due
SECTION_A1 = "ec000001-0000-0000-0000-000000000001"  # "origins" — fc-origins-1, fc-origins-2
SECTION_A2 = "ec000002-0000-0000-0000-000000000002"  # "structure" — fc-origins-3, fc-not-due

FC_ORIGINS_1 = "fc000001-0000-0000-0000-000000000001"  # last_reviewed_at=null, due
FC_ORIGINS_2 = "fc000002-0000-0000-0000-000000000002"  # last_reviewed_at=null, due
FC_ORIGINS_3 = "fc000003-0000-0000-0000-000000000003"  # last_reviewed_at=60m ago, due
FC_NOT_DUE   = "fc000004-0000-0000-0000-000000000004"  # next_due_at 1h in the future

ESSAY_D = "ea000004-0000-0000-0000-000000000004"  # stats-horizon essay, all cards future-dated
SECTION_D1 = "ec000005-0000-0000-0000-000000000005"

# Sprint05_ReviewQueueOrdering — Essay E: nine eligible cards spanning both
# ordering categories (see tests/fixtures.sql for the timestamp layout).
ESSAY_E = "ea000005-0000-0000-0000-000000000005"
FC_E_RECENT_NEAR = "fc000011-0000-0000-0000-000000000011"  # LR 2h ago,  due 2m ago     -> RECENT
FC_E_RECENT_FAR  = "fc000012-0000-0000-0000-000000000012"  # LR 3h ago,  due 20m ago    -> RECENT
FC_E_RECENT_23H  = "fc000013-0000-0000-0000-000000000013"  # LR 23h ago, due 90s ago    -> RECENT (rolling window)
FC_E_BACK_25H    = "fc000014-0000-0000-0000-000000000014"  # LR 25h ago, due 90s ago    -> BACKLOG (rolling window)
FC_E_BACK_90D    = "fc000015-0000-0000-0000-000000000015"  # interval 90d, 1h overdue   -> BACKLOG
FC_E_BACK_30D    = "fc000016-0000-0000-0000-000000000016"  # interval 30d, 2d overdue   -> BACKLOG
FC_E_BACK_1D     = "fc000017-0000-0000-0000-000000000017"  # interval 1d,  1d overdue   -> BACKLOG
FC_E_BACK_20MIN  = "fc000018-0000-0000-0000-000000000018"  # interval 20m, ~3d overdue  -> BACKLOG
FC_E_NEW         = "fc000019-0000-0000-0000-000000000019"  # last_reviewed_at NULL, due  -> BACKLOG, interval 0

UNKNOWN_ID = "00000000-0000-0000-0000-000000000000"

STATS_BUCKET_ORDER = [
    "due_now", "within_10_min", "within_1_day",
    "within_7_days", "within_30_days", "beyond_30_days",
]


def _stats_counts(rows: list[dict]) -> dict[str, int]:
    return {row["bucket"]: row["count"] for row in rows}


def _parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# ── Due flashcards ─────────────────────────────────────────────────────────────

def _order(rows: list[dict]) -> list[str]:
    return [row["flashcard_id"] for row in rows]


def test_due_no_params_returns_system_wide(client):
    """Scenario: Due flashcards — no params returns system-wide queue."""
    r = client.get("/api/essaycards/flashcards/due")
    assert r.status_code == 200
    rows = r.json()["rows"]

    essay_ids = {row["essay_id"] for row in rows}
    assert ESSAY_A in essay_ids
    assert ESSAY_B in essay_ids

    # New contract: RECENT category (reviewed within the rolling 24h window)
    # precedes BACKLOG. fc-origins-3 was reviewed ~60m ago; fc-origins-1/2 were
    # never reviewed, so they are backlog and must come after it.
    order = _order(rows)
    assert order.index(FC_ORIGINS_3) < order.index(FC_ORIGINS_1)
    assert order.index(FC_ORIGINS_3) < order.index(FC_ORIGINS_2)

    for row in rows:
        assert row["id"] == row["flashcard_id"]
        for field in ("question", "answer", "essay_id", "section_id", "anchor_slug", "next_due_at"):
            assert field in row


def test_due_scoped_to_essay(client):
    """Scenario: Due flashcards — scoped to essay."""
    r = client.get(f"/api/essaycards/flashcards/due?essay_id={ESSAY_A}")
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert len(rows) > 0
    assert all(row["essay_id"] == ESSAY_A for row in rows)


def test_due_scoped_to_section(client):
    """Scenario: Due flashcards — scoped to essay and section."""
    r = client.get(f"/api/essaycards/flashcards/due?essay_id={ESSAY_A}&section_id={SECTION_A1}")
    assert r.status_code == 200
    rows = r.json()["rows"]
    ids = {row["flashcard_id"] for row in rows}
    assert ids == {FC_ORIGINS_1, FC_ORIGINS_2}
    assert FC_ORIGINS_3 not in ids  # belongs to section A2, not A1


def test_due_section_without_essay_rejected(client):
    """Scenario: Due flashcards — section_id without essay_id is rejected."""
    r = client.get(f"/api/essaycards/flashcards/due?section_id={SECTION_A1}")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_due_excludes_not_yet_due_cards(client):
    """Scenario: Due flashcards — excludes not-yet-due cards."""
    r = client.get(f"/api/essaycards/flashcards/due?essay_id={ESSAY_A}")
    ids = {row["flashcard_id"] for row in r.json()["rows"]}
    assert FC_NOT_DUE not in ids


def test_due_empty_result(client):
    """Scenario: Due flashcards — empty result when nothing due."""
    r = client.get(f"/api/essaycards/flashcards/due?essay_id={ESSAY_C}")
    assert r.status_code == 200
    body = r.json()
    assert body["rows"] == []
    assert body["meta"]["total"] == 0


# ── Due-queue ordering (Sprint05_ReviewQueueOrdering) ─────────────────────────
#
# All tests below are scoped to ESSAY_E so they are independent of the
# system-wide fixture set. Essay E's nine cards are all eligible; the expected
# full order is:
#   RECENT : fc-e-recent-23h, fc-e-recent-near, fc-e-recent-far
#   BACKLOG: fc-e-back-90d, fc-e-back-30d, fc-e-back-25h, fc-e-back-1d,
#            fc-e-back-20min, fc-e-new

def _essay_e_order(client) -> list[str]:
    r = client.get(f"/api/essaycards/flashcards/due?essay_id={ESSAY_E}")
    assert r.status_code == 200
    return _order(r.json()["rows"])


def test_due_full_ordering_essay_e(client):
    """The complete RECENT-then-BACKLOG order for Essay E."""
    assert _essay_e_order(client) == [
        FC_E_RECENT_23H, FC_E_RECENT_NEAR, FC_E_RECENT_FAR,
        FC_E_BACK_90D, FC_E_BACK_30D, FC_E_BACK_25H, FC_E_BACK_1D,
        FC_E_BACK_20MIN, FC_E_NEW,
    ]


def test_due_recently_reviewed_card_is_eligible_again(client):
    """Scenario: a card reviewed within the last 24h becoming due again.

    fc-e-recent-23h was reviewed 23h ago and its next_due_at is in the past —
    it must appear in the queue (eligibility is purely next_due_at <= now()).
    """
    order = _essay_e_order(client)
    assert FC_E_RECENT_23H in order


def test_due_recent_card_beats_backlog(client):
    """Scenario: a recently reviewed due card takes priority over the backlog.

    Every RECENT card precedes every BACKLOG card, including the mature
    90-day-interval backlog card.
    """
    order = _essay_e_order(client)
    recent = {FC_E_RECENT_NEAR, FC_E_RECENT_FAR, FC_E_RECENT_23H}
    backlog = {FC_E_BACK_90D, FC_E_BACK_30D, FC_E_BACK_25H, FC_E_BACK_1D, FC_E_BACK_20MIN, FC_E_NEW}
    assert max(order.index(x) for x in recent) < min(order.index(x) for x in backlog)


def test_due_recent_category_ordered_closest_due_first(client):
    """Scenario: recent-review category ordered by closest due time first.

    next_due_at DESC within RECENT: fc-e-recent-near (due 2m ago) precedes
    fc-e-recent-far (due 20m ago).
    """
    order = _essay_e_order(client)
    assert order.index(FC_E_RECENT_NEAR) < order.index(FC_E_RECENT_FAR)


def test_due_backlog_ordered_longest_interval_first(client):
    """Scenario: backlog ordered by longest scheduled interval first."""
    order = _essay_e_order(client)
    assert (
        order.index(FC_E_BACK_90D)
        < order.index(FC_E_BACK_30D)
        < order.index(FC_E_BACK_1D)
        < order.index(FC_E_BACK_20MIN)
        < order.index(FC_E_NEW)
    )


def test_due_backlog_order_ignores_overdue_duration(client):
    """Scenario: overdue duration does not affect backlog order.

    fc-e-back-90d is only ~1h overdue; fc-e-back-1d is ~1d overdue and
    fc-e-back-20min is ~3d overdue. Longest-interval-first still wins, i.e.
    the order is the reverse of most-overdue-first.
    """
    order = _essay_e_order(client)
    assert order.index(FC_E_BACK_90D) < order.index(FC_E_BACK_1D)
    assert order.index(FC_E_BACK_90D) < order.index(FC_E_BACK_20MIN)
    assert order.index(FC_E_BACK_1D) < order.index(FC_E_BACK_20MIN)


def test_due_card_reviewed_over_24h_ago_is_backlog(client):
    """Scenario: a card reviewed more than 24h ago falls into the backlog.

    fc-e-back-25h (reviewed 25h ago) sits in BACKLOG — after every RECENT
    card — and is ordered among backlog cards by its interval, not by how
    recently it was touched.
    """
    order = _essay_e_order(client)
    recent = {FC_E_RECENT_NEAR, FC_E_RECENT_FAR, FC_E_RECENT_23H}
    assert order.index(FC_E_BACK_25H) > max(order.index(x) for x in recent)
    # interval ~25h: below the 30-day card, above the 1-day card
    assert order.index(FC_E_BACK_30D) < order.index(FC_E_BACK_25H) < order.index(FC_E_BACK_1D)


def test_due_rolling_24h_window_not_calendar_day(client):
    """Scenario: the rolling 24-hour boundary (no calendar-day / midnight logic).

    fc-e-recent-23h and fc-e-back-25h both came due ~90s ago. The ONLY
    difference is last_reviewed_at: 23h ago vs 25h ago, straddling the
    now()-24h boundary. The 23h card is RECENT, the 25h card is BACKLOG —
    decided purely by the rolling delta, independent of where local midnight
    falls between the review instant and now.
    """
    order = _essay_e_order(client)
    assert order.index(FC_E_RECENT_23H) < order.index(FC_E_BACK_25H)
    backlog_start = min(
        order.index(x) for x in (FC_E_BACK_90D, FC_E_BACK_30D, FC_E_BACK_1D, FC_E_BACK_20MIN, FC_E_NEW)
    )
    assert order.index(FC_E_RECENT_23H) < backlog_start   # 23h card is RECENT
    assert order.index(FC_E_BACK_25H) > backlog_start     # 25h card is BACKLOG


def test_due_new_card_interval_zero_sorts_behind_backlog(client):
    """Scenario: a new card (interval 0) sorts behind every reviewed backlog card."""
    order = _essay_e_order(client)
    reviewed_backlog = {FC_E_BACK_90D, FC_E_BACK_30D, FC_E_BACK_25H, FC_E_BACK_1D, FC_E_BACK_20MIN}
    assert order.index(FC_E_NEW) > max(order.index(x) for x in reviewed_backlog)


def test_due_new_card_available_once_positive_interval_backlog_cleared(client):
    """Scenario: a new card becomes available once no positive-interval backlog remains.

    Grade every positive-interval backlog card 'easy' (pushes each far into the
    future, out of the queue). fc-e-new then has no positive-interval backlog
    card in front of it — only the still-due RECENT cards remain ahead.
    """
    for fc in (FC_E_BACK_90D, FC_E_BACK_30D, FC_E_BACK_25H, FC_E_BACK_1D, FC_E_BACK_20MIN):
        rr = client.post(f"/api/essaycards/flashcards/{fc}/review", json={"grade": "easy"})
        assert rr.status_code == 200

    order = _essay_e_order(client)
    assert FC_E_NEW in order
    for fc in (FC_E_BACK_90D, FC_E_BACK_30D, FC_E_BACK_25H, FC_E_BACK_1D, FC_E_BACK_20MIN):
        assert fc not in order
    # only RECENT cards (still due, not graded) may precede the new card
    assert order[-1] == FC_E_NEW


def test_due_card_with_no_review_row_history_is_never_reviewed(client):
    """Scenario: a card with no answer-history is treated as never reviewed.

    EssayCards has no per-review history table — 'never reviewed' is
    last_reviewed_at IS NULL on flashcard_review_state. fc-e-new is such a
    card: it is NOT placed in the RECENT category (NULL is not >= now()-24h)
    and is treated as interval 0.
    """
    order = _essay_e_order(client)
    recent = {FC_E_RECENT_NEAR, FC_E_RECENT_FAR, FC_E_RECENT_23H}
    assert order.index(FC_E_NEW) > max(order.index(x) for x in recent)
    assert order.index(FC_E_NEW) > order.index(FC_E_BACK_20MIN)


# ── Review ──────────────────────────────────────────────────────────────────────

def test_review_again_schedules_five_seconds(client):
    """Scenario: Review — grade again schedules five seconds out."""
    r = client.post(f"/api/essaycards/flashcards/{FC_ORIGINS_1}/review", json={"grade": "again"})
    assert r.status_code == 200
    body = r.json()
    last_reviewed = _parse_ts(body["last_reviewed_at"])
    next_due = _parse_ts(body["next_due_at"])
    delta = (next_due - last_reviewed).total_seconds()
    assert 4.5 <= delta <= 5.5


def test_review_good_first_time_uses_floor(client):
    """Scenario: Review — grade good on a never-reviewed card uses the floor."""
    r = client.post(f"/api/essaycards/flashcards/{FC_ORIGINS_2}/review", json={"grade": "good"})
    assert r.status_code == 200
    body = r.json()
    last_reviewed = _parse_ts(body["last_reviewed_at"])
    next_due = _parse_ts(body["next_due_at"])
    delta = (next_due - last_reviewed).total_seconds()
    assert 1190 <= delta <= 1210  # ~20 minutes


def test_review_good_repeat_uses_doubled_elapsed(client):
    """Scenario: Review — grade good on a repeat review doubles elapsed time."""
    r = client.post(f"/api/essaycards/flashcards/{FC_ORIGINS_3}/review", json={"grade": "good"})
    assert r.status_code == 200
    body = r.json()
    last_reviewed = _parse_ts(body["last_reviewed_at"])
    next_due = _parse_ts(body["next_due_at"])
    delta = (next_due - last_reviewed).total_seconds()
    # fixture last_reviewed_at was ~60 minutes before now; 2*60=120min exceeds the 20min floor
    assert 7100 <= delta <= 7300


def test_review_invalid_grade_rejected(client):
    """Scenario: Review — invalid grade rejected.

    Also exercises the manual raw-body validation contract (R-CON-BP-04 correction):
    missing grade key, non-string grade, and out-of-set grade must all return
    ApiError VALIDATION_ERROR (400) — never FastAPI's default 422 shape.
    """
    r = client.post(f"/api/essaycards/flashcards/{FC_ORIGINS_1}/review", json={"grade": "maybe"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"

    r_missing = client.post(f"/api/essaycards/flashcards/{FC_ORIGINS_1}/review", json={})
    assert r_missing.status_code == 400
    assert r_missing.json()["error"]["code"] == "VALIDATION_ERROR"

    r_wrong_type = client.post(f"/api/essaycards/flashcards/{FC_ORIGINS_1}/review", json={"grade": 5})
    assert r_wrong_type.status_code == 400
    assert r_wrong_type.json()["error"]["code"] == "VALIDATION_ERROR"

    r_bad_json = client.post(
        f"/api/essaycards/flashcards/{FC_ORIGINS_1}/review",
        data="not json",
        headers={"Content-Type": "application/json"},
    )
    assert r_bad_json.status_code == 400
    assert r_bad_json.json()["error"]["code"] == "VALIDATION_ERROR"


def test_review_unknown_flashcard_not_found(client):
    """Scenario: Review — unknown flashcard not found."""
    r = client.post(f"/api/essaycards/flashcards/{UNKNOWN_ID}/review", json={"grade": "good"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


# ── Queue stats ───────────────────────────────────────────────────────────────

def test_stats_system_wide_partitions_all_bands(client):
    """Scenario: Queue stats — no params returns the six system-wide horizon bands."""
    r = client.get("/api/essaycards/flashcards/stats")
    assert r.status_code == 200
    body = r.json()

    assert body["meta"]["object_type"] == "flashcard_queue_stat"
    assert body["meta"]["total"] == 6
    assert [row["bucket"] for row in body["rows"]] == STATS_BUCKET_ORDER
    for row in body["rows"]:
        for field in ("bucket", "label", "count"):
            assert field in row

    counts = _stats_counts(body["rows"])
    assert counts == {
        "due_now": 13,  # 4 from essays A/B + 9 eligible Essay E ordering cards (Sprint05)
        "within_10_min": 1,
        "within_1_day": 2,
        "within_7_days": 1,
        "within_30_days": 1,
        "beyond_30_days": 1,
    }
    assert sum(counts.values()) == 19  # every scheduled card lands in exactly one band


def test_stats_scoped_to_essay(client):
    """Scenario: Queue stats — scoped to a single essay."""
    r = client.get(f"/api/essaycards/flashcards/stats?essay_id={ESSAY_D}")
    assert r.status_code == 200
    counts = _stats_counts(r.json()["rows"])
    assert counts == {
        "due_now": 0,
        "within_10_min": 1,
        "within_1_day": 0,
        "within_7_days": 1,
        "within_30_days": 1,
        "beyond_30_days": 1,
    }


def test_stats_scoped_to_section(client):
    """Scenario: Queue stats — scoped to essay and section."""
    r = client.get(f"/api/essaycards/flashcards/stats?essay_id={ESSAY_A}&section_id={SECTION_A1}")
    assert r.status_code == 200
    counts = _stats_counts(r.json()["rows"])
    # section A1 holds fc-origins-1 and fc-origins-2, both already due
    assert counts["due_now"] == 2
    assert sum(counts.values()) == 2


def test_stats_section_without_essay_rejected(client):
    """Scenario: Queue stats — section_id without essay_id is rejected."""
    r = client.get(f"/api/essaycards/flashcards/stats?section_id={SECTION_A1}")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_stats_unknown_scope_is_zero_filled(client):
    """Scenario: Queue stats — empty scope still returns six zero-filled bands."""
    r = client.get(f"/api/essaycards/flashcards/stats?essay_id={UNKNOWN_ID}")
    assert r.status_code == 200
    body = r.json()
    assert [row["bucket"] for row in body["rows"]] == STATS_BUCKET_ORDER
    assert all(row["count"] == 0 for row in body["rows"])
    assert body["meta"]["total"] == 6
