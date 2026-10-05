"""
GET /review-stats/summary, GET /review-stats/activity, GET /review-stats/intervals
— the stats page's data endpoints.

GET /review-stats/summary (Sprint11_ReviewStats). Reports on the reviewer's
actual completed review history over three fixed, independent rolling windows
off Postgres now() — day (24 hours), week (7 days), month (30 days), in that
order. Always exactly three rows, never omitted, even when a window has zero
reviews.

Scheduler-agnostic by construction since Sprint12_FSRSAndUXOverhaul made FSRS
the sole scheduler (docstring previously framed this as "across both Classic
and FSRS" — that framing is now meaningless and has been dropped; the
behavior/shape is otherwise unchanged).

recall_rate is null (not 0) when a window has zero reviews — "no data yet"
and "0% recall" are different facts. failures is always exactly equal to
again_count, named separately only because recall_rate is derived from it and
the two must always be read together.

GET /review-stats/activity (Sprint12_FSRSAndUXOverhaul, NEW). Daily review-
count time series, trailing 30 UTC calendar days, zero-filled. See
_activity_rows.

GET /review-stats/intervals (Sprint12_FSRSAndUXOverhaul, NEW). Current
review_interval distribution across every scheduled card, six fixed
zero-filled buckets — "how mature is my deck", distinct from the next-due
forecast GET /flashcards/stats already provides. See _interval_bucket_rows.
"""

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.database import get_db
from platform_contracts import ColumnSchema, Dataset, DatasetMeta
from platform_errorhandling import api_error

router = APIRouter(prefix="/review-stats", tags=["review_stats"])

REVIEW_STATS_SUMMARY_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="period", label="Period", type="string", sortable=False, filterable=False),
    ColumnSchema(key="reviews", label="Reviews", type="number", sortable=False, filterable=False),
    ColumnSchema(key="unique_cards", label="Unique cards", type="number", sortable=False, filterable=False),
    ColumnSchema(key="again_count", label="Again", type="number", sortable=False, filterable=False),
    ColumnSchema(key="hard_count", label="Hard", type="number", sortable=False, filterable=False),
    ColumnSchema(key="good_count", label="Good", type="number", sortable=False, filterable=False),
    ColumnSchema(key="easy_count", label="Easy", type="number", sortable=False, filterable=False),
    ColumnSchema(key="failures", label="Failures", type="number", sortable=False, filterable=False),
    ColumnSchema(key="recall_rate", label="Recall rate", type="number", sortable=False, filterable=False),
    ColumnSchema(key="new_count", label="New cards seen", type="number", sortable=False, filterable=False),
]

# FIRST-EVER REVIEW (Sprint13, single canonical definition): a review_events
# row is a card's first-ever review iff its reviewed_at equals this CTE body's
# min(reviewed_at) for that flashcard_id over the ENTIRE unscoped, unwindowed
# table. Composed identically into summary, activity and today.
_FIRST_EVER_CTE_SQL = (
    "select flashcard_id, min(reviewed_at) as first_reviewed_at "
    "from essaycards.review_events group by flashcard_id"
)

# Single source of both the SQL window boundaries and the fixed output row order.
_WINDOWS: tuple[tuple[str, str], ...] = (
    ("day", "24 hours"),
    ("week", "7 days"),
    ("month", "30 days"),
)

_GRADES: tuple[str, ...] = ("again", "hard", "good", "easy")


def _review_stats_aggregate(cur: Any) -> dict[str, Any]:
    """One SQL statement, one row of 3 windows * (2 + 4 grades) = 18 scalar
    aggregates over essaycards.review_events, outer-restricted to the last 30
    days (the widest window — day/week are subsets, so this bound never
    excludes a row any window needs)."""
    select_parts: list[str] = []
    for period, interval_literal in _WINDOWS:
        select_parts.append(
            f"count(*) filter (where e.reviewed_at >= now() - interval '{interval_literal}') "
            f"as {period}_reviews"
        )
        select_parts.append(
            f"count(distinct e.flashcard_id) filter (where e.reviewed_at >= now() - interval '{interval_literal}') "
            f"as {period}_unique_cards"
        )
        for grade in _GRADES:
            select_parts.append(
                f"count(*) filter (where e.reviewed_at >= now() - interval '{interval_literal}' "
                f"and e.grade = '{grade}') as {period}_{grade}_count"
            )
        # new_count: cards whose first-ever review falls inside this rolling window.
        select_parts.append(
            f"count(distinct e.flashcard_id) filter (where e.reviewed_at >= now() - interval '{interval_literal}' "
            f"and e.reviewed_at = fe.first_reviewed_at) as {period}_new_count"
        )

    query = (
        "select " + ", ".join(select_parts) + " "
        "from essaycards.review_events e "
        f"join ({_FIRST_EVER_CTE_SQL}) fe on fe.flashcard_id = e.flashcard_id "
        "where e.reviewed_at >= now() - interval '30 days'"
    )
    cur.execute(query)
    return dict(cur.fetchone())


def _build_summary_rows(aggregate: dict[str, Any]) -> list[dict[str, Any]]:
    """Builds exactly 3 row dicts, day/week/month in that fixed order."""
    rows: list[dict[str, Any]] = []
    for period, _interval_literal in _WINDOWS:
        reviews = int(aggregate.get(f"{period}_reviews") or 0)
        unique_cards = int(aggregate.get(f"{period}_unique_cards") or 0)
        grade_counts = {
            grade: int(aggregate.get(f"{period}_{grade}_count") or 0)
            for grade in _GRADES
        }
        failures = grade_counts["again"]
        recall_rate = (reviews - failures) / reviews if reviews > 0 else None
        rows.append({
            "period": period,
            "reviews": reviews,
            "unique_cards": unique_cards,
            "again_count": grade_counts["again"],
            "hard_count": grade_counts["hard"],
            "good_count": grade_counts["good"],
            "easy_count": grade_counts["easy"],
            "failures": failures,
            "recall_rate": recall_rate,
            "new_count": int(aggregate.get(f"{period}_new_count") or 0),
        })
    return rows


def _dataset_response(dataset: Dataset) -> JSONResponse:
    return JSONResponse(content=dataset.model_dump(by_alias=True, mode="json"))


@router.get("/summary", response_model=None)
def get_review_stats_summary() -> JSONResponse:
    """
    Review-performance dashboard data source: how the reviewer did over the
    trailing day/week/month, aggregated across every essay and both
    schedulers. Always exactly three rows, day/week/month, in that order. No
    parameters. Server time only (R-CON-AL-06) — every count is read live at
    request time via Postgres now().
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            aggregate = _review_stats_aggregate(cur)

    rows = _build_summary_rows(aggregate)

    dataset = Dataset(
        meta=DatasetMeta(
            object_type="review_stats_summary",
            label="Review Stats Summary",
            total=len(rows),
            page=1,
            page_size=len(rows),
            row_actions=[],
        ),
        **{"schema": REVIEW_STATS_SUMMARY_SCHEMA},
        rows=rows,
    )
    return _dataset_response(dataset)


# ── GET /review-stats/activity (Sprint12_FSRSAndUXOverhaul) ─────────────────

ACTIVITY_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="date",              label="Date",              type="date",   sortable=True,  filterable=False),
    ColumnSchema(key="recalls",           label="Recalls",           type="number", sortable=False, filterable=False),
    ColumnSchema(key="unique_cards_seen", label="Unique cards seen", type="number", sortable=False, filterable=False),
    ColumnSchema(key="first_cards_seen",  label="First cards seen",  type="number", sortable=False, filterable=False),
    ColumnSchema(key="recall_rate",       label="Recall rate",       type="number", sortable=False, filterable=False),
]


def _activity_rows(cur: Any) -> list[dict[str, Any]]:
    """
    One SQL statement producing exactly 30 zero-filled day rows, oldest first
    — the 30 most recent UTC calendar days ending today (UTC). Per day:
    recalls (all reviews), unique_cards_seen (distinct cards), first_cards_seen
    (distinct cards whose first-ever review is that day's), recall_rate
    ((recalls - again) / recalls, null when recalls = 0). generate_series
    builds the day spine so empty days still appear (R-CON-AL-06: UTC calendar
    days, server time).
    """
    cur.execute(
        f"""
        with days as (
            select generate_series(
                date_trunc('day', now() at time zone 'utc') - interval '29 days',
                date_trunc('day', now() at time zone 'utc'),
                interval '1 day'
            ) as day
        ),
        first_ever as ({_FIRST_EVER_CTE_SQL}),
        day_agg as (
            select date_trunc('day', e.reviewed_at at time zone 'utc') as day,
                   count(*) as recalls,
                   count(distinct e.flashcard_id) as unique_cards_seen,
                   count(distinct e.flashcard_id) filter (where e.reviewed_at = fe.first_reviewed_at) as first_cards_seen,
                   count(*) filter (where e.grade = 'again') as again_count
            from essaycards.review_events e
            join first_ever fe on fe.flashcard_id = e.flashcard_id
            where e.reviewed_at >= date_trunc('day', now() at time zone 'utc') - interval '29 days'
            group by 1
        )
        select
            to_char(d.day, 'YYYY-MM-DD') as date,
            coalesce(a.recalls, 0)::int as recalls,
            coalesce(a.unique_cards_seen, 0)::int as unique_cards_seen,
            coalesce(a.first_cards_seen, 0)::int as first_cards_seen,
            case when coalesce(a.recalls, 0) > 0
                 then (a.recalls - a.again_count)::float / a.recalls
                 else null end as recall_rate
        from days d
        left join day_agg a on a.day = d.day
        order by d.day asc
        """
    )
    return [dict(r) for r in cur.fetchall()]


@router.get("/activity", response_model=None)
def get_review_activity() -> JSONResponse:
    """
    Study activity over time — daily review counts, trailing 30 UTC calendar
    days. No parameters. Always exactly 30 rows, oldest first, zero-filled.
    Time basis: UTC calendar days (R-CON-AL-01/06) — see _activity_rows.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            rows = _activity_rows(cur)

    dataset = Dataset(
        meta=DatasetMeta(
            object_type="review_activity_day",
            label="Study Activity",
            total=len(rows),
            page=1,
            page_size=len(rows),
            row_actions=[],
        ),
        **{"schema": ACTIVITY_SCHEMA},
        rows=rows,
    )
    return _dataset_response(dataset)


# ── GET /review-stats/today (Sprint13_ReviewStatsSentenceFeedback) ──────────

TODAY_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="recalls",           label="Recalls", type="number", sortable=False, filterable=False),
    ColumnSchema(key="unique_cards_seen", label="Unique",  type="number", sortable=False, filterable=False),
    ColumnSchema(key="first_cards_seen",  label="First",   type="number", sortable=False, filterable=False),
]


@router.get("/today", response_model=None)
def get_review_today(
    topic: str | None = None,
    essay_id: str | None = None,
    section_id: str | None = None,
) -> JSONResponse:
    """
    Today's (UTC calendar day, server clock) recalls / unique cards / first-ever
    cards, optionally scoped. Same scope rules as GET /flashcards/due: allowed
    {}, {topic}, {essay_id}, {essay_id, section_id}; section_id without
    essay_id, or topic with essay_id/section_id -> VALIDATION_ERROR.
    Always exactly one row; zero reviews yields zeros, never an empty Dataset.
    Boundary: [date_trunc('day', now() at time zone 'utc'), + 1 day) — distinct
    from /summary's rolling 24h day.
    """
    if section_id and not essay_id:
        return api_error("VALIDATION_ERROR", "section_id requires essay_id to also be provided")
    if topic and (essay_id or section_id):
        return api_error(
            "VALIDATION_ERROR", "topic cannot be combined with essay_id or section_id"
        )

    conditions: list[str] = []
    params: list[Any] = []
    extra_join = ""
    if topic:
        extra_join = "join essaycards.essays es on es.id = f.essay_id"
        conditions.append("es.category = %s")
        params.append(topic)
    if essay_id:
        conditions.append("f.essay_id::text = %s")
        params.append(essay_id)
    if section_id:
        conditions.append("f.section_id::text = %s")
        params.append(section_id)
    where = ("where " + " and ".join(conditions)) if conditions else ""

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                with scoped_flashcards as (
                    select f.id from essaycards.flashcards f {extra_join} {where}
                ),
                first_ever as ({_FIRST_EVER_CTE_SQL}),
                today as (
                    select date_trunc('day', now() at time zone 'utc') as start_utc
                )
                select
                    count(e.id)::int as recalls,
                    count(distinct e.flashcard_id)::int as unique_cards_seen,
                    count(distinct e.flashcard_id) filter (where e.reviewed_at = fe.first_reviewed_at)::int
                        as first_cards_seen
                from scoped_flashcards sf
                join essaycards.review_events e on e.flashcard_id = sf.id
                join first_ever fe on fe.flashcard_id = e.flashcard_id
                cross join today t
                where (e.reviewed_at at time zone 'utc') >= t.start_utc
                  and (e.reviewed_at at time zone 'utc') < t.start_utc + interval '1 day'
                """,
                params,
            )
            row = dict(cur.fetchone())

    rows = [{
        "recalls": int(row["recalls"] or 0),
        "unique_cards_seen": int(row["unique_cards_seen"] or 0),
        "first_cards_seen": int(row["first_cards_seen"] or 0),
    }]
    dataset = Dataset(
        meta=DatasetMeta(
            object_type="review_today", label="Today", total=1, page=1, page_size=1, row_actions=[],
        ),
        **{"schema": TODAY_SCHEMA},
        rows=rows,
    )
    return _dataset_response(dataset)


# ── GET /review-stats/intervals (Sprint12_FSRSAndUXOverhaul) ────────────────

INTERVALS_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="bucket", label="Bucket",  type="string", sortable=False, filterable=False),
    ColumnSchema(key="label",  label="Horizon", type="string", sortable=False, filterable=False),
    ColumnSchema(key="count",  label="Cards",   type="number", sortable=False, filterable=False),
]

# Fixed near -> far bucket order, same closed-set discipline as
# backend/routers/flashcards.py::STATS_BUCKETS. "new" = never reviewed
# (review_interval = 0, the same sentinel used throughout this app). Open on
# the lower edge, closed on the upper edge.
INTERVAL_BUCKETS: list[tuple[str, str]] = [
    ("new",            "New"),
    ("within_1_day",   "< 1 day"),
    ("within_7_days",  "1-7 days"),
    ("within_30_days", "7-30 days"),
    ("within_90_days", "30-90 days"),
    ("beyond_90_days", "90+ days"),
]


def _interval_bucket_rows(cur: Any) -> list[dict[str, Any]]:
    """One SQL statement, same FILTER-based zero-fill idiom as
    backend/routers/flashcards.py::flashcard_queue_stats, over
    flashcard_review_state.review_interval (a stored write-time cache, not
    independently time-filtered — R-CON-AL-06)."""
    cur.execute(
        """
        select
          count(*) filter (where review_interval = interval '0')                                   as new,
          count(*) filter (where review_interval > interval '0'
                              and review_interval <= interval '1 day')                              as within_1_day,
          count(*) filter (where review_interval >  interval '1 day'
                              and review_interval <= interval '7 days')                              as within_7_days,
          count(*) filter (where review_interval >  interval '7 days'
                              and review_interval <= interval '30 days')                             as within_30_days,
          count(*) filter (where review_interval >  interval '30 days'
                              and review_interval <= interval '90 days')                             as within_90_days,
          count(*) filter (where review_interval >  interval '90 days')                              as beyond_90_days
        from essaycards.flashcard_review_state
        """
    )
    counts = cur.fetchone()
    return [{"bucket": key, "label": label, "count": int(counts[key])} for key, label in INTERVAL_BUCKETS]


@router.get("/intervals", response_model=None)
def get_review_intervals() -> JSONResponse:
    """
    Current scheduled-interval distribution across every card with a
    review-state row. No parameters. Always exactly six rows, zero-filled;
    the six counts sum to the total scheduled card count.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            rows = _interval_bucket_rows(cur)

    dataset = Dataset(
        meta=DatasetMeta(
            object_type="review_interval_bucket",
            label="Scheduled Interval Distribution",
            total=len(rows),
            page=1,
            page_size=len(rows),
            row_actions=[],
        ),
        **{"schema": INTERVALS_SCHEMA},
        rows=rows,
    )
    return _dataset_response(dataset)
