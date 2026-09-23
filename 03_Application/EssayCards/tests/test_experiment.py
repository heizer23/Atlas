"""
EssayCards — tests for GET /api/essaycards/experiment/summary
(Sprint10_DualSchedulerAB).

Traceability: each function name maps to a scenario in
Sprint10_DualSchedulerAB/10_test_spec.md. Uses the review_events fixture
rows in tests/fixtures.sql (fc000023 fsrs / fc000025 classic — see that
file's "Sprint10_DualSchedulerAB" section for the exact fixture layout) plus
one dedicated test that clears review_events to exercise the zero-fill case.
"""

URL = "/api/essaycards/experiment/summary"


def _rows_by_scheduler(body: dict) -> dict:
    return {row["scheduler"]: row for row in body["rows"]}


def test_experiment_summary_returns_two_fixed_rows_zero_filled(client, db_conn):
    """Scenario: Experiment summary always returns exactly two rows
    (classic, fsrs), zero-filled counts and null recall_rate when a
    scheduler has no due reviews."""
    with db_conn.cursor() as cur:
        cur.execute("delete from essaycards.review_events")

    r = client.get(URL)
    assert r.status_code == 200
    body = r.json()

    assert body["meta"]["total"] == 2
    assert [row["scheduler"] for row in body["rows"]] == ["classic", "fsrs"]

    for row in body["rows"]:
        assert row["completed_reviews"] == 0
        assert row["ordinary_due_reviews"] == 0
        assert row["failures"] == 0
        assert row["reviewed_cards"] == 0
        assert row["recall_rate"] is None  # null, not 0 — "no data yet" != "0% recall"
        # assigned_cards/cards_new/etc. still reflect real fixture data —
        # zero-filling applies to review counts, not assignment counts.
        assert row["assigned_cards"] >= 0


def test_experiment_summary_reports_assigned_reviewed_completed_and_recall_with_sample_size(client, db_conn):
    """Scenario: Experiment summary reports real recorded per-scheduler data
    with exposed sample sizes — assigned/reviewed/completed counts, a
    recall_rate restricted to events whose prior_review_interval was >= 24
    hours (per the corrected filter), with its sample size
    (ordinary_due_reviews) exposed alongside it, and failures counted only
    among those same events."""
    # Ground truth computed directly from the DB, independent of the
    # endpoint's own SQL, so this test doesn't just restate the
    # implementation.
    with db_conn.cursor() as cur:
        cur.execute(
            """
            select frs.scheduler as scheduler,
                   count(distinct frs.flashcard_id) as assigned_cards,
                   count(distinct rev.flashcard_id) as reviewed_cards,
                   count(rev.id) as completed_reviews,
                   count(rev.id) filter (where rev.prior_review_interval >= interval '24 hours') as ordinary_due_reviews,
                   count(rev.id) filter (
                       where rev.prior_review_interval >= interval '24 hours' and rev.grade = 'again'
                   ) as failures
            from essaycards.flashcard_review_state frs
            left join essaycards.review_events rev on rev.flashcard_id = frs.flashcard_id
                and rev.scheduler = frs.scheduler
            group by frs.scheduler
            """
        )
        expected = {row["scheduler"]: dict(row) for row in cur.fetchall()}

    r = client.get(URL)
    assert r.status_code == 200
    rows = _rows_by_scheduler(r.json())

    for scheduler in ("classic", "fsrs"):
        exp = expected[scheduler]
        got = rows[scheduler]
        assert got["assigned_cards"] == exp["assigned_cards"]
        assert got["completed_reviews"] == exp["completed_reviews"]
        assert got["ordinary_due_reviews"] == exp["ordinary_due_reviews"]
        assert got["failures"] == exp["failures"]

        ordinary = exp["ordinary_due_reviews"]
        failures = exp["failures"]
        if ordinary > 0:
            assert got["recall_rate"] == (ordinary - failures) / ordinary
        else:
            assert got["recall_rate"] is None

    # The fixture world's classic row (fc000025) has 2 ordinary-due events
    # (1 success, 1 failure) -> recall_rate 0.5; the fsrs row (fc000023) has
    # 1 ordinary-due success -> recall_rate 1.0. See tests/fixtures.sql.
    assert rows["classic"]["ordinary_due_reviews"] >= 2
    assert rows["classic"]["recall_rate"] == 0.5
    assert rows["fsrs"]["ordinary_due_reviews"] >= 1
    assert rows["fsrs"]["recall_rate"] == 1.0


def test_experiment_summary_excludes_non_due_reviews_from_recall_sample(client):
    """Scenario: A rapid-retry review with a short prior interval is
    excluded from ordinary due-review evidence — counted in
    completed_reviews but excluded from ordinary_due_reviews/recall_rate/
    failures, because the filter is prior_review_interval >= interval '24
    hours', not was_due (which is true for both the included and excluded
    fixture rows here — see tests/fixtures.sql)."""
    r = client.get(URL)
    assert r.status_code == 200
    rows = _rows_by_scheduler(r.json())

    # classic: 3 completed_reviews total (2 ordinary-due + 1 rapid retry with
    # prior_review_interval=10min, was_due=true) -> completed > ordinary_due.
    assert rows["classic"]["completed_reviews"] > rows["classic"]["ordinary_due_reviews"]
    assert rows["classic"]["completed_reviews"] >= 3
    assert rows["classic"]["ordinary_due_reviews"] == 2

    # fsrs: 2 completed_reviews total (1 ordinary-due + 1 rapid retry with
    # prior_review_interval=30s, was_due=true) -> completed > ordinary_due.
    assert rows["fsrs"]["completed_reviews"] > rows["fsrs"]["ordinary_due_reviews"]
    assert rows["fsrs"]["completed_reviews"] >= 2
    assert rows["fsrs"]["ordinary_due_reviews"] == 1
