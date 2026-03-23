"""
backend/routers/calendar.py

Chronicle — Calendar endpoints.

Endpoints:
  GET  /api/chronicle/calendar/sources
    Returns distinct (application, source_label, selected) from
    shared_views.calendar_event_view.

  GET  /api/chronicle/calendar/events
    Returns rows from shared_views.calendar_event_view for a given
    (application, source_label) pair, filtered by year.
    Query params: application (str), source_label (str), year (int, default=current year).

  PATCH /api/chronicle/calendar/sources
    Upserts selection state in shared_views.calendar_source_selection.
    Body: { application, source_label, selected }

No Dataset used — CalendarEventView endpoints use the CalendarEventViewRow
named contract declared in 20_design/architecture.json. This is a controlled
exception to the Atlas UI Data Contract (heatmap does not fit paginated Dataset
semantics).
"""

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.database import get_db

router = APIRouter(prefix="/chronicle", tags=["calendar"])


# ── Request / Response models ─────────────────────────────────────────────────

class SelectionToggleRequest(BaseModel):
    application:  str
    source_label: str
    selected:     bool


# ── Error helper ──────────────────────────────────────────────────────────────

def _api_error(code: str, message: str, detail: Any = None) -> dict:
    return {
        "error": {
            "code":       code,
            "message":    message,
            "detail":     detail,
            "request_id": uuid.uuid4().hex[:8],
        }
    }


# ── GET /calendar/sources ─────────────────────────────────────────────────────

@router.get("/calendar/sources", response_model=None)
def get_sources() -> JSONResponse:
    """
    Returns distinct (application, source_label, selected) rows from
    shared_views.calendar_event_view.

    The selected value for a (application, source_label) pair is the same
    across all rows — the view joins calendar_source_selection globally.
    We use MAX(selected::int)::bool as the canonical selected state per pair.
    """
    sql = """
        SELECT
            application,
            source_label,
            bool_or(selected) AS selected
        FROM shared_views.calendar_event_view
        GROUP BY application, source_label
        ORDER BY application, source_label
    """
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content=_api_error("DB_ERROR", "Failed to fetch sources.", str(exc)),
        )

    result = [
        {
            "application":  row["application"],
            "source_label": row["source_label"],
            "selected":     bool(row["selected"]),
        }
        for row in rows
    ]
    return JSONResponse(content=result)


# ── GET /calendar/events ──────────────────────────────────────────────────────

@router.get("/calendar/events", response_model=None)
def get_events(
    application:  str = Query(...),
    source_label: str = Query(...),
    year:         int = Query(default=None),
) -> JSONResponse:
    """
    Returns rows from shared_views.calendar_event_view for the given
    (application, source_label), filtered to the requested calendar year.

    year defaults to the current server year if not supplied.

    Missing days are NOT included — the frontend renders them as 0.
    """
    if year is None:
        year = date.today().year

    if year < 2000 or year > 2100:
        return JSONResponse(
            status_code=422,
            content=_api_error(
                "INVALID_PARAM",
                f"year must be between 2000 and 2100, got {year}",
                {"field": "year", "received": year},
            ),
        )

    sql = """
        SELECT
            date,
            application,
            source_label,
            label,
            value,
            selected,
            detail,
            deep_link
        FROM shared_views.calendar_event_view
        WHERE application  = %s
          AND source_label = %s
          AND date >= %s::date
          AND date <  %s::date
        ORDER BY date
    """
    year_start = f"{year}-01-01"
    year_end   = f"{year + 1}-01-01"

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (application, source_label, year_start, year_end))
                rows = cur.fetchall()
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content=_api_error("DB_ERROR", "Failed to fetch events.", str(exc)),
        )

    result = [
        {
            "date":         str(row["date"]),
            "application":  row["application"],
            "source_label": row["source_label"],
            "label":        row["label"],
            "value":        int(row["value"]),
            "selected":     bool(row["selected"]),
            "detail":       row["detail"],
            "deep_link":    row["deep_link"],
        }
        for row in rows
    ]
    return JSONResponse(content=result)


# ── PATCH /calendar/sources ───────────────────────────────────────────────────

@router.patch("/calendar/sources", response_model=None)
def patch_source(body: SelectionToggleRequest) -> JSONResponse:
    """
    Upserts selection state in shared_views.calendar_source_selection.

    Uses INSERT ... ON CONFLICT DO UPDATE to ensure idempotency.
    Returns the updated (application, source_label, selected) record.
    """
    sql = """
        INSERT INTO shared_views.calendar_source_selection
            (application, source_label, selected)
        VALUES (%s, %s, %s)
        ON CONFLICT (application, source_label)
        DO UPDATE SET selected = EXCLUDED.selected
        RETURNING application, source_label, selected
    """
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (body.application, body.source_label, body.selected))
                row = cur.fetchone()
            conn.commit()
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content=_api_error("DB_ERROR", "Failed to update selection.", str(exc)),
        )

    return JSONResponse(content={
        "application":  row["application"],
        "source_label": row["source_label"],
        "selected":     bool(row["selected"]),
    })
