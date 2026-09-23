"""
GET /experiment/summary — the experiment dashboard's sole data endpoint
(Sprint10_DualSchedulerAB).

Returns REAL RECORDED per-scheduler counts, never theoretical scheduler
predictions (mission §7). Always exactly two rows, 'classic' then 'fsrs', in
that fixed order — computed by coalescing a fixed ('classic', 'fsrs') row
list against whatever the two aggregate queries below return, so a scheduler
with zero assigned cards or zero due reviews still appears with every count
column zero-filled.

recall_rate and its sample size (ordinary_due_reviews) are always exposed
together, never recall_rate alone — a 0% recall rate and "no data yet" (null)
are different facts and must not be conflated. ordinary_due_reviews/
recall_rate/failures are filtered on essaycards.review_events.prior_review_interval
>= interval '24 hours' — NOT was_due, which is true for virtually every
reachable review (GET /flashcards/due's base eligibility already requires
next_due_at <= now() for every session type) and therefore cannot by itself
separate ordinary due-review evidence from immediate-relearning/rapid-retry
reviews. The prior_review_interval >= 24h filter mirrors the app's existing
learning/established threshold (CLAUDE.md) and correctly excludes rapid
retries, which always follow a short (learning-phase) prior interval. See
10_architecture.json §contracts.invariants and 12_design_corrections.md.
"""

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.database import get_db
from platform_contracts import ColumnSchema, Dataset, DatasetMeta

router = APIRouter(prefix="/experiment", tags=["experiment"])

EXPERIMENT_SUMMARY_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="scheduler", label="Scheduler", type="string", sortable=False, filterable=False),
    ColumnSchema(key="assigned_cards", label="Assigned cards", type="number", sortable=False, filterable=False),
    ColumnSchema(key="new_cards_assigned", label="New cards assigned", type="number", sortable=False, filterable=False),
    ColumnSchema(key="migrated_cards_assigned", label="Migrated cards assigned", type="number", sortable=False, filterable=False),
    ColumnSchema(key="cards_new", label="New", type="number", sortable=False, filterable=False),
    ColumnSchema(key="cards_learning", label="Learning", type="number", sortable=False, filterable=False),
    ColumnSchema(key="cards_established", label="Established", type="number", sortable=False, filterable=False),
    ColumnSchema(key="reviewed_cards", label="Reviewed cards", type="number", sortable=False, filterable=False),
    ColumnSchema(key="completed_reviews", label="Completed reviews", type="number", sortable=False, filterable=False),
    ColumnSchema(key="ordinary_due_reviews", label="Ordinary due reviews", type="number", sortable=False, filterable=False),
    ColumnSchema(key="recall_rate", label="Recall rate", type="number", sortable=False, filterable=False),
    ColumnSchema(key="failures", label="Failures", type="number", sortable=False, filterable=False),
]

_SCHEDULERS: tuple[str, ...] = ("classic", "fsrs")


def _assignment_counts_by_scheduler(cur: Any) -> dict[str, dict[str, int]]:
    """GROUP BY scheduler over flashcard_review_state. new_cards_assigned
    covers cards assigned at creation time (reasons 'new_card_random' or
    'assignment_disabled_classic'); migrated_cards_assigned covers cards
    assigned by the one-time migration backfill ('migrated_never_reviewed_random'
    or 'legacy_retained_classic'). cards_new/learning/established mirror the
    app's existing review_interval thresholds (CLAUDE.md)."""
    cur.execute(
        """
        select
            scheduler,
            count(*) as assigned_cards,
            count(*) filter (
                where scheduler_assignment_reason in ('new_card_random', 'assignment_disabled_classic')
            ) as new_cards_assigned,
            count(*) filter (
                where scheduler_assignment_reason in ('migrated_never_reviewed_random', 'legacy_retained_classic')
            ) as migrated_cards_assigned,
            count(*) filter (where last_reviewed_at is null) as cards_new,
            count(*) filter (
                where last_reviewed_at is not null and review_interval < interval '24 hours'
            ) as cards_learning,
            count(*) filter (where review_interval >= interval '24 hours') as cards_established
        from essaycards.flashcard_review_state
        group by scheduler
        """
    )
    return {row["scheduler"]: dict(row) for row in cur.fetchall()}


def _review_counts_by_scheduler(cur: Any) -> dict[str, dict[str, int]]:
    """GROUP BY scheduler over review_events. ordinary_due_reviews/failures
    are filtered on prior_review_interval >= interval '24 hours' (NOT
    was_due — see module docstring)."""
    cur.execute(
        """
        select
            scheduler,
            count(distinct flashcard_id) as reviewed_cards,
            count(*) as completed_reviews,
            count(*) filter (where prior_review_interval >= interval '24 hours') as ordinary_due_reviews,
            count(*) filter (
                where prior_review_interval >= interval '24 hours' and grade = 'again'
            ) as failures
        from essaycards.review_events
        group by scheduler
        """
    )
    return {row["scheduler"]: dict(row) for row in cur.fetchall()}


def _dataset_response(dataset: Dataset) -> JSONResponse:
    return JSONResponse(content=dataset.model_dump(by_alias=True, mode="json"))


@router.get("/summary", response_model=None)
def get_experiment_summary() -> JSONResponse:
    """
    Experiment comparison dashboard data source. Always exactly two rows,
    'classic' then 'fsrs', in that fixed order. No parameters. Server time
    only (R-CON-AL-06) — every count is read live at request time.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            assignment = _assignment_counts_by_scheduler(cur)
            reviews = _review_counts_by_scheduler(cur)

    rows: list[dict[str, Any]] = []
    for scheduler in _SCHEDULERS:
        a = assignment.get(scheduler, {})
        r = reviews.get(scheduler, {})
        ordinary_due_reviews = int(r.get("ordinary_due_reviews") or 0)
        failures = int(r.get("failures") or 0)
        recall_rate = (
            (ordinary_due_reviews - failures) / ordinary_due_reviews
            if ordinary_due_reviews > 0
            else None
        )
        rows.append({
            "scheduler": scheduler,
            "assigned_cards": int(a.get("assigned_cards") or 0),
            "new_cards_assigned": int(a.get("new_cards_assigned") or 0),
            "migrated_cards_assigned": int(a.get("migrated_cards_assigned") or 0),
            "cards_new": int(a.get("cards_new") or 0),
            "cards_learning": int(a.get("cards_learning") or 0),
            "cards_established": int(a.get("cards_established") or 0),
            "reviewed_cards": int(r.get("reviewed_cards") or 0),
            "completed_reviews": int(r.get("completed_reviews") or 0),
            "ordinary_due_reviews": ordinary_due_reviews,
            "recall_rate": recall_rate,
            "failures": failures,
        })

    dataset = Dataset(
        meta=DatasetMeta(
            object_type="experiment_summary",
            label="Scheduler Experiment Summary",
            total=len(rows),
            page=1,
            page_size=len(rows),
            row_actions=[],
        ),
        **{"schema": EXPERIMENT_SUMMARY_SCHEMA},
        rows=rows,
    )
    return _dataset_response(dataset)
