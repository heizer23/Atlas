import logging
import os
import uuid
from datetime import date, timedelta
from typing import Any

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from backend.database import get_db
from backend.recurrence import (
    VALID_RECURRENCE_FREQ,
    VALID_RECURRENCE_MODE,
    compute_next_date,
    format_recurrence_label,
)
from platform_errorhandling import api_error
from platform_contracts import ColumnSchema, Dataset, DatasetMeta

log = logging.getLogger("tasktracker")

# ── Platform service clients ──────────────────────────────────────────────────

LABEL_ENGINE_URL      = os.environ.get("LABEL_ENGINE_URL",      "http://localhost:8050")
PREFERENCE_STORE_URL  = os.environ.get("PREFERENCE_STORE_URL",  "http://localhost:8060")
CALENDAR_CONNECTOR_URL = os.environ.get("CALENDAR_CONNECTOR_URL", "")
ATLAS_BASE_URL         = os.environ.get("ATLAS_BASE_URL",         "https://workout.linspad.net")


def _label_client() -> httpx.Client:
    return httpx.Client(base_url=LABEL_ENGINE_URL, timeout=5.0)

def _preference_client() -> httpx.Client:
    return httpx.Client(base_url=PREFERENCE_STORE_URL, timeout=5.0)

def _calendar_client() -> httpx.Client:
    return httpx.Client(base_url=CALENDAR_CONNECTOR_URL, timeout=5.0)


def _sync_calendar_event(
    task_id: str,
    title: str,
    scheduled_at: "date | None",
    description: "str | None",
    action: str,
) -> None:
    """Best-effort calendar sync — never raises, never blocks the task response.

    action: 'create' | 'update' | 'delete'
    If CALENDAR_CONNECTOR_URL is empty, returns immediately (silent skip).
    All errors are logged as warnings and swallowed.
    Must be called AFTER DB commit.
    """
    if not CALENDAR_CONNECTOR_URL:
        return

    prefixed_title = f"[Atlas] {title}"
    event_description = f"Atlas task: {ATLAS_BASE_URL}/tasks/{task_id}\n\n{description or ''}"

    try:
        with _calendar_client() as client:
            if action == "create":
                start_at = scheduled_at.isoformat()
                end_at = (scheduled_at + timedelta(days=1)).isoformat()
                resp = client.post(
                    "/api/calendar/events",
                    json={
                        "atlas_event_id": task_id,
                        "title": prefixed_title,
                        "start_at": start_at,
                        "end_at": end_at,
                        "description": event_description,
                        "all_day": True,
                    },
                )
                if resp.status_code not in (200, 201):
                    log.warning(
                        "Calendar create returned non-2xx: status=%s body=%s task_id=%s",
                        resp.status_code, resp.text[:200], task_id,
                    )
            elif action == "update":
                start_at = scheduled_at.isoformat()
                end_at = (scheduled_at + timedelta(days=1)).isoformat()
                resp = client.patch(
                    f"/api/calendar/events/{task_id}",
                    json={
                        "title": prefixed_title,
                        "start_at": start_at,
                        "end_at": end_at,
                        "description": event_description,
                        "all_day": True,
                    },
                )
                if resp.status_code != 200:
                    log.warning(
                        "Calendar update returned non-2xx: status=%s body=%s task_id=%s",
                        resp.status_code, resp.text[:200], task_id,
                    )
            elif action == "delete":
                resp = client.delete(f"/api/calendar/events/{task_id}")
                if resp.status_code != 200:
                    log.warning(
                        "Calendar delete returned non-2xx: status=%s body=%s task_id=%s",
                        resp.status_code, resp.text[:200], task_id,
                    )
    except Exception as exc:
        log.warning("Calendar sync failed (best-effort, task unaffected): action=%s task_id=%s error=%s", action, task_id, exc)

router = APIRouter(prefix="/tasks", tags=["tasks"])

# ── Column schema — stable; matches schema.sql ────────────────────────────────

TASK_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="title",                    label="Title",             type="string", sortable=True,  filterable=False),
    ColumnSchema(key="status",                   label="Status",            type="enum",   sortable=True,  filterable=True),
    ColumnSchema(key="priority",                 label="Priority",          type="enum",   sortable=True,  filterable=True),
    ColumnSchema(key="due_date",                 label="Due Date",          type="date",   sortable=True,  filterable=False),
    ColumnSchema(key="effort_hours",             label="Effort (h)",        type="number", sortable=True,  filterable=False),
    ColumnSchema(key="created_at",               label="Created",           type="date",   sortable=True,  filterable=False),
    ColumnSchema(key="description",              label="Description",       type="string", sortable=False, filterable=False, detail_visible=True),
    ColumnSchema(key="task_type",                label="Type",              type="string", sortable=False, filterable=False),
    ColumnSchema(key="parent_task_id",           label="Parent",            type="string", sortable=False, filterable=False),
    ColumnSchema(key="actual_duration_minutes",  label="Duration (min)",    type="number", sortable=False, filterable=False),
    ColumnSchema(key="completed_at",             label="Completed At",      type="date",   sortable=False, filterable=False),
    ColumnSchema(key="scheduled_at",             label="Scheduled At",      type="string", sortable=True,  filterable=False),
    ColumnSchema(key="recurrence_freq",          label="Repeat",            type="enum",   sortable=False, filterable=False),
    ColumnSchema(key="recurrence_interval",      label="Repeat Interval",   type="number", sortable=False, filterable=False),
    ColumnSchema(key="recurrence_mode",          label="Repeat Mode",       type="enum",   sortable=False, filterable=False),
    ColumnSchema(key="recurrence_next_id",       label="Next Occurrence",   type="string", sortable=False, filterable=False),
    ColumnSchema(key="recurrence_label",         label="Repeat Summary",    type="string", sortable=False, filterable=False),
    ColumnSchema(key="recurrence_next_date",     label="Next Date",         type="date",   sortable=False, filterable=False),
]

# Agenda adds the bucket and the effective date
AGENDA_SCHEMA: list[ColumnSchema] = TASK_SCHEMA + [
    ColumnSchema(key="agenda_bucket", label="Bucket", type="enum", sortable=False, filterable=False),
    ColumnSchema(key="agenda_date",   label="Date",   type="date", sortable=True,  filterable=False),
]

TASK_SELECT_COLS = """id, title, description, status, priority, due_date,
                     effort_hours, created_at, updated_at,
                     task_type, parent_task_id, actual_duration_minutes, completed_at,
                     scheduled_at, recurrence_freq, recurrence_interval, recurrence_mode,
                     recurrence_next_id"""

AGENDA_WINDOW_DAYS = 7

# Schema for the training-units endpoint (declares derived fields)
TRAINING_UNIT_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="id",                       label="ID",                type="string", sortable=False, filterable=False),
    ColumnSchema(key="title",                    label="Title",             type="string", sortable=True,  filterable=False),
    ColumnSchema(key="status",                   label="Status",            type="enum",   sortable=True,  filterable=True),
    ColumnSchema(key="priority",                 label="Priority",          type="enum",   sortable=True,  filterable=True),
    ColumnSchema(key="labels",                   label="Labels",            type="string", sortable=False, filterable=False),
    ColumnSchema(key="actual_duration_minutes",  label="Duration (min)",    type="number", sortable=False, filterable=False),
    ColumnSchema(key="completed_at",             label="Completed At",      type="date",   sortable=False, filterable=False),
    ColumnSchema(key="last_child_completed_at",  label="Last Activity",     type="date",   sortable=True,  filterable=False),
    ColumnSchema(key="completed_child_count",    label="Done Sessions",     type="number", sortable=False, filterable=False),
    ColumnSchema(key="total_child_count",        label="Total Sessions",    type="number", sortable=False, filterable=False),
    ColumnSchema(key="description",              label="Description",       type="string", sortable=False, filterable=False, detail_visible=True),
]

VALID_STATUS   = {"open", "in_progress", "scheduled", "pending", "done"}
VALID_PRIORITY = {"low", "medium", "high"}
VALID_TASK_TYPE = {"normal", "training_unit", "training_session"}

# ── Request bodies ─────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    title:                   str
    description:             str | None = None
    status:                  str = "open"
    priority:                str = "medium"
    due_date:                str | None = None
    effort_hours:            float | None = None
    task_type:               str = "normal"
    parent_task_id:          str | None = None
    actual_duration_minutes: int | None = None
    scheduled_at:            str | None = None
    recurrence_freq:         str | None = None
    recurrence_interval:     int = 1
    recurrence_mode:         str = "fixed"


class TaskUpdate(BaseModel):
    title:                   str | None = None
    description:             str | None = None
    status:                  str | None = None
    priority:                str | None = None
    due_date:                str | None = None
    effort_hours:            float | None = None
    task_type:               str | None = None
    parent_task_id:          str | None = None
    actual_duration_minutes: int | None = None
    scheduled_at:            str | None = None
    recurrence_freq:         str | None = None
    recurrence_interval:     int | None = None
    recurrence_mode:         str | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def row_to_dict(row: Any) -> dict[str, Any]:
    d = dict(row)
    d["id"] = str(d["id"])
    if d.get("due_date"):
        d["due_date"] = str(d["due_date"])
    if d.get("created_at"):
        d["created_at"] = d["created_at"].date().isoformat()
    if d.get("updated_at"):
        d["updated_at"] = d["updated_at"].date().isoformat()
    if d.get("completed_at"):
        d["completed_at"] = d["completed_at"].isoformat()
    if d.get("scheduled_at"):
        d["scheduled_at"] = d["scheduled_at"].isoformat()
    if d.get("parent_task_id"):
        d["parent_task_id"] = str(d["parent_task_id"])
    if d.get("recurrence_next_id"):
        d["recurrence_next_id"] = str(d["recurrence_next_id"])
    if "recurrence_freq" in d:
        d["recurrence_label"] = format_recurrence_label(
            d["recurrence_freq"], d.get("recurrence_interval") or 1, d.get("recurrence_mode") or "fixed"
        )
        d["recurrence_next_date"] = None
    return d


def fetch_labels_for_tasks(task_ids: list[str]) -> dict[str, list[dict]]:
    """Return a mapping of task_id -> [{id, name, attached_at}, ...] via LabelEngine batch API."""
    if not task_ids:
        return {}
    with _label_client() as client:
        resp = client.post(
            "/api/objects/labels/batch",
            json={"object_ids": task_ids, "object_type": "task"},
        )
    if resp.status_code != 200:
        return {}
    return resp.json().get("labels", {})


def dataset_response(dataset: Dataset) -> JSONResponse:
    return JSONResponse(content=dataset.model_dump(by_alias=True, mode="json"))


def single_row_dataset(row: Any, extra: "dict[str, Any] | None" = None) -> JSONResponse:
    row_dict = row_to_dict(row)
    if extra:
        row_dict.update(extra)
    return dataset_response(Dataset(
        meta=DatasetMeta(
            object_type="task",
            label="Task",
            total=1,
            page=1,
            page_size=1,
            row_actions=["edit", "delete"],
        ),
        **{"schema": TASK_SCHEMA},
        rows=[row_dict],
    ))


# ── Endpoints ─────────────────────────────────────────────────────────────────

VALID_VIEW = {"active", "pending_board", "scheduled"}


def _run_auto_promotion(conn: Any) -> None:
    """Promote scheduled tasks whose scheduled_at is today or in the past.

    Runs as a side-effect of the active and pending_board view fetches.
    Executes within the caller's connection; caller must commit.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            update tasktracker.tasks
               set status = 'in_progress', updated_at = now()
             where status = 'scheduled'
               and scheduled_at is not null
               and scheduled_at <= current_date
            """
        )


@router.get("/training-units", response_model=None)
def list_training_units() -> JSONResponse:
    """List all training_unit tasks with derived child aggregate fields.

    Returns Dataset with TRAINING_UNIT_SCHEMA columns.
    Sort order: DONE units first (by last_child_completed_at DESC), then OPEN units
    (by priority DESC using high > medium > low mapping).
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    t.id,
                    t.title,
                    t.description,
                    t.status,
                    t.priority,
                    t.actual_duration_minutes,
                    t.completed_at,
                    max(c.completed_at) as last_child_completed_at,
                    count(c.id) filter (where c.status = 'done') as completed_child_count,
                    count(c.id) as total_child_count
                from tasktracker.tasks t
                left join tasktracker.tasks c
                    on c.parent_task_id = t.id
                    and c.task_type = 'training_session'
                where t.task_type = 'training_unit'
                group by t.id, t.title, t.description, t.status, t.priority,
                         t.actual_duration_minutes, t.completed_at
                order by
                    case when t.status = 'done' then 0 else 1 end asc,
                    case when t.status = 'done' then max(c.completed_at) end desc nulls last,
                    case t.priority
                        when 'high'   then 1
                        when 'medium' then 2
                        when 'low'    then 3
                        else 4
                    end asc
                """
            )
            rows = cur.fetchall()

    unit_ids = [str(r["id"]) for r in rows]
    labels_by_task = fetch_labels_for_tasks(unit_ids)

    result_rows = []
    for r in rows:
        d: dict[str, Any] = {}
        d["id"] = str(r["id"])
        d["title"] = r["title"]
        d["description"] = r["description"]
        d["status"] = r["status"]
        d["priority"] = r["priority"]
        d["actual_duration_minutes"] = r["actual_duration_minutes"]
        d["completed_at"] = r["completed_at"].isoformat() if r["completed_at"] else None
        d["last_child_completed_at"] = r["last_child_completed_at"].isoformat() if r["last_child_completed_at"] else None
        d["completed_child_count"] = r["completed_child_count"] or 0
        d["total_child_count"] = r["total_child_count"] or 0
        d["labels"] = labels_by_task.get(d["id"], [])
        result_rows.append(d)

    return dataset_response(Dataset(
        meta=DatasetMeta(
            object_type="training_unit",
            label="Training Units",
            total=len(result_rows),
            page=1,
            page_size=max(len(result_rows), 1),
            row_actions=["edit"],
        ),
        **{"schema": TRAINING_UNIT_SCHEMA},
        rows=result_rows,
    ))


@router.get("", response_model=None)
def list_tasks(
    status:         str | None = None,
    view:           str | None = None,
    task_type:      str | None = None,
    parent_task_id: str | None = None,
    page:           int = 1,
    page_size:      int = 25,
) -> JSONResponse:
    if status and status not in VALID_STATUS:
        return api_error("INVALID_FILTER", f"status must be one of: {', '.join(sorted(VALID_STATUS))}")
    if view and view not in VALID_VIEW:
        return api_error("INVALID_FILTER", f"view must be one of: {', '.join(sorted(VALID_VIEW))}")
    if task_type and task_type not in VALID_TASK_TYPE:
        return api_error("INVALID_FILTER", f"task_type must be one of: {', '.join(sorted(VALID_TASK_TYPE))}")
    if page < 1:
        return api_error("INVALID_PARAM", "page must be >= 1")

    offset = (page - 1) * page_size

    # Build extra filters beyond the view-specific WHERE clause.
    # By default, training_unit tasks are excluded from the main list.
    # If task_type is explicitly specified, use it directly.
    # Otherwise add task_type != 'training_unit' to all branches.
    extra_conditions: list[str] = []
    extra_params: list[Any] = []

    if task_type:
        extra_conditions.append("task_type = %s")
        extra_params.append(task_type)
    else:
        extra_conditions.append("task_type != 'training_unit'")

    if parent_task_id:
        extra_conditions.append("parent_task_id = %s")
        extra_params.append(parent_task_id)

    extra_sql = (" and " + " and ".join(extra_conditions)) if extra_conditions else ""

    select_cols = TASK_SELECT_COLS

    with get_db() as conn:
        with conn.cursor() as cur:
            if view == "active":
                # Auto-promote scheduled tasks whose time has arrived
                _run_auto_promotion(conn)
                conn.commit()  # persist promotion (otherwise rolled back when the connection is returned)
                # Active view: open + in_progress (excluding scheduled), plus done tasks updated today
                cur.execute(
                    f"""
                    select count(*) from tasktracker.tasks
                    where (status not in ('done', 'pending', 'scheduled')
                       or (status = 'done' and updated_at::date >= current_date))
                    {extra_sql}
                    """,
                    extra_params,
                )
                total = cur.fetchone()["count"]
                cur.execute(
                    f"""
                    select {select_cols}
                    from tasktracker.tasks
                    where (status not in ('done', 'pending', 'scheduled')
                       or (status = 'done' and updated_at::date >= current_date))
                    {extra_sql}
                    order by created_at desc
                    limit %s offset %s
                    """,
                    extra_params + [page_size, offset],
                )
            elif view == "pending_board":
                # Auto-promote scheduled tasks whose time has arrived
                _run_auto_promotion(conn)
                conn.commit()  # persist promotion (otherwise rolled back when the connection is returned)
                # Pending board: open + pending tasks
                cur.execute(
                    f"select count(*) from tasktracker.tasks where status in ('open', 'pending'){extra_sql}",
                    extra_params,
                )
                total = cur.fetchone()["count"]
                cur.execute(
                    f"""
                    select {select_cols}
                    from tasktracker.tasks
                    where status in ('open', 'pending')
                    {extra_sql}
                    order by created_at desc
                    limit %s offset %s
                    """,
                    extra_params + [page_size, offset],
                )
            elif view == "scheduled":
                # Scheduled view: tasks with status=scheduled ordered by scheduled_at ASC
                cur.execute(
                    f"select count(*) from tasktracker.tasks where status = 'scheduled'{extra_sql}",
                    extra_params,
                )
                total = cur.fetchone()["count"]
                cur.execute(
                    f"""
                    select {select_cols}
                    from tasktracker.tasks
                    where status = 'scheduled'
                    {extra_sql}
                    order by scheduled_at asc nulls last
                    limit %s offset %s
                    """,
                    extra_params + [page_size, offset],
                )
            elif status == "done":
                # Done view: sorted by last modified descending
                cur.execute(
                    f"select count(*) from tasktracker.tasks where status = 'done'{extra_sql}",
                    extra_params,
                )
                total = cur.fetchone()["count"]
                cur.execute(
                    f"""
                    select {select_cols}
                    from tasktracker.tasks
                    where status = 'done'
                    {extra_sql}
                    order by updated_at desc
                    limit %s offset %s
                    """,
                    extra_params + [page_size, offset],
                )
            elif status:
                cur.execute(
                    f"select count(*) from tasktracker.tasks where status = %s{extra_sql}",
                    [status] + extra_params,
                )
                total = cur.fetchone()["count"]
                cur.execute(
                    f"""
                    select {select_cols}
                    from tasktracker.tasks
                    where status = %s
                    {extra_sql}
                    order by created_at desc
                    limit %s offset %s
                    """,
                    [status] + extra_params + [page_size, offset],
                )
            else:
                cur.execute(
                    f"select count(*) from tasktracker.tasks where 1=1{extra_sql}",
                    extra_params,
                )
                total = cur.fetchone()["count"]
                # When fetching child tasks by parent_task_id, sort oldest-first (created_at ASC).
                # Default ordering is newest-first.
                order_dir = "asc" if parent_task_id else "desc"
                cur.execute(
                    f"""
                    select {select_cols}
                    from tasktracker.tasks
                    where 1=1
                    {extra_sql}
                    order by created_at {order_dir}
                    limit %s offset %s
                    """,
                    extra_params + [page_size, offset],
                )

            rows = [row_to_dict(r) for r in cur.fetchall()]

        # Embed labels into each row using a single batch query
        task_ids = [r["id"] for r in rows]
        labels_by_task = fetch_labels_for_tasks(task_ids)
        for r in rows:
            r["labels"] = labels_by_task.get(r["id"], [])

    return dataset_response(Dataset(
        meta=DatasetMeta(
            object_type="task",
            label="Tasks",
            total=total,
            page=page,
            page_size=page_size,
            row_actions=["edit", "delete"],
        ),
        **{"schema": TASK_SCHEMA},
        rows=rows,
    ))


@router.get("/agenda", response_model=None)
def list_agenda() -> JSONResponse:
    """Agenda window: overdue + today + next AGENDA_WINDOW_DAYS days, flat list.

    Effective date = coalesce(scheduled_at, due_date).
    Excludes done and training_unit tasks. Time authority: Postgres current_date.
    Order: agenda_date asc, priority high>medium>low, created_at asc, id asc.
    """
    with get_db() as conn:
        _run_auto_promotion(conn)
        conn.commit()  # persist promotion (list_tasks views do not commit)
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select * from (
                    select {TASK_SELECT_COLS},
                           coalesce(scheduled_at, due_date) as agenda_date
                    from tasktracker.tasks
                    where status != 'done' and task_type != 'training_unit'
                ) t
                where agenda_date is not null
                  and agenda_date <= current_date + %s
                order by agenda_date asc,
                         case priority when 'high' then 1 when 'medium' then 2 else 3 end asc,
                         created_at asc, id asc
                """,  # noqa: S608
                (AGENDA_WINDOW_DAYS,),
            )
            raw_rows = cur.fetchall()
            cur.execute("select current_date as today")
            today = cur.fetchone()["today"]
        conn.rollback()  # end the read transaction

        rows = []
        for r in raw_rows:
            agenda_date = r["agenda_date"]
            d = row_to_dict({k: v for k, v in r.items() if k != "agenda_date"})
            d["agenda_date"] = agenda_date.isoformat()
            d["agenda_bucket"] = (
                "overdue" if agenda_date < today else "today" if agenda_date == today else "upcoming"
            )
            rows.append(d)

        try:
            labels_by_task = fetch_labels_for_tasks([r["id"] for r in rows])
        except Exception as exc:
            log.warning("Agenda label fetch failed: %s", exc)
            labels_by_task = {}
        for r in rows:
            r["labels"] = labels_by_task.get(r["id"], [])

    return dataset_response(Dataset(
        meta=DatasetMeta(
            object_type="task",
            label="Agenda",
            total=len(rows),
            page=1,
            page_size=max(len(rows), 1),
            row_actions=["edit", "delete"],
        ),
        **{"schema": AGENDA_SCHEMA},
        rows=rows,
    ))


def _validate_recurrence_values(freq: "str | None", interval: int, mode: str) -> "str | None":
    """Body-level checks on recurrence values."""
    if freq is not None and freq not in VALID_RECURRENCE_FREQ:
        return f"recurrence_freq must be one of: {', '.join(sorted(VALID_RECURRENCE_FREQ))}"
    if mode not in VALID_RECURRENCE_MODE:
        return f"recurrence_mode must be one of: {', '.join(sorted(VALID_RECURRENCE_MODE))}"
    if interval < 1:
        return "recurrence_interval must be >= 1"
    return None


def _validate_recurrence(
    freq: "str | None",
    interval: int,
    mode: str,
    task_type: str,
    status: str,
    due_date: Any,
    scheduled_at: Any,
) -> "str | None":
    """Merged-state recurrence validation. Returns an error message or None."""
    if freq is None:
        return None
    msg = _validate_recurrence_values(freq, interval, mode)
    if msg:
        return msg
    if task_type != "normal":
        return "recurring tasks must have task_type 'normal'"
    if mode == "fixed" and status != "done" and not due_date and not scheduled_at:
        return "a fixed recurring task requires due_date or scheduled_at"
    return None


def _spawn_successor(cur: Any, pre: dict[str, Any], post: dict[str, Any]) -> dict[str, Any]:
    """Create the next occurrence in the caller's transaction. Does not commit.

    pre = locked snapshot row, post = row after the status UPDATE.
    Returns the successor row dict with extra key 'next_date'.
    """
    cur.execute("select current_date as today")
    today = cur.fetchone()["today"]

    # Edit form clears scheduled_at on save, so fall back to the snapshot when it was scheduled
    schedule_date = post["scheduled_at"] or (pre["scheduled_at"] if pre["status"] == "scheduled" else None)
    anchor = schedule_date or post["due_date"]
    next_date = compute_next_date(
        anchor, post["recurrence_freq"], post["recurrence_interval"], post["recurrence_mode"], today
    )

    if schedule_date:
        status = "scheduled"
        scheduled_at = next_date
        due_date = (post["due_date"] + (next_date - schedule_date)) if post["due_date"] else None
    else:
        status = "open"
        scheduled_at = None
        due_date = next_date

    successor_id = str(uuid.uuid4())
    cur.execute(
        """
        insert into tasktracker.tasks
            (id, title, description, status, priority, due_date, effort_hours,
             task_type, parent_task_id, scheduled_at,
             recurrence_freq, recurrence_interval, recurrence_mode)
        values (%s, %s, %s, %s, %s, %s, %s, 'normal', %s, %s, %s, %s, %s)
        returning *
        """,
        (
            successor_id, post["title"], post["description"], status, post["priority"],
            due_date, post["effort_hours"], post["parent_task_id"], scheduled_at,
            post["recurrence_freq"], post["recurrence_interval"], post["recurrence_mode"],
        ),
    )
    successor = dict(cur.fetchone())
    cur.execute(
        "update tasktracker.tasks set recurrence_next_id = %s where id = %s",
        (successor_id, str(post["id"])),
    )
    successor["next_date"] = next_date
    return successor


def _copy_labels_best_effort(source_id: str, successor_id: str) -> None:
    """Copy source labels onto the successor via LabelEngine. Never raises. Call after commit."""
    try:
        with _label_client() as client:
            resp = client.get(f"/api/objects/{source_id}/labels")
            if resp.status_code != 200:
                log.warning("Label copy: source labels fetch returned %s task_id=%s", resp.status_code, source_id)
                return
            for lbl in resp.json().get("labels", []):
                r = client.post(
                    f"/api/objects/{successor_id}/labels",
                    json={"label_name": lbl["label_name"], "object_type": "task"},
                )
                if r.status_code not in (200, 201):
                    log.warning("Label copy: attach returned %s task_id=%s", r.status_code, successor_id)
    except Exception as exc:
        log.warning("Label copy failed (best-effort): source=%s successor=%s error=%s", source_id, successor_id, exc)


@router.post("", response_model=None)
def create_task(body: TaskCreate) -> JSONResponse:
    if not body.title.strip():
        return api_error("VALIDATION_ERROR", "title cannot be empty")
    if body.status not in {"open", "pending", "scheduled"}:
        return api_error("VALIDATION_ERROR", "status must be one of: open, pending, scheduled")
    if body.status == "scheduled" and not body.scheduled_at:
        return api_error("VALIDATION_ERROR", "scheduled_at is required when status is scheduled")
    if body.priority not in VALID_PRIORITY:
        return api_error("VALIDATION_ERROR", f"priority must be one of: {', '.join(sorted(VALID_PRIORITY))}")
    if body.effort_hours is not None and body.effort_hours < 0:
        return api_error("VALIDATION_ERROR", "effort_hours must be >= 0")
    if body.task_type not in VALID_TASK_TYPE:
        return api_error("VALIDATION_ERROR", f"task_type must be one of: {', '.join(sorted(VALID_TASK_TYPE))}")
    if body.actual_duration_minutes is not None and body.actual_duration_minutes < 0:
        return api_error("VALIDATION_ERROR", "actual_duration_minutes must be >= 0")
    msg = _validate_recurrence_values(body.recurrence_freq, body.recurrence_interval, body.recurrence_mode)
    if msg:
        return api_error("VALIDATION_ERROR", msg)
    rec_freq     = body.recurrence_freq
    rec_interval = body.recurrence_interval if rec_freq else 1
    rec_mode     = body.recurrence_mode if rec_freq else "fixed"
    msg = _validate_recurrence(
        rec_freq, rec_interval, rec_mode, body.task_type, body.status,
        body.due_date, body.scheduled_at,
    )
    if msg:
        return api_error("VALIDATION_ERROR", msg)

    task_id = str(uuid.uuid4())
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into tasktracker.tasks
                    (id, title, description, status, priority, due_date, effort_hours,
                     task_type, parent_task_id, actual_duration_minutes, scheduled_at,
                     recurrence_freq, recurrence_interval, recurrence_mode)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                returning *
                """,
                (
                    task_id,
                    body.title.strip(),
                    body.description or None,
                    body.status,
                    body.priority,
                    body.due_date or None,
                    body.effort_hours,
                    body.task_type,
                    body.parent_task_id or None,
                    body.actual_duration_minutes,
                    body.scheduled_at or None,
                    rec_freq,
                    rec_interval,
                    rec_mode,
                ),
            )
            row = cur.fetchone()
        conn.commit()

    # Best-effort calendar sync — after commit, never blocks response
    if body.status == "scheduled" and body.scheduled_at:
        _sync_calendar_event(
            task_id=task_id,
            title=body.title.strip(),
            scheduled_at=date.fromisoformat(body.scheduled_at),
            description=body.description,
            action="create",
        )

    return single_row_dataset(row)


@router.patch("/{task_id}", response_model=None)
def update_task(task_id: str, body: TaskUpdate) -> JSONResponse:
    if body.status and body.status not in VALID_STATUS:
        return api_error("VALIDATION_ERROR", f"status must be one of: {', '.join(sorted(VALID_STATUS))}")
    if body.priority and body.priority not in VALID_PRIORITY:
        return api_error("VALIDATION_ERROR", f"priority must be one of: {', '.join(sorted(VALID_PRIORITY))}")
    if body.effort_hours is not None and body.effort_hours < 0:
        return api_error("VALIDATION_ERROR", "effort_hours must be >= 0")
    if body.task_type and body.task_type not in VALID_TASK_TYPE:
        return api_error("VALIDATION_ERROR", f"task_type must be one of: {', '.join(sorted(VALID_TASK_TYPE))}")
    if body.actual_duration_minutes is not None and body.actual_duration_minutes < 0:
        return api_error("VALIDATION_ERROR", "actual_duration_minutes must be >= 0")
    sent = body.model_fields_set
    if "recurrence_interval" in sent and body.recurrence_interval is None:
        return api_error("VALIDATION_ERROR", "recurrence_interval cannot be null")
    if "recurrence_mode" in sent and body.recurrence_mode is None:
        return api_error("VALIDATION_ERROR", "recurrence_mode cannot be null")
    msg = _validate_recurrence_values(
        body.recurrence_freq,
        body.recurrence_interval if body.recurrence_interval is not None else 1,
        body.recurrence_mode if body.recurrence_mode is not None else "fixed",
    )
    if msg:
        return api_error("VALIDATION_ERROR", msg)

    fields: dict[str, Any] = {}
    if body.title       is not None: fields["title"]       = body.title.strip() or None
    if body.description is not None: fields["description"] = body.description or None
    if body.status      is not None: fields["status"]      = body.status
    if body.priority    is not None: fields["priority"]    = body.priority
    if body.task_type   is not None: fields["task_type"]   = body.task_type
    # Use model_fields_set to distinguish "not sent" (skip) from "explicitly null" (clear column)
    if "due_date"                in body.model_fields_set: fields["due_date"]                = body.due_date or None
    if "effort_hours"            in body.model_fields_set: fields["effort_hours"]            = body.effort_hours
    if "actual_duration_minutes" in body.model_fields_set: fields["actual_duration_minutes"] = body.actual_duration_minutes
    if "parent_task_id"          in body.model_fields_set: fields["parent_task_id"]          = body.parent_task_id or None
    if "scheduled_at"            in body.model_fields_set: fields["scheduled_at"]            = body.scheduled_at or None

    if not fields and not (sent & {"recurrence_freq", "recurrence_interval", "recurrence_mode"}):
        return api_error("VALIDATION_ERROR", "no fields provided to update")

    # Fetch current row (locked) to determine status transitions, recurrence and calendar sync
    successor: dict[str, Any] | None = None
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select * from tasktracker.tasks where id = %s for update",
                (task_id,),
            )
            current = cur.fetchone()

        if current is None:
            conn.rollback()
            return api_error("NOT_FOUND", f"task {task_id} not found", status=404)

        # Merged-state recurrence validation + normalisation
        res_freq = body.recurrence_freq if "recurrence_freq" in sent else current["recurrence_freq"]
        res_interval = body.recurrence_interval if "recurrence_interval" in sent else current["recurrence_interval"]
        res_mode = body.recurrence_mode if "recurrence_mode" in sent else current["recurrence_mode"]
        if res_freq is None:
            res_interval, res_mode = 1, "fixed"
        msg = _validate_recurrence(
            res_freq, res_interval, res_mode,
            fields.get("task_type", current["task_type"]),
            fields.get("status", current["status"]),
            fields["due_date"] if "due_date" in fields else current["due_date"],
            fields["scheduled_at"] if "scheduled_at" in fields else current["scheduled_at"],
        )
        if msg:
            conn.rollback()
            return api_error("VALIDATION_ERROR", msg)
        if "recurrence_freq" in sent:
            fields["recurrence_freq"] = res_freq
        if res_freq is None:
            if sent & {"recurrence_freq", "recurrence_interval", "recurrence_mode"}:
                fields["recurrence_interval"] = 1
                fields["recurrence_mode"] = "fixed"
        else:
            if "recurrence_interval" in sent: fields["recurrence_interval"] = res_interval
            if "recurrence_mode"     in sent: fields["recurrence_mode"]     = res_mode

        # If transitioning to scheduled, ensure scheduled_at is set (from body or existing)
        new_status_from_body = fields.get("status")
        if new_status_from_body == "scheduled":
            # scheduled_at must be present: either provided in this PATCH or already non-null in DB
            scheduled_at_in_body = "scheduled_at" in body.model_fields_set and body.scheduled_at
            scheduled_at_in_db   = current.get("scheduled_at") is not None
            if not scheduled_at_in_body and not scheduled_at_in_db:
                conn.rollback()
                return api_error("VALIDATION_ERROR", "scheduled_at is required when status is scheduled")

        # Server-side completed_at management:
        # - Set completed_at = now() when transitioning TO done AND completed_at IS NULL
        # - Clear completed_at when transitioning FROM done to any other status
        new_status = fields.get("status")
        if new_status == "done" and current["status"] != "done" and current["completed_at"] is None:
            fields["completed_at"] = "now()"
        elif new_status and new_status != "done" and current["status"] == "done":
            fields["completed_at"] = None

        # Build SET clause — completed_at = now() is a SQL function, not a param
        set_parts = []
        values: list[Any] = []
        for k, v in fields.items():
            if k == "completed_at" and v == "now()":
                set_parts.append("completed_at = now()")
            else:
                set_parts.append(f"{k} = %s")
                values.append(v)
        set_parts.append("updated_at = now()")
        set_clause = ", ".join(set_parts)
        values.append(task_id)

        with conn.cursor() as cur:
            cur.execute(
                f"update tasktracker.tasks set {set_clause} where id = %s returning *",  # noqa: S608
                values,
            )
            row = cur.fetchone()

            # Spawn the next occurrence in the same transaction (exactly once)
            if (
                current["status"] != "done"
                and row["status"] == "done"
                and row["recurrence_freq"] is not None
                and row["recurrence_next_id"] is None
            ):
                successor = _spawn_successor(cur, current, row)
        conn.commit()

    if row is None:
        return api_error("NOT_FOUND", f"task {task_id} not found", status=404)

    # Best-effort calendar sync — after commit, never blocks response
    old_status = current["status"]
    new_status_resolved = fields.get("status") or old_status

    if new_status_resolved == "scheduled" and old_status != "scheduled":
        # Transition TO scheduled: create calendar event
        sched = body.scheduled_at or (
            current["scheduled_at"].isoformat() if current.get("scheduled_at") else None
        )
        if sched:
            new_title = fields.get("title", current["title"])
            new_desc = fields.get("description", current.get("description"))
            _sync_calendar_event(
                task_id=task_id,
                title=new_title,
                scheduled_at=date.fromisoformat(sched) if isinstance(sched, str) else sched,
                description=new_desc,
                action="create",
            )
    elif new_status_resolved == "scheduled" and old_status == "scheduled":
        # Still scheduled — check if scheduled_at or title changed
        new_sched_at = fields.get("scheduled_at")
        new_title_val = fields.get("title")
        scheduled_at_changed = "scheduled_at" in body.model_fields_set and new_sched_at != (
            current["scheduled_at"].isoformat() if current.get("scheduled_at") else None
        )
        title_changed = "title" in body.model_fields_set and new_title_val and new_title_val.strip() != current.get("title", "")
        if scheduled_at_changed or title_changed:
            resolved_sched = new_sched_at or (
                current["scheduled_at"].isoformat() if current.get("scheduled_at") else None
            )
            resolved_title = (new_title_val.strip() if new_title_val else None) or current["title"]
            resolved_desc = fields.get("description", current.get("description"))
            if resolved_sched:
                _sync_calendar_event(
                    task_id=task_id,
                    title=resolved_title,
                    scheduled_at=date.fromisoformat(resolved_sched) if isinstance(resolved_sched, str) else resolved_sched,
                    description=resolved_desc,
                    action="update",
                )
    elif old_status == "scheduled" and new_status_resolved != "scheduled":
        # Transition AWAY from scheduled: delete calendar event
        _sync_calendar_event(
            task_id=task_id,
            title=current["title"],
            scheduled_at=None,
            description=None,
            action="delete",
        )

    extra = None
    if successor is not None:
        successor_id = str(successor["id"])
        if successor["status"] == "scheduled":
            _sync_calendar_event(
                task_id=successor_id,
                title=successor["title"],
                scheduled_at=successor["scheduled_at"],
                description=successor["description"],
                action="create",
            )
        _copy_labels_best_effort(task_id, successor_id)
        extra = {"recurrence_next_date": successor["next_date"].isoformat()}

    return single_row_dataset(row, extra)


@router.delete("/{task_id}", response_model=None)
def delete_task(task_id: str) -> JSONResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "delete from tasktracker.tasks where id = %s returning id",
                (task_id,),
            )
            deleted = cur.fetchone()
        conn.commit()

    if deleted is None:
        return api_error("NOT_FOUND", f"task {task_id} not found", status=404)

    return dataset_response(Dataset(
        meta=DatasetMeta(object_type="task", label="Tasks", total=0, page=1, page_size=1, row_actions=[]),
        **{"schema": TASK_SCHEMA},
        rows=[],
    ))


# ── Label proxy endpoints ─────────────────────────────────────────────────────
# Thin forwards to LabelEngine.  object_type is always "task".

class LabelAttachBody(BaseModel):
    label_name: str


@router.get("/labels/search", response_model=None)
def search_labels(q: str = "") -> JSONResponse:
    """Search labels by prefix via LabelEngine; returns Dataset."""
    with _label_client() as client:
        resp = client.get("/api/labels", params={"q": q})
    if resp.status_code != 200:
        return JSONResponse(status_code=resp.status_code, content=resp.json())
    items = resp.json().get("labels", [])
    return dataset_response(Dataset(
        meta=DatasetMeta(
            object_type="label",
            label="Labels",
            total=len(items),
            page=1,
            page_size=len(items),
            row_actions=[],
        ),
        **{"schema": [
            ColumnSchema(key="id",   label="ID",   type="string"),
            ColumnSchema(key="name", label="Name", type="string"),
        ]},
        rows=[{"id": item["id"], "name": item["name"]} for item in items],
    ))


@router.get("/labels/used", response_model=None)
def list_used_labels() -> JSONResponse:
    """Return all labels attached to at least one task via LabelEngine.

    Proxies LabelEngine GET /api/labels/used?object_type=task.
    On LabelEngine failure, returns an empty Dataset (graceful degradation).
    """
    _LABEL_SCHEMA = [
        ColumnSchema(key="id",   label="ID",   type="string"),
        ColumnSchema(key="name", label="Name", type="string"),
    ]
    try:
        with _label_client() as client:
            resp = client.get("/api/labels/used", params={"object_type": "task"})
        if resp.status_code != 200:
            items: list = []
        else:
            items = resp.json().get("labels", [])
    except Exception:
        items = []

    return dataset_response(Dataset(
        meta=DatasetMeta(
            object_type="label",
            label="Used Labels",
            total=len(items),
            page=1,
            page_size=max(len(items), 1),
            row_actions=[],
        ),
        **{"schema": _LABEL_SCHEMA},
        rows=[{"id": item["id"], "name": item["name"]} for item in items],
    ))


class LabelFilterPutBody(BaseModel):
    label_ids: list[str]


@router.get("/preferences/label_filter", response_model=None)
def get_label_filter_preference() -> JSONResponse:
    """Return the stored label filter selection from PreferenceStore.

    Returns Dataset (one row) on 200, or 404 ApiError if not yet saved.
    """
    with _preference_client() as client:
        resp = client.get("/api/preferences/tasktracker.task-list/label_filter")
    return JSONResponse(status_code=resp.status_code, content=resp.json())


@router.put("/preferences/label_filter", response_model=None)
def put_label_filter_preference(body: LabelFilterPutBody) -> JSONResponse:
    """Persist the label filter selection to PreferenceStore.

    Stores body.label_ids as a JSON array under scope=tasktracker.task-list key=label_filter.
    Returns 200 PreferenceRecord on success, or ApiError on failure.
    """
    with _preference_client() as client:
        resp = client.put(
            "/api/preferences/tasktracker.task-list/label_filter",
            json={"value": body.label_ids},
        )
    return JSONResponse(status_code=resp.status_code, content=resp.json())


@router.get("/{task_id}/labels", response_model=None)
def get_task_labels(task_id: str) -> JSONResponse:
    """Return labels attached to a task via LabelEngine; returns Dataset."""
    with _label_client() as client:
        resp = client.get(f"/api/objects/{task_id}/labels")
    if resp.status_code != 200:
        return JSONResponse(status_code=resp.status_code, content=resp.json())
    items = resp.json().get("labels", [])
    return dataset_response(Dataset(
        meta=DatasetMeta(
            object_type="task_label",
            label="Task Labels",
            total=len(items),
            page=1,
            page_size=len(items),
            row_actions=["delete"],
        ),
        **{"schema": [
            ColumnSchema(key="id",          label="ID",       type="string"),
            ColumnSchema(key="name",        label="Name",     type="string"),
            ColumnSchema(key="attached_at", label="Attached", type="date"),
        ]},
        rows=[
            {"id": lbl["label_id"], "name": lbl["label_name"], "attached_at": lbl["attached_at"]}
            for lbl in items
        ],
    ))


@router.post("/{task_id}/labels", response_model=None)
def attach_task_label(task_id: str, body: LabelAttachBody) -> JSONResponse:
    """Proxy: attach a label to a task."""
    with _label_client() as client:
        resp = client.post(
            f"/api/objects/{task_id}/labels",
            json={"label_name": body.label_name, "object_type": "task"},
        )
    return JSONResponse(status_code=resp.status_code, content=resp.json())


@router.delete("/{task_id}/labels/{label_id}", response_model=None)
def detach_task_label(task_id: str, label_id: str) -> Response:
    """Proxy: detach a label from a task."""
    with _label_client() as client:
        resp = client.delete(f"/api/objects/{task_id}/labels/{label_id}")
    if resp.status_code == 204:
        return Response(status_code=204)
    return JSONResponse(status_code=resp.status_code, content=resp.json())


class LabelSetBody(BaseModel):
    labels: list[str]


@router.put("/{task_id}/labels", response_model=None)
def set_task_labels(task_id: str, body: LabelSetBody) -> JSONResponse:
    """Atomically replace all labels on a task with the provided list.

    Fetches current labels, detaches each, then attaches the new set.
    Returns the updated label list in the same shape as GET /{task_id}/labels.
    """
    with _label_client() as client:
        # 1. Fetch current labels
        resp = client.get(f"/api/objects/{task_id}/labels")
        if resp.status_code != 200:
            return JSONResponse(status_code=resp.status_code, content=resp.json())
        current_labels: list[dict] = resp.json().get("labels", [])

        # 2. Detach each existing label
        for lbl in current_labels:
            label_id = lbl.get("label_id") or lbl.get("id")
            if label_id:
                client.delete(f"/api/objects/{task_id}/labels/{label_id}")

        # 3. Attach each new label by name
        for raw_name in body.labels:
            name = raw_name.strip()
            if name:
                client.post(
                    f"/api/objects/{task_id}/labels",
                    json={"label_name": name, "object_type": "task"},
                )

        # 4. Return updated label list
        resp = client.get(f"/api/objects/{task_id}/labels")

    return JSONResponse(status_code=resp.status_code, content=resp.json())
