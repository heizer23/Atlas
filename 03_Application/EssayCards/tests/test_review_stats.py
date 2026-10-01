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
    """Scenario: Aggregation combines classic and fsrs reviews with no
    per-scheduler breakdown in the response — the week window's fixture data
    spans both schedulers (fc000025=classic, fc000023=fsrs)."""
    r = client.get(URL)
    assert r.status_code == 200
    body = r.json()

    for row in body["rows"]:
        assert "scheduler" not in row
        assert set(row.keys()) == {
            "period", "reviews", "unique_cards", "again_count", "hard_count",
            "good_count", "easy_count", "failures", "recall_rate",
        }

    with db_conn.cursor() as cur:
        cur.execute(
            "select count(distinct scheduler) as n from essaycards.review_events "
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
