import json as _json
from typing import Any, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.database import get_db
from backend.purchasing import build_shopping_list
from backend.routers import movements as _movements
from backend.routers.items import berlin_today
from platform_errorhandling import api_error
from platform_contracts import ColumnSchema, Dataset, DatasetMeta

router = APIRouter(tags=["shopping_tasks"])

# ── Valid enum values ─────────────────────────────────────────────────────────

VALID_TASK_STATUSES = {"open", "done", "dismissed"}
VALID_CLOSE_STATUSES = {"done", "dismissed"}

# ── Column schemas ────────────────────────────────────────────────────────────

TASK_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="id",           label="ID",          type="string", sortable=False, filterable=False),
    ColumnSchema(key="item_id",      label="Item ID",     type="number", sortable=False, filterable=False),
    ColumnSchema(key="item_name",    label="Item",        type="string", sortable=True,  filterable=False),
    ColumnSchema(key="status",       label="Status",      type="enum",   sortable=True,  filterable=True),
    ColumnSchema(key="source_tags",  label="Source Tags", type="string", sortable=False, filterable=False),
    ColumnSchema(key="notes",        label="Notes",       type="string", sortable=False, filterable=False),
    ColumnSchema(key="created_at",   label="Created",     type="date",   sortable=True,  filterable=False),
    ColumnSchema(key="completed_at", label="Completed",   type="date",   sortable=True,  filterable=False),
]

BY_SOURCE_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="id",           label="ID",          type="string", sortable=False, filterable=False),
    ColumnSchema(key="item_id",      label="Item ID",     type="number", sortable=False, filterable=False),
    ColumnSchema(key="item_name",    label="Item",        type="string", sortable=True,  filterable=False),
    ColumnSchema(key="status",       label="Status",      type="enum",   sortable=False, filterable=False),
    ColumnSchema(key="source_tags",  label="Source Tags", type="string", sortable=False, filterable=False),
    ColumnSchema(key="notes",        label="Notes",       type="string", sortable=False, filterable=False),
    ColumnSchema(key="created_at",   label="Created",     type="date",   sortable=True,  filterable=False),
    ColumnSchema(key="completed_at", label="Completed",   type="date",   sortable=False, filterable=False),
    ColumnSchema(key="source_tag",   label="Group",       type="string", sortable=True,  filterable=True),
]

CENTRAL_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="item_id",       label="Article",     type="number", sortable=False, filterable=False),
    ColumnSchema(key="item_name",     label="Item",        type="string", sortable=True,  filterable=False),
    ColumnSchema(key="category",      label="Category",    type="enum",   sortable=True,  filterable=True),
    ColumnSchema(key="unit",          label="Unit",        type="string", sortable=False, filterable=False),
    ColumnSchema(key="stock",         label="On hand",     type="number", sortable=False, filterable=False),
    ColumnSchema(key="usable_stock",  label="Usable",      type="number", sortable=False, filterable=False),
    ColumnSchema(key="demand_qty",    label="Needed",      type="number", sortable=False, filterable=False),
    ColumnSchema(key="shortage",      label="Short",       type="number", sortable=False, filterable=False),
    ColumnSchema(key="purchase_qty",  label="Buy",         type="number", sortable=False, filterable=False),
    ColumnSchema(key="needed_by",     label="Needed by",   type="date",   sortable=True,  filterable=False),
    ColumnSchema(key="origins",       label="Origin",      type="string", sortable=False, filterable=False),
    ColumnSchema(key="source_tags",   label="Buy at",      type="string", sortable=False, filterable=False),
    ColumnSchema(key="task_id",       label="Task",        type="string", sortable=False, filterable=False),
    ColumnSchema(key="notes",         label="Notes",       type="string", sortable=False, filterable=False),
]

DEMAND_STATUS_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="source",        label="Source",     type="string", sortable=False, filterable=False),
    ColumnSchema(key="line_count",    label="Lines",      type="number", sortable=False, filterable=False),
    ColumnSchema(key="last_ok_at",    label="Last sync",  type="date",   sortable=False, filterable=False),
    ColumnSchema(key="last_error",    label="Last error", type="string", sortable=False, filterable=False),
    ColumnSchema(key="last_error_at", label="Error at",   type="date",   sortable=False, filterable=False),
]

# ── Request models ────────────────────────────────────────────────────────────

class ShoppingTaskCreate(BaseModel):
    item_id: int
    notes:   Optional[str] = None


class PurchaseIn(BaseModel):
    item_id:         int
    qty:             float
    idempotency_key: Optional[str] = None


class ShoppingTaskUpdate(BaseModel):
    status: str
    notes:  Optional[str] = None

# ── Helpers ───────────────────────────────────────────────────────────────────

def _task_row_to_dict(row: Any) -> dict[str, Any]:
    d = dict(row)
    d["id"]      = str(d["id"])
    if d.get("created_at"):
        d["created_at"] = d["created_at"].isoformat()
    if d.get("completed_at"):
        d["completed_at"] = d["completed_at"].isoformat()
    else:
        d["completed_at"] = None
    if d.get("source_tags") is None:
        d["source_tags"] = []
    return d


def _tasks_dataset(rows: list[dict], schema: list[ColumnSchema] | None = None) -> Dataset:
    return Dataset(
        meta=DatasetMeta(
            object_type="shopping_task",
            label="Shopping Tasks",
            total=len(rows),
            page=1,
            page_size=max(len(rows), 1),
            row_actions=["done", "dismiss", "delete"],
        ),
        **{"schema": schema or TASK_SCHEMA},
        rows=rows,
    )


def _single_task_dataset(row: dict) -> Dataset:
    return Dataset(
        meta=DatasetMeta(
            object_type="shopping_task",
            label="Shopping Task",
            total=1,
            page=1,
            page_size=1,
            row_actions=["done", "dismiss", "delete"],
        ),
        **{"schema": TASK_SCHEMA},
        rows=[row],
    )


def _empty_task_dataset() -> Dataset:
    return Dataset(
        meta=DatasetMeta(
            object_type="shopping_task",
            label="Shopping Tasks",
            total=0,
            page=1,
            page_size=0,
            row_actions=[],
        ),
        **{"schema": TASK_SCHEMA},
        rows=[],
    )


def _dataset_response(dataset: Dataset) -> JSONResponse:
    return JSONResponse(content=dataset.model_dump(by_alias=True, mode="json"))


def _record_item_history(
    conn: Any,
    item_id: int,
    change_type: str,
    old_value: str | None,
    new_value: str | None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into storagetracker.item_history
                (item_id, change_type, old_value, new_value)
            values (%s, %s, %s, %s)
            """,
            (item_id, change_type, old_value, new_value),
        )


# ── IMPORTANT: View routes MUST be registered before parameterised routes ─────

@router.get("/shopping-tasks/views/by_source", response_model=None)
def view_by_source() -> JSONResponse:
    """
    Open tasks expanded by source_tag.
    One row per (task, source_tag). Tasks with no source_tags produce one row
    with source_tag='Other'. Tasks with multiple tags appear in each group.
    Ordered: source_tag ASC with 'Other' last, then created_at ASC within group.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select t.id, t.item_id, i.name as item_name, t.status,
                       t.source_tags, t.notes, t.created_at, t.completed_at
                from storagetracker.shopping_tasks t
                join storagetracker.items i on i.id = t.item_id
                where t.status = 'open'
                order by t.created_at asc
                """,
            )
            task_rows = cur.fetchall()

    # Expand each task into one row per source_tag (or 'Other' if empty)
    expanded: list[dict] = []
    for raw in task_rows:
        base = _task_row_to_dict(raw)
        tags: list[str] = base.get("source_tags") or []
        if not tags:
            row = dict(base)
            row["source_tag"] = "Other"
            expanded.append(row)
        else:
            for tag in tags:
                row = dict(base)
                row["source_tag"] = tag
                expanded.append(row)

    # Sort: 'Other' last, then alphabetically by source_tag, then created_at ASC within group
    expanded.sort(key=lambda r: (
        1 if r["source_tag"] == "Other" else 0,
        r["source_tag"],
        r["created_at"],
    ))

    return _dataset_response(_tasks_dataset(expanded, schema=BY_SOURCE_SCHEMA))


@router.get("/shopping-tasks/views/central", response_model=None)
def view_central() -> JSONResponse:
    """
    THE shopping list. One row per article that is short or has an open task (manual / low-stock).
    Demand from all sources is netted against usable stock ONCE per article (backend/purchasing.py), and the shortage
    is rounded up to the article's pack size / minimum order. Ordering: needed_by ascending (undated last), then name.
    Empty result: rows = [].
    """
    with get_db() as conn:
        rows = build_shopping_list(conn, berlin_today())
    return _dataset_response(Dataset(
        meta=DatasetMeta(object_type="shopping_list_item", label="Shopping list", total=len(rows), page=1,
                         page_size=max(len(rows), 1), row_actions=["bought", "done", "dismiss"]),
        **{"schema": CENTRAL_SCHEMA}, rows=rows))


@router.get("/shopping-tasks/views/demand_status", response_model=None)
def view_demand_status() -> JSONResponse:
    """Per demand source: last accepted snapshot and last rejected attempt (shown above the shopping list)."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select source, line_count, last_ok_at, last_error, last_error_at "
                        "from storagetracker.demand_sync order by source")
            rows = []
            for r in cur.fetchall():
                d = dict(r)
                for k in ("last_ok_at", "last_error_at"):
                    d[k] = d[k].isoformat() if d.get(k) else None
                # an error only matters while it is newer than the last accepted snapshot
                if d["last_error"] and d["last_ok_at"] and d["last_error_at"] and d["last_error_at"] <= d["last_ok_at"]:
                    d["last_error"] = None
                rows.append(d)
    return _dataset_response(Dataset(
        meta=DatasetMeta(object_type="demand_sync", label="Demand sync", total=len(rows), page=1,
                         page_size=max(len(rows), 1), row_actions=[]),
        **{"schema": DEMAND_STATUS_SCHEMA}, rows=rows))


# ── Standard CRUD ─────────────────────────────────────────────────────────────

@router.get("/shopping-tasks", response_model=None)
def list_shopping_tasks(
    status:     str = "open",
    source_tag: Optional[str] = None,
) -> JSONResponse:
    if status not in VALID_TASK_STATUSES:
        return api_error("INVALID_FILTER", f"status must be one of: {', '.join(sorted(VALID_TASK_STATUSES))}", status=400)

    conditions: list[str] = ["t.status = %s"]
    params: list[Any] = [status]

    if source_tag:
        conditions.append("t.source_tags @> %s::jsonb")
        params.append(f'["{source_tag}"]')

    where = "where " + " and ".join(conditions)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select t.id, t.item_id, i.name as item_name, t.status,
                       t.source_tags, t.notes, t.created_at, t.completed_at
                from storagetracker.shopping_tasks t
                join storagetracker.items i on i.id = t.item_id
                {where}
                order by t.created_at asc
                """,
                params,
            )
            rows = [_task_row_to_dict(r) for r in cur.fetchall()]

    return _dataset_response(_tasks_dataset(rows))


@router.post("/shopping-tasks", response_model=None)
def create_shopping_task(body: ShoppingTaskCreate) -> JSONResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            # Confirm item exists and fetch source_tags
            cur.execute(
                "select id, source_tags from storagetracker.items where id = %s",
                (body.item_id,),
            )
            item = cur.fetchone()
            if not item:
                return api_error("NOT_FOUND", f"Item {body.item_id} not found", status=404)

            source_tags = item["source_tags"] or []

            # Check for existing open task
            cur.execute(
                "select id from storagetracker.shopping_tasks where item_id = %s and status = 'open'",
                (body.item_id,),
            )
            if cur.fetchone():
                return api_error(
                    "CONFLICT",
                    f"An open shopping task already exists for item {body.item_id}",
                    status=409,
                )

            # Insert task
            cur.execute(
                """
                insert into storagetracker.shopping_tasks (item_id, source_tags, notes)
                values (%s, %s::jsonb, %s)
                returning id, item_id, status, source_tags, notes, created_at, completed_at
                """,
                (body.item_id, _json.dumps(source_tags), body.notes),
            )
            task = _task_row_to_dict(cur.fetchone())

        # Fetch item name for the response row
        with conn.cursor() as cur:
            cur.execute("select name from storagetracker.items where id = %s", (body.item_id,))
            task["item_name"] = cur.fetchone()["name"]

        conn.commit()

    return JSONResponse(
        status_code=201,
        content=_single_task_dataset(task).model_dump(by_alias=True, mode="json"),
    )


@router.post("/shopping-tasks/purchase", response_model=None)
def purchase(body: PurchaseIn) -> JSONResponse:
    """
    "Bought": book the received quantity as ONE `purchase` stock movement (idempotent via idempotency_key) and close the
    article's open task WITHOUT the restock reset (the movement already added the stock; resetting would double-book).
    Demand-driven rows need nothing else: the shortage recalculates from the new stock, so the row disappears (or shrinks)
    by itself. A low-stock article that is still below its minimum afterwards gets a fresh task from the normal transition.
    KANBAN articles have no quantity: use the task's Done instead.
    """
    if body.qty <= 0:
        return api_error("VALIDATION_ERROR", "qty must be > 0")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select stock_management_type from storagetracker.items where id = %s", (body.item_id,))
            item = cur.fetchone()
            if not item:
                return api_error("NOT_FOUND", f"Item {body.item_id} not found", status=404)
            if item["stock_management_type"] == "KANBAN":
                return api_error("CONFLICT", "Kanban articles have no quantity: mark the task Done instead", status=409)
            cur.execute("update storagetracker.shopping_tasks set status = 'done', completed_at = now() "
                        "where item_id = %s and status = 'open'", (body.item_id,))
        try:
            movement, info, replayed = _movements._apply(
                conn, body.item_id, body.qty, "purchase", "shopping-list", body.idempotency_key, None)
        except ValueError as e:
            return api_error("CONFLICT", str(e), status=409)
        conn.commit()
    return JSONResponse(status_code=200, content={"item_id": body.item_id, "quantity": info["quantity"],
                                                  "movement_id": movement["id"], "replayed": replayed})


@router.patch("/shopping-tasks/{task_id}", response_model=None)
def update_shopping_task(task_id: str, body: ShoppingTaskUpdate) -> JSONResponse:
    if body.status not in VALID_CLOSE_STATUSES:
        return api_error(
            "VALIDATION_ERROR",
            f"status must be one of: {', '.join(sorted(VALID_CLOSE_STATUSES))}",
            status=400,
        )

    with get_db() as conn:
        # Fetch task
        with conn.cursor() as cur:
            cur.execute(
                "select id, item_id, status from storagetracker.shopping_tasks where id = %s",
                (task_id,),
            )
            task = cur.fetchone()
            if not task:
                return api_error("NOT_FOUND", f"Shopping task {task_id} not found", status=404)
            if task["status"] != "open":
                return api_error(
                    "VALIDATION_ERROR",
                    f"Task is already {task['status']} and cannot be updated",
                    status=400,
                )

        item_id = task["item_id"]

        # Update task status and completed_at
        notes_update = ""
        notes_params: list[Any] = []
        if body.notes is not None:
            notes_update = ", notes = %s"
            notes_params = [body.notes]

        with conn.cursor() as cur:
            cur.execute(
                f"""
                update storagetracker.shopping_tasks
                set status = %s, completed_at = now(){notes_update}
                where id = %s
                returning id, item_id, status, source_tags, notes, created_at, completed_at
                """,
                [body.status] + notes_params + [task_id],
            )
            updated_task = _task_row_to_dict(cur.fetchone())

        # If done: apply restock logic to the item
        if body.status == "done":
            with conn.cursor() as cur:
                cur.execute(
                    "select id, state, quantity, min_quantity, restock_quantity, stock_management_type from storagetracker.items where id = %s",
                    (item_id,),
                )
                item = dict(cur.fetchone())

            old_state = item["state"]

            if item["restock_quantity"] is not None and item["stock_management_type"] == "QUANTITY":
                # Set quantity to restock_quantity and re-evaluate state
                new_qty = item["restock_quantity"]
                min_qty = item["min_quantity"]

                if min_qty is not None and new_qty <= min_qty:
                    new_state = "low_stock"
                else:
                    new_state = "stored"

                with conn.cursor() as cur:
                    cur.execute(
                        "update storagetracker.items set quantity = %s, state = %s, updated_at = now() where id = %s",
                        (new_qty, new_state, item_id),
                    )
            else:
                # No restock_quantity (or KANBAN: status only, no quantity): just set state to stored
                new_state = "stored"
                with conn.cursor() as cur:
                    cur.execute(
                        "update storagetracker.items set state = %s, updated_at = now() where id = %s",
                        (new_state, item_id),
                    )

            # Record history if state changed
            if old_state != new_state:
                _record_item_history(conn, item_id, "state_change", old_state, new_state)

        # Fetch item_name for response
        with conn.cursor() as cur:
            cur.execute("select name from storagetracker.items where id = %s", (item_id,))
            updated_task["item_name"] = cur.fetchone()["name"]

        conn.commit()

    return _dataset_response(_single_task_dataset(updated_task))


@router.delete("/shopping-tasks/{task_id}", response_model=None)
def delete_shopping_task(task_id: str) -> JSONResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "delete from storagetracker.shopping_tasks where id = %s returning id",
                (task_id,),
            )
            deleted = cur.fetchone()
            if not deleted:
                return api_error("NOT_FOUND", f"Shopping task {task_id} not found", status=404)
        conn.commit()

    return _dataset_response(_empty_task_dataset())
