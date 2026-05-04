"""
TaskTracker MCP tools.

Plain functions — no FastMCP dependency.
Registered into 02_Platform/MCPGateway at startup.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import psycopg
from psycopg.rows import dict_row


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CALENDAR_CONNECTOR_URL = os.environ.get("CALENDAR_CONNECTOR_URL", "http://localhost:8021")
ATLAS_BASE_URL         = os.environ.get("ATLAS_BASE_URL",         "https://workout.linspad.net")

DEFAULT_DURATION_MINUTES = 60  # used when effort_hours is null


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _pg():
    """Open a Postgres connection using Atlas platform env vars."""
    return psycopg.connect(
        host="127.0.0.1",
        port=int(os.environ.get("ATLAS_PG_PORT", 5432)),
        dbname=os.environ["ATLAS_PG_DB"],
        user=os.environ["ATLAS_PG_USER"],
        password=os.environ["ATLAS_PG_PASSWORD"],
        row_factory=dict_row,
    )


def _to_json(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if v is None or isinstance(v, (int, float, str, bool)):
            out[k] = v
        else:
            out[k] = str(v)
    return out


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def schedule_task(
    task_id: str,
    start_at: str,
    duration_minutes: Optional[int] = None,
) -> dict:
    """
    Schedule an Atlas task by creating a Google Calendar blocker and setting
    the task status to 'scheduled'.

    Parameters
    ----------
    task_id : str
        UUID of the task to schedule.
    start_at : str
        ISO-8601 datetime for when the work starts, e.g. "2026-05-06T09:00:00".
        Assumed local time if no timezone offset is provided.
    duration_minutes : int, optional
        How long the work block should be in minutes.
        If omitted, the task's effort_hours is used (converted to minutes).
        If effort_hours is also null, defaults to 60 minutes.
        Provide an explicit value to override the effort estimate.

    Returns
    -------
    dict with keys:
        task_id, title, scheduled_date, start_at, end_at, duration_minutes,
        calendar_status ("created" | "existing" | "skipped"), message
    """
    # ── 1. Fetch the task ────────────────────────────────────────────────────
    with _pg() as con, con.cursor() as cur:
        cur.execute(
            "SELECT id::text, title, description, status, effort_hours, scheduled_at "
            "FROM tasktracker.tasks WHERE id = %s",
            (task_id,),
        )
        task = cur.fetchone()

    if not task:
        return {"error": f"Task {task_id!r} not found"}

    # ── 2. Compute duration ──────────────────────────────────────────────────
    if duration_minutes is not None:
        dur = int(duration_minutes)
    elif task["effort_hours"] is not None:
        dur = max(15, int(float(task["effort_hours"]) * 60))
    else:
        dur = DEFAULT_DURATION_MINUTES

    # ── 3. Parse start/end times ─────────────────────────────────────────────
    # Normalise: if no timezone, treat as local (attach +00:00 for Google compat)
    try:
        dt_start = datetime.fromisoformat(start_at)
    except ValueError as exc:
        return {"error": f"Invalid start_at: {exc}"}

    if dt_start.tzinfo is None:
        dt_start = dt_start.replace(tzinfo=timezone.utc)

    dt_end = dt_start + timedelta(minutes=dur)
    start_iso = dt_start.isoformat()
    end_iso   = dt_end.isoformat()
    scheduled_date = dt_start.date().isoformat()   # YYYY-MM-DD stored on task

    title = task["title"]
    description = task.get("description") or ""
    event_description = (
        f"Atlas task: {ATLAS_BASE_URL}/tasks/{task_id}\n\n{description}".rstrip()
    )

    # ── 4. Create calendar event ─────────────────────────────────────────────
    cal_status = "skipped"
    try:
        resp = httpx.post(
            f"{CALENDAR_CONNECTOR_URL}/api/calendar/events",
            json={
                "atlas_event_id": task_id,
                "title":          f"[Atlas] {title}",
                "start_at":       start_iso,
                "end_at":         end_iso,
                "description":    event_description,
                "all_day":        False,
            },
            timeout=10.0,
        )
        if resp.status_code in (200, 201):
            cal_status = resp.json().get("status", "created")
        else:
            # Non-fatal — log and carry on; task will still be scheduled
            cal_status = f"error_{resp.status_code}"
    except Exception as exc:
        cal_status = f"error_{type(exc).__name__}"

    # ── 5. Update task: status=scheduled, scheduled_at=date ──────────────────
    with _pg() as con, con.cursor() as cur:
        cur.execute(
            """
            UPDATE tasktracker.tasks
               SET status       = 'scheduled',
                   scheduled_at = %s::date,
                   updated_at   = now()
             WHERE id = %s
            """,
            (scheduled_date, task_id),
        )
        con.commit()

    return {
        "task_id":          task_id,
        "title":            title,
        "scheduled_date":   scheduled_date,
        "start_at":         start_iso,
        "end_at":           end_iso,
        "duration_minutes": dur,
        "calendar_status":  cal_status,
        "message": (
            f"Task '{title}' scheduled for {scheduled_date}. "
            f"Calendar event {cal_status}. Duration: {dur} min."
        ),
    }
