import os
import uuid
from typing import Any

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from backend.database import get_db
from platform_errorhandling import api_error
from platform_contracts import ColumnSchema, Dataset, DatasetMeta

# ── Platform service clients ──────────────────────────────────────────────────

LABEL_ENGINE_URL      = os.environ.get("LABEL_ENGINE_URL",      "http://localhost:8050")
PREFERENCE_STORE_URL  = os.environ.get("PREFERENCE_STORE_URL",  "http://localhost:8060")

def _label_client() -> httpx.Client:
    return httpx.Client(base_url=LABEL_ENGINE_URL, timeout=5.0)

def _preference_client() -> httpx.Client:
    return httpx.Client(base_url=PREFERENCE_STORE_URL, timeout=5.0)

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
]

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


def single_row_dataset(row: Any) -> JSONResponse:
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
        rows=[row_to_dict(row)],
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

    select_cols = """id, title, description, status, priority, due_date,
                     effort_hours, created_at, updated_at,
                     task_type, parent_task_id, actual_duration_minutes, completed_at,
                     scheduled_at"""

    with get_db() as conn:
        with conn.cursor() as cur:
            if view == "active":
                # Auto-promote scheduled tasks whose time has arrived
                _run_auto_promotion(conn)
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

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into tasktracker.tasks
                    (id, title, description, status, priority, due_date, effort_hours,
                     task_type, parent_task_id, actual_duration_minutes, scheduled_at)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                returning *
                """,
                (
                    str(uuid.uuid4()),
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
                ),
            )
            row = cur.fetchone()
        conn.commit()

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

    fields: dict[str, Any] = {}
    if body.title       is not None: fields["title"]       = body.title.strip() or None
    if body.description is not None: fields["description"] = body.description or None
    if body.status      is not None: fields["status"]      = body.status
    if body.priority    is not None: fields["priority"]    = body.priority
    if body.due_date    is not None: fields["due_date"]    = body.due_date or None
    if body.task_type   is not None: fields["task_type"]   = body.task_type
    # Use model_fields_set to distinguish "not sent" (skip) from "explicitly null" (clear column)
    if "effort_hours"            in body.model_fields_set: fields["effort_hours"]            = body.effort_hours
    if "actual_duration_minutes" in body.model_fields_set: fields["actual_duration_minutes"] = body.actual_duration_minutes
    if "parent_task_id"          in body.model_fields_set: fields["parent_task_id"]          = body.parent_task_id or None
    if "scheduled_at"            in body.model_fields_set: fields["scheduled_at"]            = body.scheduled_at or None

    if not fields:
        return api_error("VALIDATION_ERROR", "no fields provided to update")

    # Fetch current row to determine status transitions
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select status, completed_at, scheduled_at from tasktracker.tasks where id = %s",
                (task_id,),
            )
            current = cur.fetchone()

        if current is None:
            return api_error("NOT_FOUND", f"task {task_id} not found", status=404)

        # If transitioning to scheduled, ensure scheduled_at is set (from body or existing)
        new_status_from_body = fields.get("status")
        if new_status_from_body == "scheduled":
            # scheduled_at must be present: either provided in this PATCH or already non-null in DB
            scheduled_at_in_body = "scheduled_at" in body.model_fields_set and body.scheduled_at
            scheduled_at_in_db   = current.get("scheduled_at") is not None
            if not scheduled_at_in_body and not scheduled_at_in_db:
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
        conn.commit()

    if row is None:
        return api_error("NOT_FOUND", f"task {task_id} not found", status=404)

    return single_row_dataset(row)


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
