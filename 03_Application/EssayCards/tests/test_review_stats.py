"""
EssayCards — tests for GET /api/essaycards/review-stats/summary
(Sprint11_ReviewStats).

Traceability: each function name maps to a scenario in
Sprint11_ReviewStats/10_test_spec.md.

This endpoint aggregates essaycards.review_events with NO scope filter
(global, across every essay) and NO scheduler/prior_review_interval filter
— unlike GET /experiment/summary. The fixture world (tests/fixtures.sql,
"Sprint10_DualSchedulerAB" + "Sprint11_ReviewStats" sections) has exactly
11 review_events rows total, all on the two pre-existing established cards
fc000025 (classic) / fc000023 (fsrs) — see that file for why new rows reuse
these two cards rather than introducing new ones. The expected
day/week/month composition below is derived directly from those 11 rows'
timestamps/grades, independent of the endpoint's own SQL.
"""

URL = "/api/essaycards/review-stats/summary"


def _rows_by_period(body: dict) -> dict:
    return {row["period"]: row for row in body["rows"]}


def _expected_window(db_conn, interval_literal: str) -> dict:
    """Ground truth computed directly from the DB, independent of the
    endpoint's own SQL — same convention as test_experiment.py's second
    test."""
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            select
                count(*) as reviews,
                count(distinct flashcard_id) as unique_cards,
                count(*) filter (where grade = 'again') as again_count,
                count(*) filter (where grade = 'hard') as hard_count,
                count(*) filter (where grade = 'good') as good_count,
                count(*) filter (where grade = 'easy') as easy_count
            from essaycards.review_events
            where reviewed_at >= now() - interval '{interval_literal}'
            """
        )
        return dict(cur.fetchone())


def test_review_stats_summary_returns_three_fixed_rows_in_order(client):
    """Scenario: Always three fixed rows in day/week/month order."""
    r = client.get(URL)
    assert r.status_code == 200
    body = r.json()
    assert body["meta"]["total"] == 3
    assert [row["period"] for row in body["rows"]] == ["day", "week", "month"]


def test_review_stats_day_window_excludes_reviews_older_than_24_hours(client, db_conn):
    """Scenario: Day window excludes reviews older than 24 hours; week/month
    windows are wider and overlapping, not exclusive — a review counted in
    day is also counted in week and month.

    Fixture composition (see tests/fixtures.sql): day = the ~30min/~20min
    (Sprint10) plus ~2h/~1h (Sprint11) rows (4 reviews); week adds the
    ~4d/~3d(x2)/~2d-ago rows (5 more, 9 total); month adds the ~20d-ago row
    (1 more, 10 total) but never the ~40d-ago row."""
    r = client.get(URL)
    assert r.status_code == 200
    rows = _rows_by_period(r.json())

    for period, interval_literal in (("day", "24 hours"), ("week", "7 days"), ("month", "30 days")):
        expected = _expected_window(db_conn, interval_literal)
        assert rows[period]["reviews"] == expected["reviews"]
        assert rows[period]["unique_cards"] == expected["unique_cards"]

    assert rows["day"]["reviews"] == 4
    assert rows["week"]["reviews"] == 9
    assert rows["month"]["reviews"] == 10

    # Windows overlap, they do not partition: day's reviews are a subset of
    # week's, which are a subset of month's.
    assert rows["day"]["reviews"] <= rows["week"]["reviews"] <= rows["month"]["reviews"]


def test_review_stats_grade_breakdown_sums_to_reviews(client, db_conn):
    """Scenario: Grade breakdown sums to reviews count; failures equals
    again_count, for every window row."""
    r = client.get(URL)
    assert r.status_code == 200
    body = r.json()

    for row in body["rows"]:
        assert row["again_count"] + row["hard_count"] + row["good_count"] + row["easy_count"] == row["reviews"]
        assert row["failures"] == row["again_count"]

    week = _rows_by_period(body)["week"]
    expected = _expected_window(db_conn, "7 days")
    assert week["again_count"] == expected["again_count"] == 4
    assert week["hard_count"] == expected["hard_count"] == 1
    assert week["good_count"] == expected["good_count"] == 4
    assert week["easy_count"] == expected["easy_count"] == 0


def test_review_stats_recall_rate_is_null_when_window_has_zero_reviews(client, db_conn):
    """Scenario: Recall rate is null (not 0) when a window has zero
    reviews."""
    with db_conn.cursor() as cur:
        cur.execute("delete from essaycards.review_events")

    r = client.get(URL)
    assert r.status_code == 200
    for row in r.json()["rows"]:
        assert row["reviews"] == 0
        assert row["unique_cards"] == 0
        assert row["again_count"] == row["hard_count"] == row["good_count"] == row["easy_count"] == 0
        assert row["failures"] == 0
        assert row["recall_rate"] is None  # null, not 0 — "no data yet" != "0% recall"


def test_review_stats_recall_rate_computed_from_reviews_and_failures(client, db_conn):
    """Scenario: Recall rate computed correctly when reviews exist —
    recall_rate == (reviews - failures) / reviews, for the month row (10
    reviews, 4 'again' failures per the fixture composition -> 0.6)."""
    r = client.get(URL)
    assert r.status_code == 200
    rows = _rows_by_period(r.json())

    month = rows["month"]
    expected = _expected_window(db_conn, "30 days")
    assert month["reviews"] == expected["reviews"] == 10
    assert month["failures"] == 4
    assert month["recall_rate"] == (month["reviews"] - month["failures"]) / month["reviews"]
    assert month["recall_rate"] == 0.6


def test_review_stats_aggregation_is_scheduler_agnostic(client, db_conn):
    """Scenario: Aggregation has no per-scheduler breakdown in the response
    (the concept no longer exists — review_events.scheduler was dropped this
    sprint) — the week window's fixture data spans two distinct cards
    (fc000025, fc000023)."""
    r = client.get(URL)
    assert r.status_code == 200
    body = r.json()

    for row in body["rows"]:
        assert "scheduler" not in row
        assert set(row.keys()) == {
            "period", "reviews", "unique_cards", "again_count", "hard_count",
            "good_count", "easy_count", "failures", "recall_rate", "new_count",
            "orals_count", "guided_orals_count", "unguided_orals_count",  # Sprint15
        }

    with db_conn.cursor() as cur:
        cur.execute(
            "select count(distinct flashcard_id) as n from essaycards.review_events "
            "where reviewed_at >= now() - interval '7 days'"
        )
        assert cur.fetchone()["n"] == 2


def test_review_stats_includes_rapid_retry_reviews(client, db_conn):
    """Scenario: A review_events row with a short prior_review_interval
    (rapid retry) is still counted — no prior_review_interval filter,
    unlike GET /experiment/summary's ordinary_due_reviews filter. The
    fixture's ~1h-ago fsrs 'again' row has prior_review_interval='30
    seconds' (a rapid retry) yet must still appear in the day row — as do
    the other three day-window rows, which are also short-prior-interval
    rapid retries by fixture design (see tests/fixtures.sql)."""
    with db_conn.cursor() as cur:
        cur.execute(
            "select count(*) as n from essaycards.review_events "
            "where reviewed_at >= now() - interval '24 hours' "
            "and prior_review_interval < interval '24 hours'"
        )
        assert cur.fetchone()["n"] == 4  # every day-window row is a rapid retry

    r = client.get(URL)
    assert r.status_code == 200
    rows = _rows_by_period(r.json())

    assert rows["day"]["reviews"] == 4
    assert rows["day"]["again_count"] == 2  # the two fsrs rapid-retry 'again' rows


# ── GET /review-stats/activity (Sprint12_FSRSAndUXOverhaul) ─────────────────

ACTIVITY_URL = "/api/essaycards/review-stats/activity"


def test_activity_returns_thirty_zero_filled_utc_days(client):
    """Scenario: GET /review-stats/activity always returns exactly 30 rows,
    oldest UTC calendar day first, with 0 reviews on every day with no
    recorded review."""
    r = client.get(ACTIVITY_URL)
    assert r.status_code == 200
    body = r.json()
    rows = body["rows"]
    assert len(rows) == 30
    assert body["meta"]["total"] == 30

    dates = [row["date"] for row in rows]
    assert dates == sorted(dates)  # oldest first
    assert all(row["recalls"] >= 0 for row in rows)
    # Every fixture review is recent (within the last 40 days at most, per
    # tests/fixtures.sql); at least one day in the trailing 30-day window has
    # zero reviews (the window is mostly empty).
    assert any(row["recalls"] == 0 for row in rows)


def test_activity_counts_reviews_on_the_correct_utc_day(client, db_conn):
    """Scenario: a review recorded near a UTC day boundary is counted on the
    correct side of it."""
    with db_conn.cursor() as cur:
        cur.execute("delete from essaycards.review_events")
        cur.execute(
            """
            insert into essaycards.review_events
                (flashcard_id, grade, reviewed_at, was_due, prior_review_interval, resulting_review_interval)
            values
                ('fc000025-0000-0000-0000-000000000025', 'good',
                 date_trunc('day', now() at time zone 'utc') + interval '1 minute',
                 true, interval '1 day', interval '2 days')
            """
        )

    r = client.get(ACTIVITY_URL)
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert rows[-1]["recalls"] == 1  # today (UTC) is the last row — oldest-first order
    assert sum(row["recalls"] for row in rows) == 1


# ── Sprint13_ReviewStatsSentenceFeedback ────────────────────────────────────

TODAY_URL = "/api/essaycards/review-stats/today"
A1 = "fc000001-0000-0000-0000-000000000001"   # essay A
A2 = "fc000002-0000-0000-0000-000000000002"   # essay A
B1 = "fc000005-0000-0000-0000-000000000005"   # essay B
ESSAY_A = "ea000001-0000-0000-0000-000000000001"
ESSAY_B = "ea000002-0000-0000-0000-000000000002"
SECTION_A_ORIGINS = "ec000001-0000-0000-0000-000000000001"

# UTC midnight of today as a timestamptz expression.
_TODAY_START = "(date_trunc('day', now() at time zone 'utc') at time zone 'utc')"


def _clear_events(db_conn):
    with db_conn.cursor() as cur:
        cur.execute("delete from essaycards.review_events")


def _add_event(db_conn, card_id, when_sql, grade="good"):
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            insert into essaycards.review_events
                (flashcard_id, grade, reviewed_at, was_due, prior_review_interval, resulting_review_interval)
            values (%s, %s, {when_sql}, true, interval '1 day', interval '2 days')
            """,
            (card_id, grade),
        )


def _today_row(client, qs=""):
    r = client.get(TODAY_URL + qs)
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert len(rows) == 1
    return rows[0]


def test_today_endpoint_no_scope_returns_global_counts(client, db_conn):
    _clear_events(db_conn)
    _add_event(db_conn, A1, f"{_TODAY_START} + interval '1 minute'")
    _add_event(db_conn, A2, f"{_TODAY_START} + interval '2 minutes'")
    _add_event(db_conn, B1, f"{_TODAY_START} + interval '3 minutes'")
    row = _today_row(client)
    assert row["recalls"] == 3
    assert row["unique_cards_seen"] == 3


def test_today_endpoint_scoped_by_essay_and_section(client, db_conn):
    _clear_events(db_conn)
    _add_event(db_conn, A1, f"{_TODAY_START} + interval '1 minute'")
    _add_event(db_conn, B1, f"{_TODAY_START} + interval '2 minutes'")
    assert _today_row(client, f"?essay_id={ESSAY_A}")["recalls"] == 1
    assert _today_row(client, f"?essay_id={ESSAY_B}")["recalls"] == 1
    assert _today_row(client, f"?essay_id={ESSAY_A}&section_id={SECTION_A_ORIGINS}")["recalls"] == 1
    assert _today_row(client, f"?essay_id={ESSAY_B}&section_id={SECTION_A_ORIGINS}")["recalls"] == 0


def test_today_endpoint_no_reviews_yields_zero_row_not_empty(client, db_conn):
    _clear_events(db_conn)
    row = _today_row(client)
    assert (row["recalls"], row["unique_cards_seen"], row["first_cards_seen"]) == (0, 0, 0)


def test_today_endpoint_section_id_without_essay_id_is_rejected(client):
    r = client.get(f"{TODAY_URL}?section_id={SECTION_A_ORIGINS}")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_today_endpoint_topic_combined_with_essay_id_is_rejected(client):
    r = client.get(f"{TODAY_URL}?topic=Philosophy&essay_id={ESSAY_A}")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_today_endpoint_repeat_reviews_count_once_in_unique(client, db_conn):
    _clear_events(db_conn)
    for minutes in (1, 2, 3):
        _add_event(db_conn, A1, f"{_TODAY_START} + interval '{minutes} minutes'")
    row = _today_row(client, f"?essay_id={ESSAY_A}")
    assert row["recalls"] == 3
    assert row["unique_cards_seen"] == 1
    assert row["first_cards_seen"] == 1


def test_today_endpoint_first_review_from_yesterday_does_not_count_as_first_today(client, db_conn):
    _clear_events(db_conn)
    _add_event(db_conn, A1, f"{_TODAY_START} - interval '1 hour'")
    _add_event(db_conn, A1, f"{_TODAY_START} + interval '1 minute'")
    row = _today_row(client, f"?essay_id={ESSAY_A}")
    assert row["recalls"] == 1
    assert row["unique_cards_seen"] == 1
    assert row["first_cards_seen"] == 0


def test_activity_endpoint_reshaped_row_matches_the_worked_example(client, db_conn):
    """20 recalls, 12 distinct cards, 2 first-ever -> repeat 8 / unique 10 / first 2."""
    _clear_events(db_conn)
    with db_conn.cursor() as cur:
        cur.execute("select id::text as id from essaycards.flashcards order by card_key limit 12")
        cards = [r["id"] for r in cur.fetchall()]
    assert len(cards) == 12
    day = f"({_TODAY_START} - interval '3 days' + interval '12 hours')"
    # 10 cards were already seen earlier, so only cards[0] and cards[1] are first-ever on that day.
    for c in cards[2:]:
        _add_event(db_conn, c, f"{day} - interval '10 days'")
    for i, c in enumerate(cards):
        _add_event(db_conn, c, f"{day} + interval '{i} minutes'")
    for i in range(8):  # 8 repeats of cards[0]
        _add_event(db_conn, cards[0], f"{day} + interval '{30 + i} minutes'", grade="again" if i < 2 else "good")

    rows = client.get(ACTIVITY_URL).json()["rows"]
    row = rows[-4]  # today is rows[-1]; 3 days ago is rows[-4]
    assert (row["recalls"], row["unique_cards_seen"], row["first_cards_seen"]) == (20, 12, 2)
    repeat = row["recalls"] - row["unique_cards_seen"]
    unique_segment = row["unique_cards_seen"] - row["first_cards_seen"]
    assert (repeat, unique_segment, row["first_cards_seen"]) == (8, 10, 2)
    assert row["recall_rate"] == (20 - 2) / 20


def test_activity_endpoint_recall_rate_is_null_not_zero_on_a_day_with_no_reviews(client, db_conn):
    _clear_events(db_conn)
    rows = client.get(ACTIVITY_URL).json()["rows"]
    assert len(rows) == 30
    for row in rows:
        assert row["recalls"] == 0 and row["unique_cards_seen"] == 0 and row["first_cards_seen"] == 0
        assert row["recall_rate"] is None


def test_summary_endpoint_new_cards_seen_reflects_first_ever_reviews_inside_each_window(client, db_conn):
    _clear_events(db_conn)
    _add_event(db_conn, A1, "now() - interval '10 days'")
    rows = _rows_by_period(client.get(URL).json())
    assert rows["day"]["new_count"] == 0
    assert rows["week"]["new_count"] == 0
    assert rows["month"]["new_count"] == 1


# ── GET /review-stats/intervals (Sprint12_FSRSAndUXOverhaul) ────────────────

INTERVALS_URL = "/api/essaycards/review-stats/intervals"


def test_intervals_returns_six_zero_filled_buckets_summing_to_total_scheduled(client, db_conn):
    """Scenario: GET /review-stats/intervals always returns exactly six rows
    whose counts sum to the total number of flashcard_review_state rows."""
    r = client.get(INTERVALS_URL)
    assert r.status_code == 200
    body = r.json()
    rows = body["rows"]
    assert len(rows) == 6
    assert [row["bucket"] for row in rows] == [
        "new", "within_1_day", "within_7_days", "within_30_days", "within_90_days", "beyond_90_days",
    ]

    with db_conn.cursor() as cur:
        cur.execute("select count(*) as n from essaycards.flashcard_review_state")
        total = cur.fetchone()["n"]

    assert sum(row["count"] for row in rows) == total
    assert total > 0


# ── Sprint15: oral counts in the summary rows ───────────────────────────────

def _expected_orals(db_conn, interval_literal: str) -> dict:
    """Ground truth straight from the DB: section + essay scope combined."""
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            select count(*) as total,
                   count(*) filter (where exam_type = 'guided') as guided,
                   count(*) filter (where exam_type = 'unguided') as unguided
            from (
                select examined_at, exam_type from essaycards.section_examinations
                union all
                select examined_at, exam_type from essaycards.essay_examinations
            ) x
            where examined_at >= now() - interval '{interval_literal}'
            """
        )
        return dict(cur.fetchone())


def test_summary_rows_carry_oral_counts_per_window(client, db_conn):
    """Scenario: each row has orals_count / guided_orals_count / unguided_orals_count
    equal to the section+essay exam rows inside that window; guided + unguided = total."""
    rows = _rows_by_period(client.get(URL).json())
    for period, interval_literal in (("day", "24 hours"), ("week", "7 days"), ("month", "30 days")):
        exp = _expected_orals(db_conn, interval_literal)
        assert rows[period]["orals_count"] == exp["total"]
        assert rows[period]["guided_orals_count"] == exp["guided"]
        assert rows[period]["unguided_orals_count"] == exp["unguided"]
        assert rows[period]["guided_orals_count"] + rows[period]["unguided_orals_count"] == rows[period]["orals_count"]
    assert rows["day"]["orals_count"] <= rows["week"]["orals_count"] <= rows["month"]["orals_count"]
