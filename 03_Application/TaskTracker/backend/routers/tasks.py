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

VALID_STATUS   = {"open", "in_progress", "done"}
VALID_PRIORITY = {"low", "medium", "high"}

# ── Request bodies ─────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    title:        str
    description:  str | None = None
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


def fetch_labels_for_tasks(conn: Any, task_ids: list[str]) -> dict[str, list[dict[str, str]]]:
    """Return a mapping of task_id -> [{id, name}, ...] ordered by attached_at ASC."""
    if not task_ids:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            """
            select ol.object_id, l.id as label_id, l.name as label_name
            from labels.object_labels ol
            join labels.labels l on l.id = ol.label_id
            where ol.object_id = any(%s)
              and ol.object_type = 'task'
            order by ol.object_id, ol.attached_at, ol.label_id
            """,
            (task_ids,),
        )
        rows = cur.fetchall()
    result: dict[str, list[dict[str, str]]] = {}
    for r in rows:
        tid = r["object_id"]
        if tid not in result:
            result[tid] = []
        result[tid].append({"id": r["label_id"], "name": r["label_name"]})
    return result


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

@router.get("", response_model=None)
def list_tasks(
    status:    str | None = None,
    page:      int = 1,
    page_size: int = 25,
) -> JSONResponse:
    if status and status not in VALID_STATUS:
        return api_error("INVALID_FILTER", f"status must be one of: {', '.join(sorted(VALID_STATUS))}")
    if page < 1:
        return api_error("INVALID_PARAM", "page must be ≥ 1")

    offset = (page - 1) * page_size

    with get_db() as conn:
        with conn.cursor() as cur:
            if status:
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
        labels_by_task = fetch_labels_for_tasks(conn, task_ids)
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
    if body.priority not in VALID_PRIORITY:
        return api_error("VALIDATION_ERROR", f"priority must be one of: {', '.join(sorted(VALID_PRIORITY))}")
    if body.effort_hours is not None and body.effort_hours < 0:
        return api_error("VALIDATION_ERROR", "effort_hours must be >= 0")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into tasktracker.tasks (id, title, description, priority, due_date, effort_hours)
                values (%s, %s, %s, %s, %s, %s)
                returning *
                """,
                (
                    str(uuid.uuid4()),
                    body.title.strip(),
                    body.description or None,
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
    """Proxy: search labels by prefix via LabelEngine."""
    with _label_client() as client:
        resp = client.get("/api/labels", params={"q": q})
    return JSONResponse(status_code=resp.status_code, content=resp.json())


@router.get("/{task_id}/labels", response_model=None)
def get_task_labels(task_id: str) -> JSONResponse:
    """Proxy: return labels attached to a task."""
    with _label_client() as client:
        resp = client.get(f"/api/objects/{task_id}/labels")
    return JSONResponse(status_code=resp.status_code, content=resp.json())


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
