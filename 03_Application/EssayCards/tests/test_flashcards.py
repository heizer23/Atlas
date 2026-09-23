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

# Sprint10_DualSchedulerAB — Essay H fixture cards (see tests/fixtures.sql).
ESSAY_H = "ea000008-0000-0000-0000-000000000008"
FC_FSRS_ESTABLISHED = "fc000023-0000-0000-0000-000000000023"  # fsrs, established, NOT due
FC_FSRS_FRESH       = "fc000024-0000-0000-0000-000000000024"  # fsrs, never reviewed, no fsrs_card_state row, NOT due
FC_CLASSIC_ESTABLISHED = "fc000025-0000-0000-0000-000000000025"  # classic, established, NOT due
FC_MIX_RECENT_CLASSIC  = "fc000026-0000-0000-0000-000000000026"  # classic, RECENT, due 5m ago
FC_MIX_RECENT_FSRS     = "fc000027-0000-0000-0000-000000000027"  # fsrs, RECENT, due 20m ago
FC_MIX_BACKLOG_CLASSIC = "fc000028-0000-0000-0000-000000000028"  # classic, BACKLOG, 12h interval
FC_MIX_BACKLOG_FSRS    = "fc000029-0000-0000-0000-000000000029"  # fsrs, BACKLOG, 6h interval

STATS_BUCKET_ORDER = [
    "due_now", "within_10_min", "within_1_day",
    "within_7_days", "within_30_days", "within_90_days", "beyond_90_days",
]


def _stats_counts(rows: list[dict]) -> dict[str, int]:
    return {row["bucket"]: row["count"] for row in rows}


def _parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# ── Due flashcards ─────────────────────────────────────────────────────────────

def _order(rows: list[dict]) -> list[str]:
    return [row["flashcard_id"] for row in rows]


def test_due_no_params_returns_review_queue(client):
    """No scope params -> REVIEW mode: only cards that are open AND established
    (review_interval >= 24h). New and learning (sub-24h) cards are excluded —
    they are reachable only through a scoped (focus) session.
    """
    r = client.get("/api/essaycards/flashcards/due")
    assert r.status_code == 200
    rows = r.json()["rows"]
    ids = _order(rows)

    # Every card in the review queue is established.
    assert rows and all(row["scheduled_interval_seconds"] >= 86400 for row in rows)

    # New / learning / still-sub-24h cards are absent.
    assert FC_ORIGINS_1 not in ids        # never reviewed (interval 0)
    assert FC_ORIGINS_3 not in ids        # reviewed ~60m ago, ~59m interval
    assert FC_E_BACK_20MIN not in ids     # 20-minute interval
    assert FC_E_RECENT_23H not in ids     # ~23h interval, still < 24h

    # The established, currently-due cards (Essay E) in BACKLOG order
    # (longest interval first).
    assert ids == [FC_E_BACK_90D, FC_E_BACK_30D, FC_E_BACK_25H, FC_E_BACK_1D]

    for row in rows:
        assert row["id"] == row["flashcard_id"]
        for field in ("question", "answer", "essay_id", "section_id", "anchor_slug",
                      "next_due_at", "is_new", "is_recent", "scheduled_interval_seconds"):
            assert field in row


def test_due_essay_scope_is_focus_includes_new_and_learning(client):
    """A scope param makes the session a FOCUS session: every open card in
    scope appears regardless of interval — new, learning, established alike.
    """
    r = client.get(f"/api/essaycards/flashcards/due?essay_id={ESSAY_A}")
    assert r.status_code == 200
    ids = {row["flashcard_id"] for row in r.json()["rows"]}
    assert {FC_ORIGINS_1, FC_ORIGINS_2, FC_ORIGINS_3} <= ids   # 2 new + 1 sub-24h
    assert FC_NOT_DUE not in ids                                # still must be open


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


def test_due_topic_scope_is_focus_across_the_topics_essays(client):
    """?topic=<category> is a FOCUS session over every essay in that topic:
    all open cards, no interval filter."""
    for slug in ("ftopic-a", "ftopic-b"):
        assert client.post("/api/essaycards/essays/ingest", json={
            "title": slug, "slug": slug, "category": "FocusTopic",
            "sections": [{
                "heading": "S", "anchor_slug": f"{slug}-s", "body_markdown": "b",
                "cards": [{"id": f"{slug}-c1", "q": f"{slug} q", "a": "a"}],
            }],
        }).status_code == 200

    r = client.get("/api/essaycards/flashcards/due?topic=FocusTopic")
    assert r.status_code == 200
    rows = r.json()["rows"]
    # both freshly-ingested (new, interval 0) cards appear — no established gate
    assert {row["question"] for row in rows} == {"ftopic-a q", "ftopic-b q"}
    assert all(row["scheduled_interval_seconds"] == 0 for row in rows)


def test_due_topic_combined_with_essay_id_rejected(client):
    r = client.get(f"/api/essaycards/flashcards/due?topic=Whatever&essay_id={ESSAY_A}")
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


def test_due_rows_expose_is_new_recent_and_interval(client):
    """Each /due row carries is_new = (last_reviewed_at IS NULL),
    is_recent = (last_reviewed_at >= now() - 24h), and
    scheduled_interval_seconds = epoch(next_due_at - last_reviewed_at).

    Feed the review screen's CURRENT 'New' metric, the recency-selected bold
    frame, and the diagnostics frame. fc-e-new is never reviewed (is_new, not
    recent, interval 0); fc-e-recent-near was reviewed 2h ago (recent);
    fc-e-back-25h was reviewed 25h ago (not recent); fc-e-back-1d was last
    reviewed 2 days ago and is due 1 day ago -> a ~1-day interval.
    """
    r = client.get(f"/api/essaycards/flashcards/due?essay_id={ESSAY_E}")
    assert r.status_code == 200
    by_id = {row["flashcard_id"]: row for row in r.json()["rows"]}
    sample = next(iter(by_id.values()))
    for field in ("is_new", "is_recent", "scheduled_interval_seconds"):
        assert field in sample

    assert by_id[FC_E_NEW]["is_new"] is True
    assert by_id[FC_E_NEW]["is_recent"] is False
    assert by_id[FC_E_NEW]["scheduled_interval_seconds"] == 0

    assert by_id[FC_E_RECENT_NEAR]["is_recent"] is True
    assert by_id[FC_E_RECENT_23H]["is_recent"] is True
    assert by_id[FC_E_BACK_25H]["is_recent"] is False
    assert by_id[FC_E_BACK_90D]["is_recent"] is False

    one_day = 24 * 3600
    assert abs(by_id[FC_E_BACK_1D]["scheduled_interval_seconds"] - one_day) < 3600


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


def test_review_materialises_review_interval(client, db_conn):
    """POST .../review writes review_interval = next_due_at - last_reviewed_at
    in the same statement (the single writer of that cache column)."""
    client.post(f"/api/essaycards/flashcards/{FC_ORIGINS_3}/review", json={"grade": "good"})
    with db_conn.cursor() as cur:
        cur.execute(
            "select last_reviewed_at, next_due_at, review_interval "
            "from essaycards.flashcard_review_state where flashcard_id = %s",
            (FC_ORIGINS_3,),
        )
        row = cur.fetchone()
    assert row["review_interval"] == row["next_due_at"] - row["last_reviewed_at"]

    client.post(f"/api/essaycards/flashcards/{FC_ORIGINS_1}/review", json={"grade": "again"})
    with db_conn.cursor() as cur:
        cur.execute(
            "select review_interval from essaycards.flashcard_review_state where flashcard_id = %s",
            (FC_ORIGINS_1,),
        )
        assert 4 <= cur.fetchone()["review_interval"].total_seconds() <= 6


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


# ── Sprint10_DualSchedulerAB — Classic regression coverage via the HTTP endpoint ──
#
# FC_ORIGINS_1/2/3/4 and the Essay E fixture cards are all pinned to
# scheduler='classic' by tests/fixtures.sql's Sprint10 catch-all UPDATE, so
# every review here still exercises compute_next_due_at exactly as before
# this sprint — these are regression-pinning tests, not new behavior.

def test_review_hard_first_time_and_repeat_via_endpoint(client):
    """Scenario: Classic hard grade applies floor-or-doubled-elapsed via the
    endpoint — never-reviewed uses the 1-minute floor; previously-reviewed
    uses max(1 minute, 2 x elapsed)."""
    r = client.post(f"/api/essaycards/flashcards/{FC_ORIGINS_2}/review", json={"grade": "hard"})
    assert r.status_code == 200
    body = r.json()
    delta = (_parse_ts(body["next_due_at"]) - _parse_ts(body["last_reviewed_at"])).total_seconds()
    assert 55 <= delta <= 65  # ~1 minute floor

    r2 = client.post(f"/api/essaycards/flashcards/{FC_ORIGINS_3}/review", json={"grade": "hard"})
    assert r2.status_code == 200
    body2 = r2.json()
    delta2 = (_parse_ts(body2["next_due_at"]) - _parse_ts(body2["last_reviewed_at"])).total_seconds()
    # fixture last_reviewed_at ~60 minutes before now; 2*60min=120min exceeds the 1min floor
    assert 7100 <= delta2 <= 7300


def test_review_easy_first_time_and_repeat_via_endpoint(client):
    """Scenario: Classic easy grade applies floor-or-doubled-elapsed via the
    endpoint — never-reviewed uses the 1-day floor; previously-reviewed uses
    max(1 day, 2 x elapsed)."""
    r = client.post(f"/api/essaycards/flashcards/{FC_ORIGINS_2}/review", json={"grade": "easy"})
    assert r.status_code == 200
    body = r.json()
    delta = (_parse_ts(body["next_due_at"]) - _parse_ts(body["last_reviewed_at"])).total_seconds()
    assert 86300 <= delta <= 86500  # ~1 day floor

    r2 = client.post(f"/api/essaycards/flashcards/{FC_CLASSIC_ESTABLISHED}/review", json={"grade": "easy"})
    assert r2.status_code == 200
    body2 = r2.json()
    delta2 = (_parse_ts(body2["next_due_at"]) - _parse_ts(body2["last_reviewed_at"])).total_seconds()
    # fixture last_reviewed_at ~40 days before now; 2*40d comfortably exceeds the 1-day floor
    assert 79 * 86400 <= delta2 <= 81 * 86400


def test_review_consecutive_reviews_chain_from_persisted_state(client):
    """Scenario: Consecutive reviews on the same card chain from persisted
    state — the second review is computed from the first review's persisted
    last_reviewed_at, not the original pre-review state."""
    r1 = client.post(f"/api/essaycards/flashcards/{FC_ORIGINS_2}/review", json={"grade": "good"})
    first_last_reviewed = _parse_ts(r1.json()["last_reviewed_at"])
    first_next_due = _parse_ts(r1.json()["next_due_at"])
    assert (first_next_due - first_last_reviewed).total_seconds() < 1300  # first-time floor (~20min)

    r2 = client.post(f"/api/essaycards/flashcards/{FC_ORIGINS_2}/review", json={"grade": "good"})
    second_last_reviewed = _parse_ts(r2.json()["last_reviewed_at"])
    second_next_due = _parse_ts(r2.json()["next_due_at"])
    assert second_last_reviewed >= first_last_reviewed
    # Second review's elapsed-since-last-review is tiny (back-to-back calls),
    # so doubled-elapsed is far below the 20min floor -> floor wins again.
    assert (second_next_due - second_last_reviewed).total_seconds() < 1300


def test_review_again_after_several_successful_reviews_still_flat_five_seconds(client):
    """Scenario: Failure after several successful reviews still resets to
    flat five seconds, discarding the accumulated interval entirely."""
    client.post(f"/api/essaycards/flashcards/{FC_ORIGINS_2}/review", json={"grade": "good"})
    client.post(f"/api/essaycards/flashcards/{FC_ORIGINS_2}/review", json={"grade": "easy"})

    r = client.post(f"/api/essaycards/flashcards/{FC_ORIGINS_2}/review", json={"grade": "again"})
    assert r.status_code == 200
    body = r.json()
    delta = (_parse_ts(body["next_due_at"]) - _parse_ts(body["last_reviewed_at"])).total_seconds()
    assert 4.5 <= delta <= 5.5


def test_review_established_card_doubling_at_multiday_scale_via_endpoint(client):
    """Scenario: Mature card reviewed again applies doubling at multi-day
    scale via the endpoint — max(floor, 2 x elapsed), correctly computed at
    a multi-day scale."""
    r = client.post(f"/api/essaycards/flashcards/{FC_CLASSIC_ESTABLISHED}/review", json={"grade": "good"})
    assert r.status_code == 200
    body = r.json()
    delta = (_parse_ts(body["next_due_at"]) - _parse_ts(body["last_reviewed_at"])).total_seconds()
    # fixture last_reviewed_at ~40 days before now; 2*40d comfortably exceeds the 20min floor
    assert 79 * 86400 <= delta <= 81 * 86400


# ── Sprint10_DualSchedulerAB — scheduler field, dispatch, FSRS, assignment ──────

def test_due_rows_carry_scheduler(client):
    """Scenario: Due-queue selection is scheduler-agnostic (due-row field
    part). Due rows carry scheduler: 'classic' for a legacy fixture card,
    'fsrs' for an FSRS fixture card."""
    r = client.get(f"/api/essaycards/flashcards/due?essay_id={ESSAY_H}")
    assert r.status_code == 200
    rows = {row["flashcard_id"]: row for row in r.json()["rows"]}
    assert rows[FC_MIX_RECENT_CLASSIC]["scheduler"] == "classic"
    assert rows[FC_MIX_RECENT_FSRS]["scheduler"] == "fsrs"
    assert rows[FC_MIX_BACKLOG_CLASSIC]["scheduler"] == "classic"
    assert rows[FC_MIX_BACKLOG_FSRS]["scheduler"] == "fsrs"


def test_due_queue_ordering_is_scheduler_agnostic(client):
    """Scenario: Due-queue selection is scheduler-agnostic. Eligibility,
    RECENT-before-BACKLOG grouping, RECENT's next_due_at-DESC ordering,
    BACKLOG's review_interval-DESC ordering are determined purely by
    next_due_at/last_reviewed_at/review_interval across a deliberate mix of
    classic and fsrs cards, with scheduler never a sort/filter key. Also
    confirms is_new/is_recent/scheduled_interval_seconds still compute
    correctly across the scheduler mix (11_design_review.md Recommended
    Improvement #2 / 12_design_corrections.md item 4)."""
    r = client.get(f"/api/essaycards/flashcards/due?essay_id={ESSAY_H}")
    assert r.status_code == 200
    rows = r.json()["rows"]
    ids = _order(rows)
    assert ids == [
        FC_MIX_RECENT_CLASSIC, FC_MIX_RECENT_FSRS,   # RECENT, next_due_at DESC
        FC_MIX_BACKLOG_CLASSIC, FC_MIX_BACKLOG_FSRS,  # BACKLOG, review_interval DESC
    ]

    by_id = {row["flashcard_id"]: row for row in rows}
    assert by_id[FC_MIX_RECENT_CLASSIC]["is_recent"] is True
    assert by_id[FC_MIX_RECENT_FSRS]["is_recent"] is True
    assert by_id[FC_MIX_BACKLOG_CLASSIC]["is_recent"] is False
    assert by_id[FC_MIX_BACKLOG_FSRS]["is_recent"] is False
    assert all(row["is_new"] is False for row in rows)
    assert by_id[FC_MIX_BACKLOG_CLASSIC]["scheduled_interval_seconds"] == 12 * 3600
    assert by_id[FC_MIX_BACKLOG_FSRS]["scheduled_interval_seconds"] == 6 * 3600

    # The seven forecast bands remain unaffected by the scheduler mix — still
    # exactly seven zero-filled rows, no scheduler-conditional behavior.
    stats_r = client.get(f"/api/essaycards/flashcards/stats?essay_id={ESSAY_H}")
    assert stats_r.status_code == 200
    assert stats_r.json()["meta"]["total"] == 7


def test_fsrs_resurfacing_uses_recent_mechanism(client, db_conn):
    """Scenario: FSRS resurfacing uses the same RECENT mechanism as Classic.
    Grading an fsrs card 'again' produces a short interval; once that
    interval elapses, the card reappears via the existing RECENT category —
    no separate FSRS queue exists."""
    r = client.post(f"/api/essaycards/flashcards/{FC_FSRS_FRESH}/review", json={"grade": "again"})
    assert r.status_code == 200

    # Simulate the short learning-step interval elapsing (same technique
    # fixtures.sql already uses to construct fixed points in time).
    with db_conn.cursor() as cur:
        cur.execute(
            "update essaycards.flashcard_review_state set next_due_at = now() - interval '1 minute' "
            "where flashcard_id = %s",
            (FC_FSRS_FRESH,),
        )

    due_r = client.get(f"/api/essaycards/flashcards/due?essay_id={ESSAY_H}")
    rows = {row["flashcard_id"]: row for row in due_r.json()["rows"]}
    assert FC_FSRS_FRESH in rows
    assert rows[FC_FSRS_FRESH]["is_recent"] is True  # RECENT, not a separate queue


def test_fsrs_review_persists_and_reloads_state_across_requests(client, db_conn):
    """Scenario: FSRS card state persists and reloads across requests
    (simulating an application restart, since state is read fresh from the
    database on every request, never cached in-process) — the review is
    computed from the reloaded prior stability/difficulty/state, not a fresh
    card."""
    with db_conn.cursor() as cur:
        cur.execute(
            "select stability, difficulty from essaycards.fsrs_card_state where flashcard_id = %s",
            (FC_FSRS_ESTABLISHED,),
        )
        before = cur.fetchone()
    assert before is not None

    r = client.post(f"/api/essaycards/flashcards/{FC_FSRS_ESTABLISHED}/review", json={"grade": "good"})
    assert r.status_code == 200

    with db_conn.cursor() as cur:
        cur.execute(
            "select stability, difficulty, raw_state from essaycards.fsrs_card_state where flashcard_id = %s",
            (FC_FSRS_ESTABLISHED,),
        )
        after = cur.fetchone()
    # Continuation, not a reset: the pre-existing fixture stability (15.0) is
    # what the review is computed FROM, so the resulting stability differs
    # from what a fresh card's first "good" review would produce.
    assert after["stability"] != before["stability"]
    assert after["raw_state"]["stability"] == after["stability"]


def test_fsrs_review_enters_relearning_on_again_after_review_state(client, db_conn):
    """Scenario: FSRS relearning. Grading 'again' on a card whose
    fsrs_card_state reflects the Review state (already graduated) produces
    Relearning with a short relearning-step interval, persisted and flowing
    through next_due_at like any other FSRS result."""
    r = client.post(f"/api/essaycards/flashcards/{FC_FSRS_ESTABLISHED}/review", json={"grade": "again"})
    assert r.status_code == 200
    body = r.json()
    delta = (_parse_ts(body["next_due_at"]) - _parse_ts(body["last_reviewed_at"])).total_seconds()
    assert delta < 3600  # short relearning-step interval, not a multi-day one

    with db_conn.cursor() as cur:
        cur.execute(
            "select fsrs_state from essaycards.fsrs_card_state where flashcard_id = %s",
            (FC_FSRS_ESTABLISHED,),
        )
        assert cur.fetchone()["fsrs_state"] == 3  # State.Relearning


def test_fsrs_review_due_date_flows_through_existing_fields(client, db_conn):
    """Scenario: FSRS due date flows through the existing fields with no
    separate queue — the response and persisted flashcard_review_state show
    next_due_at/review_interval set from the library's calculated due date,
    same fields/shape/single-writer as a classic-scheduler review."""
    r = client.post(f"/api/essaycards/flashcards/{FC_FSRS_FRESH}/review", json={"grade": "good"})
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"flashcard_id", "last_reviewed_at", "next_due_at"}

    with db_conn.cursor() as cur:
        cur.execute(
            "select last_reviewed_at, next_due_at, review_interval "
            "from essaycards.flashcard_review_state where flashcard_id = %s",
            (FC_FSRS_FRESH,),
        )
        row = cur.fetchone()
    assert row["next_due_at"].isoformat() == _parse_ts(body["next_due_at"]).isoformat()
    assert row["review_interval"] == row["next_due_at"] - row["last_reviewed_at"]


def test_fsrs_review_handles_first_ever_review_with_no_prior_state(client, db_conn):
    """Scenario: FSRS handles a card's first-ever review with no prior
    state — a fresh fsrs_card_state row is created (library defaults —
    Learning state) and no error occurs from the absence of prior state."""
    with db_conn.cursor() as cur:
        cur.execute(
            "select 1 from essaycards.fsrs_card_state where flashcard_id = %s", (FC_FSRS_FRESH,)
        )
        assert cur.fetchone() is None  # no prior state, per fixture design

    r = client.post(f"/api/essaycards/flashcards/{FC_FSRS_FRESH}/review", json={"grade": "good"})
    assert r.status_code == 200

    with db_conn.cursor() as cur:
        cur.execute(
            "select fsrs_state, raw_state from essaycards.fsrs_card_state where flashcard_id = %s",
            (FC_FSRS_FRESH,),
        )
        row = cur.fetchone()
    assert row is not None
    assert row["fsrs_state"] == 1  # State.Learning


def test_new_card_creation_assigns_scheduler_permanently(client, db_conn):
    """Scenario: New card creation assigns a scheduler permanently — via
    POST /flashcards/upsert, its flashcard_review_state row is seeded with a
    scheduler, scheduler_assigned_at, scheduler_assignment_reason=
    'new_card_random', experiment_version='sprint10_v1' — and this
    assignment never changes afterward."""
    r = client.post("/api/essaycards/flashcards/upsert", json={
        "essay_slug": "origins-of-long-form-formats",
        "section_id": SECTION_A1,
        "card": {"level": 2, "q": "New scheduler-assignment question?", "a": "An answer."},
    })
    assert r.status_code == 200
    flashcard_id = r.json()["flashcard_id"]

    with db_conn.cursor() as cur:
        cur.execute(
            "select scheduler, scheduler_assigned_at, scheduler_assignment_reason, experiment_version "
            "from essaycards.flashcard_review_state where flashcard_id = %s",
            (flashcard_id,),
        )
        row = cur.fetchone()
    assert row["scheduler"] in ("classic", "fsrs")
    assert row["scheduler_assigned_at"] is not None
    assert row["scheduler_assignment_reason"] == "new_card_random"
    assert row["experiment_version"] == "sprint10_v1"

    # Reviewing it does not change the assignment.
    client.post(f"/api/essaycards/flashcards/{flashcard_id}/review", json={"grade": "good"})
    with db_conn.cursor() as cur:
        cur.execute(
            "select scheduler from essaycards.flashcard_review_state where flashcard_id = %s",
            (flashcard_id,),
        )
        assert cur.fetchone()["scheduler"] == row["scheduler"]


def test_upsert_edit_of_existing_card_never_changes_scheduler_assignment(client, db_conn):
    """Scenario: Editing an existing card never reassigns its scheduler —
    editing question/answer/level via POST /flashcards/upsert leaves
    scheduler/scheduler_assigned_at/scheduler_assignment_reason unchanged."""
    with db_conn.cursor() as cur:
        cur.execute(
            "select scheduler, scheduler_assigned_at, scheduler_assignment_reason "
            "from essaycards.flashcard_review_state where flashcard_id = %s",
            (FC_ORIGINS_1,),
        )
        before = cur.fetchone()

    r = client.post("/api/essaycards/flashcards/upsert", json={
        "essay_slug": "origins-of-long-form-formats",
        "section_id": SECTION_A1,
        "card": {"id": "fc-origins-1", "level": 3, "q": "Edited question?", "a": "Edited answer."},
    })
    assert r.status_code == 200

    with db_conn.cursor() as cur:
        cur.execute(
            "select scheduler, scheduler_assigned_at, scheduler_assignment_reason "
            "from essaycards.flashcard_review_state where flashcard_id = %s",
            (FC_ORIGINS_1,),
        )
        after = cur.fetchone()
    assert after == before


def test_kill_switch_disabled_assigns_new_cards_classic(client, db_conn, monkeypatch):
    """Scenario: Kill switch disables new assignment without disturbing
    existing state — a new flashcard is assigned scheduler='classic',
    scheduler_assignment_reason='assignment_disabled_classic', and no
    existing card's assignment or FSRS state is altered."""
    with db_conn.cursor() as cur:
        cur.execute(
            "select scheduler from essaycards.flashcard_review_state where flashcard_id = %s",
            (FC_FSRS_ESTABLISHED,),
        )
        existing_scheduler_before = cur.fetchone()["scheduler"]

    monkeypatch.setenv("ESSAYCARDS_FSRS_EXPERIMENT_ENABLED", "false")
    r = client.post("/api/essaycards/flashcards/upsert", json={
        "essay_slug": "origins-of-long-form-formats",
        "section_id": SECTION_A1,
        "card": {"level": 2, "q": "Kill-switch question?", "a": "An answer."},
    })
    assert r.status_code == 200
    flashcard_id = r.json()["flashcard_id"]

    with db_conn.cursor() as cur:
        cur.execute(
            "select scheduler, scheduler_assignment_reason "
            "from essaycards.flashcard_review_state where flashcard_id = %s",
            (flashcard_id,),
        )
        new_row = cur.fetchone()
    assert new_row["scheduler"] == "classic"
    assert new_row["scheduler_assignment_reason"] == "assignment_disabled_classic"

    with db_conn.cursor() as cur:
        cur.execute(
            "select scheduler from essaycards.flashcard_review_state where flashcard_id = %s",
            (FC_FSRS_ESTABLISHED,),
        )
        assert cur.fetchone()["scheduler"] == existing_scheduler_before


# ── Queue stats ───────────────────────────────────────────────────────────────

def test_stats_system_wide_partitions_all_bands(client):
    """Scenario: Queue stats — no params returns the seven system-wide horizon bands."""
    r = client.get("/api/essaycards/flashcards/stats")
    assert r.status_code == 200
    body = r.json()

    assert body["meta"]["object_type"] == "flashcard_queue_stat"
    assert body["meta"]["total"] == 7
    assert [row["bucket"] for row in body["rows"]] == STATS_BUCKET_ORDER
    for row in body["rows"]:
        for field in ("bucket", "label", "count"):
            assert field in row

    counts = _stats_counts(body["rows"])
    assert counts == {
        # 4 from essays A/B + 9 eligible Essay E ordering cards (Sprint05) + 2
        # fixture Essay F nugget cards (fc-nugget-linked/-unlinked, Sprint09,
        # due 10 minutes ago, never reviewed) + 4 Sprint10_DualSchedulerAB
        # Essay H due cards (fix-mix-recent-classic/-fsrs, due 5m/20m ago;
        # fix-mix-backlog-classic/-fsrs, due 1d12h/2d18h ago) -> due_now.
        "due_now": 19,
        "within_10_min": 1,
        # +3 Sprint10_DualSchedulerAB Essay H cards, all next_due_at = now()
        # + 1 hour (fix-fsrs-established, fix-fsrs-fresh, fix-classic-established
        # — deliberately not due; see tests/fixtures.sql "Sprint10_DualSchedulerAB"
        # section for why none of Essay H's cards may be both due AND
        # established, to preserve this system-wide count).
        "within_1_day": 5,
        "within_7_days": 1,
        "within_30_days": 1,
        "within_90_days": 1,   # fc-stats-60day
        "beyond_90_days": 1,   # fc-stats-120day
    }
    assert sum(counts.values()) == 29  # every scheduled card lands in exactly one band


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
        "within_90_days": 1,   # fc-stats-60day
        "beyond_90_days": 1,   # fc-stats-120day
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


def test_stats_scoped_to_topic(client):
    """Queue stats accepts topic= (matching GET /flashcards/due) so the review
    screen's forecast is scoped to a topic focus session."""
    for slug in ("stopic-a", "stopic-b"):
        assert client.post("/api/essaycards/essays/ingest", json={
            "title": slug, "slug": slug, "category": "StatTopic",
            "sections": [{
                "heading": "S", "anchor_slug": f"{slug}-s", "body_markdown": "b",
                "cards": [{"id": f"{slug}-c1", "q": "q", "a": "a"}],
            }],
        }).status_code == 200

    counts = _stats_counts(client.get("/api/essaycards/flashcards/stats?topic=StatTopic").json()["rows"])
    assert counts["due_now"] == 2               # both essays' new cards, due at ingest
    assert sum(counts.values()) == 2            # nothing else in scope


def test_stats_topic_combined_with_essay_id_rejected(client):
    r = client.get(f"/api/essaycards/flashcards/stats?topic=X&essay_id={ESSAY_A}")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_stats_unknown_scope_is_zero_filled(client):
    """Scenario: Queue stats — empty scope still returns seven zero-filled bands."""
    r = client.get(f"/api/essaycards/flashcards/stats?essay_id={UNKNOWN_ID}")
    assert r.status_code == 200
    body = r.json()
    assert [row["bucket"] for row in body["rows"]] == STATS_BUCKET_ORDER
    assert all(row["count"] == 0 for row in body["rows"])
    assert body["meta"]["total"] == 7


# ── Nuggets (Sprint09_Nuggets) ─────────────────────────────────────────────────
#
# Fixture essay F ('essay-f-nuggets', ea000006) / section F1 (ec000007) has
# fc-nugget-linked (fc000021, linked to fix-nugget-cogito, ee000001) and
# fc-nugget-unlinked (fc000022, no nugget). Both are due, never reviewed.

ESSAY_F_SLUG = "essay-f-nuggets"
SECTION_F1_ID = "ec000007-0000-0000-0000-000000000007"
FC_NUGGET_LINKED = "fc000021-0000-0000-0000-000000000021"
FC_NUGGET_UNLINKED = "fc000022-0000-0000-0000-000000000022"
NUGGET_COGITO_ID = "ee000001-0000-0000-0000-000000000001"
NUGGET_WAX_ID = "ee000002-0000-0000-0000-000000000002"


def _current_nugget_id(client, flashcard_id):
    return client.get(f"/api/essaycards/flashcards/{flashcard_id}/export").json()["card"]["nugget_id"]


def test_due_rows_carry_nugget_id(client):
    """Scenario: Due rows carry nugget_id."""
    rows = client.get(
        "/api/essaycards/flashcards/due",
        params={"essay_id": "ea000006-0000-0000-0000-000000000006"},
    ).json()["rows"]
    linked = next(r for r in rows if r["flashcard_id"] == FC_NUGGET_LINKED)
    unlinked = next(r for r in rows if r["flashcard_id"] == FC_NUGGET_UNLINKED)
    assert linked["nugget_id"] == NUGGET_COGITO_ID
    assert unlinked["nugget_id"] is None


def test_upsert_omitted_nugget_id_leaves_existing_assignment_untouched(client):
    """Scenario: Flashcard upsert with nugget_id omitted leaves an existing assignment untouched."""
    r = client.post("/api/essaycards/flashcards/upsert", json={
        "essay_slug": ESSAY_F_SLUG, "section_id": SECTION_F1_ID,
        "card": {"id": "fc-nugget-linked", "level": 2, "q": "q edited", "a": "a edited"},
    })
    assert r.status_code == 200, r.text
    assert _current_nugget_id(client, FC_NUGGET_LINKED) == NUGGET_COGITO_ID


def test_upsert_explicit_null_nugget_id_clears_assignment(client):
    """Scenario: Flashcard upsert with nugget_id explicit null clears an existing assignment."""
    r = client.post("/api/essaycards/flashcards/upsert", json={
        "essay_slug": ESSAY_F_SLUG, "section_id": SECTION_F1_ID,
        "card": {"id": "fc-nugget-linked", "level": 2, "q": "q", "a": "a", "nugget_id": None},
    })
    assert r.status_code == 200, r.text
    assert _current_nugget_id(client, FC_NUGGET_LINKED) is None


def test_upsert_valid_nugget_id_sets_assignment(client):
    """Scenario: Flashcard upsert with a valid nugget_id sets the assignment."""
    assert _current_nugget_id(client, FC_NUGGET_UNLINKED) is None
    r = client.post("/api/essaycards/flashcards/upsert", json={
        "essay_slug": ESSAY_F_SLUG, "section_id": SECTION_F1_ID,
        "card": {"id": "fc-nugget-unlinked", "level": 2, "q": "q", "a": "a", "nugget_id": NUGGET_WAX_ID},
    })
    assert r.status_code == 200, r.text
    assert _current_nugget_id(client, FC_NUGGET_UNLINKED) == NUGGET_WAX_ID


def test_upsert_unresolvable_nugget_id_rejected_assignment_unchanged(client):
    """Scenario: Flashcard upsert with an unresolvable nugget_id is rejected without side effects."""
    bogus = "00000000-0000-0000-0000-000000000000"
    r = client.post("/api/essaycards/flashcards/upsert", json={
        "essay_slug": ESSAY_F_SLUG, "section_id": SECTION_F1_ID,
        "card": {"id": "fc-nugget-linked", "level": 2, "q": "q", "a": "a", "nugget_id": bogus},
    })
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert _current_nugget_id(client, FC_NUGGET_LINKED) == NUGGET_COGITO_ID


def test_export_question_includes_nugget_id(client):
    """Scenario: Single-question export includes nugget_id."""
    r = client.get(f"/api/essaycards/flashcards/{FC_NUGGET_LINKED}/export")
    assert r.status_code == 200
    assert r.json()["card"]["nugget_id"] == NUGGET_COGITO_ID
