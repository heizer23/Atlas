"""
GET /review-stats/summary — the review-performance stats page's sole data
endpoint (Sprint11_ReviewStats).

Reports on the reviewer's actual completed review history over three fixed,
independent rolling windows off Postgres now() — day (24 hours), week (7
days), month (30 days), in that order. Always exactly three rows, never
omitted, even when a window has zero reviews.

Deliberately scheduler-agnostic: aggregates across both Classic and FSRS
(unlike backend/routers/experiment.py, which compares the two schedulers
against each other). Deliberately applies no prior_review_interval filter —
unlike GET /experiment/summary's ordinary_due_reviews filter — because this
page answers "how did I do", counting every completed review including
relearning/rapid retries, not isolated evidence of long-term retention.

recall_rate is null (not 0) when a window has zero reviews — "no data yet"
and "0% recall" are different facts, mirroring experiment.py's identical
convention. failures is always exactly equal to again_count, named
separately only because recall_rate is derived from it and the two must
always be read together.
"""

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.database import get_db
from platform_contracts import ColumnSchema, Dataset, DatasetMeta

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
]

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
            f"count(*) filter (where reviewed_at >= now() - interval '{interval_literal}') "
            f"as {period}_reviews"
        )
        select_parts.append(
            f"count(distinct flashcard_id) filter (where reviewed_at >= now() - interval '{interval_literal}') "
            f"as {period}_unique_cards"
        )
        for grade in _GRADES:
            select_parts.append(
                f"count(*) filter (where reviewed_at >= now() - interval '{interval_literal}' "
                f"and grade = '{grade}') as {period}_{grade}_count"
            )

    query = (
        "select " + ", ".join(select_parts) + " "
        "from essaycards.review_events "
        "where reviewed_at >= now() - interval '30 days'"
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
