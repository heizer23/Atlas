"""
Daily review endpoints: GET and PUT /reviews/{date}. Thin HTTP wrappers
around backend/review_logic.py — no merge/expected-set logic duplicated
here.

Route -> internal_flow step mapping (10_architecture.json):
  GET /reviews/{date} -> step 7  get_review_view
  PUT /reviews/{date} -> step 8/9 compute_expected_habit_ids + upsert_review
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend import review_logic
from backend.database import get_db
from platform_errorhandling import api_error
from platform_contracts import ColumnSchema, Dataset, DatasetMeta

router = APIRouter(prefix="/habittracker", tags=["habittracker"])

# habits is a nested array (one entry per habit), rendered by this app's own
# bespoke DailyReviewView, not a generic platform table — same convention as
# StoryReader's VERSION_CONTENT_SCHEMA.paragraphs.
REVIEW_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="review_date",  label="Date",         type="date"),
    ColumnSchema(key="status",       label="Status",       type="enum"),
    ColumnSchema(key="confirmed_at", label="Confirmed At", type="date"),
    ColumnSchema(key="habits",       label="Habits",       type="string"),
]

# ── Request models ───────────────────────────────────────────────────────────
# Both fields are Optional with no default so a missing status/habit_results
# surfaces as our own VALIDATION_ERROR below rather than FastAPI's default
# 422 shape (R-CON-BP-04 — every error body must be ApiError-shaped).


class HabitResultIn(BaseModel):
    habit_id: str
    checked:  bool


class ReviewPutBody(BaseModel):
    status:        str | None = None
    habit_results: list[HabitResultIn] | None = None

# ── Helpers ───────────────────────────────────────────────────────────────────


def _parse_date_param(date_str: str) -> date | None:
    """Parse a YYYY-MM-DD path segment. Shared by both endpoints in this
    file only — reports.py keeps its own file-local duplicate (R-CON-BP-10),
    it does not import this one.
    """
    try:
        return date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return None


def _dataset_response(dataset: Dataset, status: int = 200) -> JSONResponse:
    return JSONResponse(status_code=status, content=dataset.model_dump(by_alias=True, mode="json"))


def _review_dataset(row: dict) -> Dataset:
    return Dataset(
        meta=DatasetMeta(object_type="daily_review", label="Daily Review", total=1, page=1, page_size=1, row_actions=[]),
        **{"schema": REVIEW_SCHEMA},
        rows=[row],
    )

# ── GET /reviews/{date} ───────────────────────────────────────────────────────


@router.get("/reviews/{date}", response_model=None)
def get_review(date: str) -> JSONResponse:
    target_date = _parse_date_param(date)
    if target_date is None:
        return api_error("VALIDATION_ERROR", "date must be a valid YYYY-MM-DD date", status=400)

    with get_db() as conn:
        with conn.cursor() as cur:
            view = review_logic.get_review_view(cur, target_date)

    return _dataset_response(_review_dataset(view))

# ── PUT /reviews/{date} ───────────────────────────────────────────────────────


@router.put("/reviews/{date}", response_model=None)
def put_review(date: str, body: ReviewPutBody) -> JSONResponse:
    target_date = _parse_date_param(date)
    if target_date is None:
        return api_error("VALIDATION_ERROR", "date must be a valid YYYY-MM-DD date", status=400)

    if body.status not in ("draft", "confirmed"):
        return api_error("VALIDATION_ERROR", "status must be 'draft' or 'confirmed'", status=400)

    if body.habit_results is None:
        return api_error("VALIDATION_ERROR", "habit_results is required", status=400)

    submitted_ids = [hr.habit_id for hr in body.habit_results]

    with get_db() as conn:
        with conn.cursor() as cur:
            expected = review_logic.compute_expected_habit_ids(cur, target_date)

        if len(submitted_ids) != len(set(submitted_ids)) or set(submitted_ids) != expected:
            return api_error(
                "VALIDATION_ERROR",
                "habit_results must cover exactly the expected habit set for this date, with no duplicates",
                status=400,
            )

        habit_results = [{"habit_id": hr.habit_id, "checked": hr.checked} for hr in body.habit_results]
        view = review_logic.upsert_review(conn, target_date, body.status, habit_results)

    return _dataset_response(_review_dataset(view))
