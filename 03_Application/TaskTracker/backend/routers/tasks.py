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

# ── LabelEngine client ────────────────────────────────────────────────────────

LABEL_ENGINE_URL = os.environ.get("LABEL_ENGINE_URL", "http://localhost:8050")

def _label_client() -> httpx.Client:
    return httpx.Client(base_url=LABEL_ENGINE_URL, timeout=5.0)

router = APIRouter(prefix="/tasks", tags=["tasks"])

# ── Column schema — stable; matches tasktracker_schema.sql ───────────────────

TASK_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="title",        label="Title",       type="string", sortable=True,  filterable=False),
    ColumnSchema(key="status",       label="Status",      type="enum",   sortable=True,  filterable=True),
    ColumnSchema(key="priority",     label="Priority",    type="enum",   sortable=True,  filterable=True),
    ColumnSchema(key="due_date",     label="Due Date",    type="date",   sortable=True,  filterable=False),
    ColumnSchema(key="effort_hours", label="Effort (h)",  type="number", sortable=True,  filterable=False),
    ColumnSchema(key="created_at",   label="Created",     type="date",   sortable=True,  filterable=False),
    ColumnSchema(key="description",  label="Description", type="string", sortable=False, filterable=False, detail_visible=True),
]

VALID_STATUS   = {"open", "in_progress", "pending", "done"}
VALID_PRIORITY = {"low", "medium", "high"}

# ── Request bodies ─────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    title:        str
    description:  str | None = None
    status:       str = "open"
    priority:     str = "medium"
    due_date:     str | None = None
    effort_hours: float | None = None


class TaskUpdate(BaseModel):
    title:        str | None = None
    description:  str | None = None
    status:       str | None = None
    priority:     str | None = None
    due_date:     str | None = None
    effort_hours: float | None = None


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

VALID_VIEW = {"active", "pending_board"}


@router.get("", response_model=None)
def list_tasks(
    status:    str | None = None,
    view:      str | None = None,
    page:      int = 1,
    page_size: int = 25,
) -> JSONResponse:
    if status and status not in VALID_STATUS:
        return api_error("INVALID_FILTER", f"status must be one of: {', '.join(sorted(VALID_STATUS))}")
    if view and view not in VALID_VIEW:
        return api_error("INVALID_FILTER", f"view must be one of: {', '.join(sorted(VALID_VIEW))}")
    if page < 1:
        return api_error("INVALID_PARAM", "page must be ≥ 1")

    offset = (page - 1) * page_size

    with get_db() as conn:
        with conn.cursor() as cur:
            if view == "active":
                # Active view: open + in_progress, plus done tasks updated today
                cur.execute(
                    """
                    select count(*) from tasktracker.tasks
                    where status in ('open', 'in_progress')
                       or (status = 'done' and updated_at::date >= current_date)
                    """,
                )
                total = cur.fetchone()["count"]
                cur.execute(
                    """
                    select id, title, description, status, priority, due_date,
                           effort_hours, created_at, updated_at
                    from tasktracker.tasks
                    where status in ('open', 'in_progress')
                       or (status = 'done' and updated_at::date >= current_date)
                    order by created_at desc
                    limit %s offset %s
                    """,
                    (page_size, offset),
                )
            elif view == "pending_board":
                # Pending board: open + pending tasks
                cur.execute(
                    "select count(*) from tasktracker.tasks where status in ('open', 'pending')",
                )
                total = cur.fetchone()["count"]
                cur.execute(
                    """
                    select id, title, description, status, priority, due_date,
                           effort_hours, created_at, updated_at
                    from tasktracker.tasks
                    where status in ('open', 'pending')
                    order by created_at desc
                    limit %s offset %s
                    """,
                    (page_size, offset),
                )
            elif status == "done":
                # Done view: sorted by last modified descending
                cur.execute(
                    "select count(*) from tasktracker.tasks where status = 'done'",
                )
                total = cur.fetchone()["count"]
                cur.execute(
                    """
                    select id, title, description, status, priority, due_date,
                           effort_hours, created_at, updated_at
                    from tasktracker.tasks
                    where status = 'done'
                    order by updated_at desc
                    limit %s offset %s
                    """,
                    (page_size, offset),
                )
            elif status:
                cur.execute(
                    "select count(*) from tasktracker.tasks where status = %s",
                    (status,),
                )
                total = cur.fetchone()["count"]
                cur.execute(
                    """
                    select id, title, description, status, priority, due_date,
                           effort_hours, created_at, updated_at
                    from tasktracker.tasks
                    where status = %s
                    order by created_at desc
                    limit %s offset %s
                    """,
                    (status, page_size, offset),
                )
            else:
                cur.execute("select count(*) from tasktracker.tasks")
                total = cur.fetchone()["count"]
                cur.execute(
                    """
                    select id, title, description, status, priority, due_date,
                           effort_hours, created_at, updated_at
                    from tasktracker.tasks
                    order by created_at desc
                    limit %s offset %s
                    """,
                    (page_size, offset),
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
    if body.status not in {"open", "pending"}:
        return api_error("VALIDATION_ERROR", "status must be one of: open, pending")
    if body.priority not in VALID_PRIORITY:
        return api_error("VALIDATION_ERROR", f"priority must be one of: {', '.join(sorted(VALID_PRIORITY))}")
    if body.effort_hours is not None and body.effort_hours < 0:
        return api_error("VALIDATION_ERROR", "effort_hours must be >= 0")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into tasktracker.tasks (id, title, description, status, priority, due_date, effort_hours)
                values (%s, %s, %s, %s, %s, %s, %s)
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

    fields: dict[str, Any] = {}
    if body.title       is not None: fields["title"]       = body.title.strip() or None
    if body.description is not None: fields["description"] = body.description or None
    if body.status      is not None: fields["status"]      = body.status
    if body.priority    is not None: fields["priority"]    = body.priority
    if body.due_date    is not None: fields["due_date"]    = body.due_date or None
    # Use model_fields_set to distinguish "not sent" (skip) from "explicitly null" (clear column)
    if "effort_hours" in body.model_fields_set: fields["effort_hours"] = body.effort_hours

    if not fields:
        return api_error("VALIDATION_ERROR", "no fields provided to update")

    set_parts = [f"{k} = %s" for k in fields] + ["updated_at = now()"]
    set_clause = ", ".join(set_parts)
    values = list(fields.values()) + [task_id]

    with get_db() as conn:
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
