"""
Calendar — HTTP router for /api/cal/events CRUD endpoints.

Endpoints:
  GET    /api/cal/events               List events (optional start/end filter)
  POST   /api/cal/events               Create a new event
  PATCH  /api/cal/events/{event_id}    Partially update an event
  DELETE /api/cal/events/{event_id}    Delete an event
"""
from datetime import datetime
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.database import get_db
from backend.models import (
    UNSET,
    CalendarEventCreate,
    CalendarEventPatch,
    VALID_EVENT_TYPES,
    VALID_SOURCE_TYPES,
)
from platform_contracts import ColumnSchema, Dataset, DatasetMeta
from platform_errorhandling import api_error

router = APIRouter(prefix="/api/cal", tags=["calendar"])

# ── Schema definition for Dataset responses ───────────────────────────────────

EVENT_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="id",                 label="ID",          type="string",  sortable=False, detail_visible=False),
    ColumnSchema(key="title",              label="Title",       type="string",  sortable=True),
    ColumnSchema(key="start_at",           label="Start",       type="date",    sortable=True),
    ColumnSchema(key="end_at",             label="End",         type="date",    sortable=True),
    ColumnSchema(key="event_type",         label="Type",        type="enum",    sortable=True,  filterable=True),
    ColumnSchema(key="source_object_type", label="Source Type", type="string",  sortable=False),
    ColumnSchema(key="source_object_id",   label="Source ID",   type="string",  sortable=False),
    ColumnSchema(key="notes",              label="Notes",       type="string",  sortable=False),
    ColumnSchema(key="created_at",         label="Created",     type="date",    sortable=True,  detail_visible=False),
    ColumnSchema(key="updated_at",         label="Updated",     type="date",    sortable=True,  detail_visible=False),
]


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Convert a psycopg2 RealDictRow to a plain dict with serializable types."""
    d = dict(row)
    d["id"] = str(d["id"])
    for field in ("start_at", "end_at", "created_at", "updated_at"):
        if d.get(field) is not None:
            d[field] = d[field].isoformat()
    return d


def _to_dataset(rows: list[dict]) -> Dataset:
    return Dataset(
        **{
            "meta": DatasetMeta(
                object_type="calendar_event",
                label="Calendar Events",
                total=len(rows),
                page=1,
                page_size=len(rows) if rows else 25,
                row_actions=["edit", "delete"],
            ),
            "schema": EVENT_SCHEMA,
            "rows": rows,
        }
    )


def _empty_dataset() -> Dataset:
    return Dataset(
        **{
            "meta": DatasetMeta(
                object_type="calendar_event",
                label="Calendar Events",
                total=0,
                page=1,
                page_size=25,
                row_actions=[],
            ),
            "schema": EVENT_SCHEMA,
            "rows": [],
        }
    )


def _validate_times(start_at: str, end_at: str) -> str | None:
    """Return error message if start_at >= end_at, else None."""
    try:
        start = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_at.replace("Z", "+00:00"))
    except ValueError:
        return "start_at and end_at must be valid ISO-8601 datetimes"
    if start >= end:
        return "start_at must be before end_at"
    return None


def _validate_source(source_type: str | None, source_id: str | None) -> str | None:
    """Return error message if source fields are inconsistent, else None."""
    if source_type is not None and source_id is None:
        return "source_object_id is required when source_object_type is provided"
    if source_id is not None and source_type is None:
        return "source_object_type is required when source_object_id is provided"
    if source_type is not None and source_type not in VALID_SOURCE_TYPES:
        return f"source_object_type must be one of: {VALID_SOURCE_TYPES}"
    return None


# ── GET /api/cal/events ───────────────────────────────────────────────────────

@router.get("/events")
def list_events(start: str | None = None, end: str | None = None):
    """
    List CalendarEvents ordered by start_at ASC.

    Optional query params:
      start: ISO-8601 datetime, inclusive lower bound (start_at >= start)
      end:   ISO-8601 datetime, exclusive upper bound (start_at < end)

    Returns Dataset. Empty Dataset when no events match.
    """
    sql = "SELECT * FROM calendar_events"
    params: list[Any] = []
    conditions: list[str] = []

    if start is not None:
        conditions.append(f"start_at >= %s")
        params.append(start)
    if end is not None:
        conditions.append(f"start_at < %s")
        params.append(end)

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY start_at ASC"

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = [_row_to_dict(r) for r in cur.fetchall()]

    return _to_dataset(rows)


# ── POST /api/cal/events ──────────────────────────────────────────────────────

@router.post("/events")
def create_event(body: CalendarEventCreate):
    """
    Create a CalendarEvent. Returns Dataset (single row) on success.
    Returns 422 ApiError if start_at >= end_at or source fields are inconsistent.
    """
    # Validate event_type
    if body.event_type not in VALID_EVENT_TYPES:
        return api_error(
            "CALENDAR_VALIDATION_ERROR",
            f"event_type must be one of: {VALID_EVENT_TYPES}",
            status=422,
        )

    # Validate time constraint
    if err := _validate_times(body.start_at, body.end_at):
        return api_error("CALENDAR_VALIDATION_ERROR", err, status=422)

    # Validate source consistency
    if err := _validate_source(body.source_object_type, body.source_object_id):
        return api_error("CALENDAR_VALIDATION_ERROR", err, status=422)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO calendar_events
                  (title, start_at, end_at, event_type,
                   source_object_type, source_object_id, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    body.title,
                    body.start_at,
                    body.end_at,
                    body.event_type,
                    body.source_object_type,
                    body.source_object_id,
                    body.notes,
                ),
            )
            row = _row_to_dict(cur.fetchone())
        conn.commit()

    return _to_dataset([row])


# ── PATCH /api/cal/events/{event_id} ─────────────────────────────────────────

@router.patch("/events/{event_id}")
def patch_event(event_id: str, body: CalendarEventPatch):
    """
    Partially update a CalendarEvent.
    Omitted fields are unchanged. Explicit null clears nullable fields.
    Returns Dataset (single row) on success, 404 ApiError if not found.
    """
    # Collect only provided (non-UNSET) fields
    updates: dict[str, Any] = {}
    raw = body.model_dump()

    # We re-check using the sentinel since model_dump converts UNSET to None
    # (they're the same object under the hood). Use __dict__ instead.
    for field in ("title", "start_at", "end_at", "event_type",
                  "source_object_type", "source_object_id", "notes"):
        val = body.__dict__.get(field, UNSET)
        if val is not UNSET:
            updates[field] = val

    if not updates:
        # Nothing to update — fetch and return current state
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM calendar_events WHERE id = %s", (event_id,))
                existing = cur.fetchone()
        if existing is None:
            return api_error("CALENDAR_EVENT_NOT_FOUND", f"Event {event_id} not found", status=404)
        return _to_dataset([_row_to_dict(existing)])

    # Validate times if both or either are being updated
    new_start = updates.get("start_at", UNSET)
    new_end = updates.get("end_at", UNSET)

    if new_start is not UNSET and new_end is not UNSET:
        if err := _validate_times(new_start, new_end):
            return api_error("CALENDAR_VALIDATION_ERROR", err, status=422)
    elif new_start is not UNSET or new_end is not UNSET:
        # Only one side provided — need to fetch the other for validation
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT start_at, end_at FROM calendar_events WHERE id = %s", (event_id,))
                existing_times = cur.fetchone()
        if existing_times is None:
            return api_error("CALENDAR_EVENT_NOT_FOUND", f"Event {event_id} not found", status=404)
        check_start = new_start if new_start is not UNSET else existing_times["start_at"].isoformat()
        check_end = new_end if new_end is not UNSET else existing_times["end_at"].isoformat()
        if err := _validate_times(check_start, check_end):
            return api_error("CALENDAR_VALIDATION_ERROR", err, status=422)

    # Validate source consistency for fields being updated
    src_type = updates.get("source_object_type", UNSET)
    src_id = updates.get("source_object_id", UNSET)
    if src_type is not UNSET or src_id is not UNSET:
        # Both present in update — validate together
        check_type = src_type if src_type is not UNSET else None
        check_id = src_id if src_id is not UNSET else None
        if src_type is not UNSET and src_id is not UNSET:
            if err := _validate_source(check_type, check_id):
                return api_error("CALENDAR_VALIDATION_ERROR", err, status=422)

    # Validate event_type if being updated
    if "event_type" in updates and updates["event_type"] not in VALID_EVENT_TYPES:
        return api_error(
            "CALENDAR_VALIDATION_ERROR",
            f"event_type must be one of: {VALID_EVENT_TYPES}",
            status=422,
        )

    # Build SET clause dynamically
    set_parts = [f"{col} = %s" for col in updates.keys()]
    set_parts.append("updated_at = now()")
    set_clause = ", ".join(set_parts)
    values = list(updates.values()) + [event_id]

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE calendar_events SET {set_clause} WHERE id = %s RETURNING *",
                values,
            )
            updated = cur.fetchone()
        if updated is None:
            conn.rollback()
            return api_error("CALENDAR_EVENT_NOT_FOUND", f"Event {event_id} not found", status=404)
        conn.commit()

    return _to_dataset([_row_to_dict(updated)])


# ── DELETE /api/cal/events/{event_id} ────────────────────────────────────────

@router.delete("/events/{event_id}")
def delete_event(event_id: str):
    """
    Delete a CalendarEvent. Returns empty Dataset on success.
    Returns 404 ApiError if not found.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM calendar_events WHERE id = %s RETURNING id",
                (event_id,),
            )
            deleted = cur.fetchone()
        if deleted is None:
            conn.rollback()
            return api_error("CALENDAR_EVENT_NOT_FOUND", f"Event {event_id} not found", status=404)
        conn.commit()

    return _empty_dataset()
