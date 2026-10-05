"""
GET /reports — the grid + per-habit stats + period-level confirmed-vs-elapsed
endpoint.

Mechanism for attaching the additive period_summary sibling field
(10_architecture.json internal_flow step 11): this route is declared
response_model=None; it parses the required anchor_date query param (str)
into anchor_date_parsed: date via a file-local _parse_date_param helper
(VALIDATION_ERROR if unparseable) — a same-named duplicate of reviews.py's
private _parse_date_param, since that function is explicitly scoped
file-local to reviews.py (R-CON-BP-10) and must not be imported cross-file —
the original anchor_date string is kept unchanged for use in period_summary.
It builds the Dataset as usual, converts period_start/period_end (raw
datetime.date objects from review_logic.resolve_report_period) to
YYYY-MM-DD strings via .isoformat() before merging them into the response
dict — required because they are merged in AFTER dataset.model_dump() runs
and so never pass through pydantic's JSON serializer, and Starlette's
JSONResponse.render() uses stdlib json.dumps() with no custom encoder, which
raises TypeError on a raw date (R-CON-AL-03). Follows the same
response_model=None + model_dump() + JSONResponse bypass pattern as
EssayCards' backend/routers/review_stats.py::_dataset_response() helper;
that helper never merges a sibling key into the dict and never needed
date-formatting (its dates are pre-stringified via SQL to_char()) — the
sibling-field merge and date-conversion are this design's own addition.
period_summary is never passed as a Dataset(...) constructor kwarg (pydantic's
default extra="ignore" would silently drop it).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend import review_logic
from backend.database import get_db
from platform_errorhandling import api_error
from platform_contracts import ColumnSchema, Dataset, DatasetMeta

router = APIRouter(prefix="/habittracker", tags=["habittracker"])

# cells is a nested array (one entry per date in the period), rendered by
# this app's own bespoke ReportsView — same convention as REVIEW_SCHEMA.habits.
REPORTS_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="habit_id",                label="Habit",                   type="string"),
    ColumnSchema(key="name",                    label="Name",                    type="string"),
    ColumnSchema(key="description",              label="Description",             type="string"),
    ColumnSchema(key="display_order",            label="Order",                   type="number"),
    ColumnSchema(key="cells",                    label="Cells",                   type="string"),
    ColumnSchema(key="eligible_confirmed_days",  label="Eligible Confirmed Days", type="number"),
    ColumnSchema(key="completed_count",          label="Completed",               type="number"),
    ColumnSchema(key="rate",                     label="Rate",                    type="number"),
]

# ── Helpers ───────────────────────────────────────────────────────────────────


def _parse_date_param(date_str: str) -> date | None:
    """A same-named, file-local duplicate of reviews.py's private
    _parse_date_param — that function is explicitly scoped file-local to
    reviews.py and must not be imported cross-file into this module
    (R-CON-BP-10)."""
    try:
        return date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return None


def _cell_state(
    habit: dict,
    target_date: date,
    review_status_by_date: dict,
    checked_by_date_habit: dict,
) -> str:
    """Pure function implementing the four-way cell-state rule
    (10_architecture.json contracts.invariants). The presence of a saved
    row (confirmed OR draft) is what decides not_active vs. the other three
    — a habit's current window only matters when no row exists at all for
    that date.
    """
    habit_id = str(habit["id"])
    key = (target_date, habit_id)

    if key in checked_by_date_habit:
        status = review_status_by_date.get(target_date)
        if status == "confirmed":
            return "completed" if checked_by_date_habit[key] else "not_completed"
        return "unreviewed"

    active_from = habit["active_from"]
    end_date = habit["end_date"]
    if target_date < active_from or (end_date is not None and target_date > end_date):
        return "not_active"
    return "unreviewed"

# ── GET /reports ──────────────────────────────────────────────────────────────


@router.get("/reports", response_model=None)
def get_reports(period: str, anchor_date: str) -> JSONResponse:
    if period not in ("week", "month"):
        return api_error("VALIDATION_ERROR", "period must be 'week' or 'month'", status=400)

    anchor_date_parsed = _parse_date_param(anchor_date)
    if anchor_date_parsed is None:
        return api_error("VALIDATION_ERROR", "anchor_date must be a valid YYYY-MM-DD date", status=400)

    period_start, period_end, dates = review_logic.resolve_report_period(period, anchor_date_parsed)
    date_objs = [date.fromisoformat(d) for d in dates]

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select * from habittracker.habits
                where active_from <= %s and (end_date is null or end_date >= %s)
                order by display_order asc
                """,
                (period_end, period_start),
            )
            habit_rows = [dict(r) for r in cur.fetchall()]

            cur.execute(
                """
                select review_date, status from habittracker.daily_reviews
                where review_date between %s and %s
                """,
                (period_start, period_end),
            )
            review_status_by_date = {r["review_date"]: r["status"] for r in cur.fetchall()}

            checked_by_date_habit: dict[Any, bool] = {}
            habit_ids = [h["id"] for h in habit_rows]
            if habit_ids:
                cur.execute(
                    """
                    select review_date, habit_id, checked from habittracker.habit_results
                    where review_date between %s and %s and habit_id = any(%s::uuid[])
                    """,
                    (period_start, period_end, habit_ids),
                )
                for r in cur.fetchall():
                    checked_by_date_habit[(r["review_date"], str(r["habit_id"]))] = r["checked"]

    today_berlin = review_logic.berlin_today()
    elapsed_threshold = min(period_end, today_berlin)
    elapsed_days = (elapsed_threshold - period_start).days + 1 if elapsed_threshold >= period_start else 0

    rows = []
    for h in habit_rows:
        habit_id = str(h["id"])
        cells = []
        eligible = 0
        completed = 0
        for d in date_objs:
            state = _cell_state(h, d, review_status_by_date, checked_by_date_habit)
            cells.append({"date": d.isoformat(), "state": state})
            if state in ("completed", "not_completed"):
                eligible += 1
                if state == "completed":
                    completed += 1
        rate = (completed / eligible) if eligible > 0 else None
        rows.append({
            "id": habit_id,
            "habit_id": habit_id,
            "name": h["name"],
            "description": h["description"],
            "display_order": h["display_order"],
            "cells": cells,
            "eligible_confirmed_days": eligible,
            "completed_count": completed,
            "rate": rate,
        })

    confirmed_days = sum(1 for status in review_status_by_date.values() if status == "confirmed")

    dataset = Dataset(
        meta=DatasetMeta(
            object_type="habit_report_row",
            label="Habit Report",
            total=len(rows),
            page=1,
            page_size=max(len(rows), 1),
            row_actions=[],
        ),
        **{"schema": REPORTS_SCHEMA},
        rows=rows,
    )

    content = dataset.model_dump(by_alias=True, mode="json")
    content["period_summary"] = {
        "period": period,
        "anchor_date": anchor_date,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "dates": dates,
        "confirmed_days": confirmed_days,
        "elapsed_days": elapsed_days,
    }
    return JSONResponse(content=content)
