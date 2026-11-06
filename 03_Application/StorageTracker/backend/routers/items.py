import json as _json
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.database import get_db
from platform_errorhandling import api_error
from platform_contracts import ColumnSchema, Dataset, DatasetMeta

router = APIRouter(prefix="/items", tags=["items"])

# ── Valid enum values ─────────────────────────────────────────────────────────

VALID_STATES = {
    "stored", "low_stock", "out_of_stock",
    "marked_for_recycling", "missing", "lent_out",
}
VALID_ITEM_TYPES = {"consumable", "object", "pending_action"}
VALID_KINDS = {"ingredient", "batch"}
VALID_STOCK_TYPES = {"QUANTITY", "KANBAN"}
VALID_CATEGORIES = [
    "Vegetables & Fruit", "Meat & Fish", "Dairy", "Dry Goods", "Spices", "Frozen", "Beverages", "Other",
]

# Expiry (R-CON-AL-06 time authority: server clock, Europe/Berlin calendar day).
# expires_at is the last day the item is still fine: expired = expires_at < today,
# expiring_soon = expires_at <= today + EXPIRY_SOON_DAYS. Derived on read, never stored; only for quantity > 0.
BERLIN = ZoneInfo("Europe/Berlin")
EXPIRY_SOON_DAYS = 2


def berlin_today() -> date:
    return datetime.now(BERLIN).date()


# States that trigger auto shopping task creation
SHOPPING_TRIGGER_STATES = {"low_stock", "out_of_stock"}

# ── Column schemas ────────────────────────────────────────────────────────────

ITEM_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="name",             label="Name",            type="string", sortable=True,  filterable=True),
    ColumnSchema(key="item_type",        label="Type",            type="enum",   sortable=True,  filterable=True),
    ColumnSchema(key="state",            label="State",           type="enum",   sortable=True,  filterable=True),
    ColumnSchema(key="location",         label="Location",        type="string", sortable=True,  filterable=False),
    ColumnSchema(key="quantity",         label="Qty",             type="number", sortable=True,  filterable=False),
    ColumnSchema(key="min_quantity",     label="Min Qty",         type="number", sortable=False, filterable=False),
    ColumnSchema(key="restock_quantity", label="Restock Qty",     type="number", sortable=False, filterable=False),
    ColumnSchema(key="unit",             label="Unit",            type="string", sortable=False, filterable=False),
    ColumnSchema(key="expires_at",       label="Expires",         type="date",   sortable=True,  filterable=False),
    ColumnSchema(key="kind",             label="Kind",            type="enum",   sortable=True,  filterable=True),
    ColumnSchema(key="produced_at",      label="Produced",        type="date",   sortable=True,  filterable=False),
    ColumnSchema(key="archived_at",      label="Archived",        type="date",   sortable=True,  filterable=False),
    ColumnSchema(key="expiry_status",    label="Expiry",          type="enum",   sortable=False, filterable=False),
    ColumnSchema(key="stock_management_type", label="Stock Mgmt",  type="enum",   sortable=True,  filterable=True),
    ColumnSchema(key="category",         label="Category",        type="enum",   sortable=True,  filterable=True),
    ColumnSchema(key="recipe_ref",       label="Recipe Ref",      type="string", sortable=False, filterable=False),
    ColumnSchema(key="source_tags",      label="Source Tags",     type="string", sortable=False, filterable=False),
    ColumnSchema(key="notes",            label="Notes",           type="string", sortable=False, filterable=False, detail_visible=True),
    ColumnSchema(key="created_at",       label="Created",         type="date",   sortable=True,  filterable=False),
    ColumnSchema(key="updated_at",       label="Updated",         type="date",   sortable=True,  filterable=False),
]

HISTORY_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="timestamp",   label="When",      type="date",   sortable=True,  filterable=False),
    ColumnSchema(key="change_type", label="Change",    type="enum",   sortable=False, filterable=False),
    ColumnSchema(key="old_value",   label="Old Value", type="string", sortable=False, filterable=False),
    ColumnSchema(key="new_value",   label="New Value", type="string", sortable=False, filterable=False),
    ColumnSchema(key="notes",       label="Notes",     type="string", sortable=False, filterable=False),
]

# ── Request models ────────────────────────────────────────────────────────────

class ItemCreate(BaseModel):
    name:             str
    item_type:        str
    state:            str = "stored"
    location:         str | None = None
    notes:            str | None = None
    source_tags:      list[str] = []
    quantity:         float | None = None
    min_quantity:     int | None = None
    restock_quantity: int | None = None
    unit:             str | None = None
    expires_at:       date | None = None
    kind:             str = "ingredient"
    recipe_ref:       str | None = None
    produced_at:      date | None = None
    stock_management_type: str = "QUANTITY"
    category:         str = "Other"


class ItemUpdate(BaseModel):
    name:             str | None = None
    state:            str | None = None
    location:         str | None = None
    quantity:         float | None = None
    min_quantity:     int | None = None
    restock_quantity: int | None = None
    unit:             str | None = None
    expires_at:       date | None = None
    recipe_ref:       str | None = None
    produced_at:      date | None = None
    stock_management_type: str | None = None
    category:         str | None = None
    notes:            str | None = None
    source_tags:      list[str] | None = None

# ── Helpers ───────────────────────────────────────────────────────────────────

def _expiry_status(expires_at: date | None, quantity: Any) -> str | None:
    if expires_at is None or not quantity or float(quantity) <= 0:
        return None
    today = berlin_today()
    if expires_at < today:
        return "expired"
    if expires_at <= today + timedelta(days=EXPIRY_SOON_DAYS):
        return "expiring_soon"
    return None


def _num(v: Decimal | float | int) -> int | float:
    """Render integral numerics as int so existing integer clients see no change."""
    f = float(v)
    return int(f) if f.is_integer() else f


def _row_to_dict(row: Any) -> dict[str, Any]:
    d = dict(row)
    if isinstance(d.get("quantity"), Decimal):
        d["quantity"] = _num(d["quantity"])
    d["expiry_status"] = _expiry_status(d.get("expires_at"), d.get("quantity"))
    if d.get("expires_at"):
        d["expires_at"] = d["expires_at"].isoformat()
    if d.get("produced_at"):
        d["produced_at"] = d["produced_at"].isoformat()
    if d.get("archived_at"):
        d["archived_at"] = d["archived_at"].isoformat()
    if d.get("created_at"):
        d["created_at"] = d["created_at"].isoformat()
    if d.get("updated_at"):
        d["updated_at"] = d["updated_at"].isoformat()
    # source_tags comes back as a list already from psycopg2 jsonb
    if d.get("source_tags") is None:
        d["source_tags"] = []
    return d


def _history_row_to_dict(row: Any) -> dict[str, Any]:
    d = dict(row)
    d["id"] = str(d["id"])
    if d.get("timestamp"):
        d["timestamp"] = d["timestamp"].isoformat()
    return d


def _apply_auto_transition(
    quantity: Any,
    min_quantity: int | None,
) -> str | None:
    """Return 'low_stock' if auto-transition applies, else None."""
    if quantity is not None and min_quantity is not None and quantity <= min_quantity:
        return "low_stock"
    return None


def _record_history(
    conn: Any,
    item_id: int,
    change_type: str,
    old_value: str | None,
    new_value: str | None,
    notes: str | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into storagetracker.item_history
                (item_id, change_type, old_value, new_value, notes)
            values (%s, %s, %s, %s, %s)
            """,
            (item_id, change_type, old_value, new_value, notes),
        )


def _ensure_open_shopping_task(
    conn: Any,
    item_id: int,
    source_tags: list[str],
) -> None:
    """
    Create an open shopping task for item_id if none exists.
    Called synchronously within the item write transaction.
    """
    with conn.cursor() as cur:
        cur.execute(
            "select id from storagetracker.shopping_tasks where item_id = %s and status = 'open'",
            (item_id,),
        )
        if cur.fetchone() is None:
            cur.execute(
                """
                insert into storagetracker.shopping_tasks (item_id, source_tags)
                values (%s, %s::jsonb)
                """,
                (item_id, _json.dumps(source_tags)),
            )


def _dataset_response(dataset: Dataset) -> JSONResponse:
    return JSONResponse(content=dataset.model_dump(by_alias=True, mode="json"))


def _items_dataset(rows: list[dict], total: int, page: int = 1, page_size: int = 25) -> Dataset:
    return Dataset(
        meta=DatasetMeta(
            object_type="item",
            label="Items",
            total=total,
            page=page,
            page_size=page_size,
            row_actions=["edit", "delete"],
        ),
        **{"schema": ITEM_SCHEMA},
        rows=rows,
    )


def _single_item_dataset(row: dict) -> Dataset:
    return Dataset(
        meta=DatasetMeta(
            object_type="item",
            label="Item",
            total=1,
            page=1,
            page_size=1,
            row_actions=["edit", "delete"],
        ),
        **{"schema": ITEM_SCHEMA},
        rows=[row],
    )


def _history_dataset(rows: list[dict], total: int) -> Dataset:
    return Dataset(
        meta=DatasetMeta(
            object_type="item_history",
            label="History",
            total=total,
            page=1,
            page_size=total,
            row_actions=[],
        ),
        **{"schema": HISTORY_SCHEMA},
        rows=rows,
    )


def _empty_dataset() -> Dataset:
    return Dataset(
        meta=DatasetMeta(
            object_type="item",
            label="Items",
            total=0,
            page=1,
            page_size=0,
            row_actions=[],
        ),
        **{"schema": ITEM_SCHEMA},
        rows=[],
    )


# ── IMPORTANT: View routes MUST be registered before parameterised routes ─────
# FastAPI matches routes in registration order. /items/views/* would otherwise
# match {id} = "views".

@router.get("/views/low_stock", response_model=None)
def view_low_stock() -> JSONResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, name, item_type, state, location, notes, source_tags,
                       quantity, min_quantity, restock_quantity, unit, expires_at, kind, recipe_ref,
                       produced_at, archived_at, stock_management_type, category, created_at, updated_at
                from storagetracker.items
                where state in ('low_stock', 'out_of_stock') and archived_at is null
                order by name asc
                """,
            )
            rows = [_row_to_dict(r) for r in cur.fetchall()]
    return _dataset_response(_items_dataset(rows, total=len(rows)))


@router.get("/views/recycling", response_model=None)
def view_recycling() -> JSONResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, name, item_type, state, location, notes, source_tags,
                       quantity, min_quantity, restock_quantity, unit, expires_at, kind, recipe_ref,
                       produced_at, archived_at, stock_management_type, category, created_at, updated_at
                from storagetracker.items
                where state = 'marked_for_recycling' and archived_at is null
                order by name asc
                """,
            )
            rows = [_row_to_dict(r) for r in cur.fetchall()]
    return _dataset_response(_items_dataset(rows, total=len(rows)))


@router.get("/views/expiring", response_model=None)
def view_expiring() -> JSONResponse:
    """Items with stock whose expires_at is in the past or within EXPIRY_SOON_DAYS; earliest first."""
    limit = berlin_today() + timedelta(days=EXPIRY_SOON_DAYS)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, name, item_type, state, location, notes, source_tags,
                       quantity, min_quantity, restock_quantity, unit, expires_at, kind, recipe_ref,
                       produced_at, archived_at, stock_management_type, category, created_at, updated_at
                from storagetracker.items
                where expires_at is not null and expires_at <= %s and quantity > 0 and archived_at is null
                order by expires_at asc, name asc
                """,
                (limit,),
            )
            rows = [_row_to_dict(r) for r in cur.fetchall()]
    return _dataset_response(_items_dataset(rows, total=len(rows)))


@router.get("/views/important", response_model=None)
def view_important() -> JSONResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, name, item_type, state, location, notes, source_tags,
                       quantity, min_quantity, restock_quantity, unit, expires_at, kind, recipe_ref,
                       produced_at, archived_at, stock_management_type, category, created_at, updated_at
                from storagetracker.items
                where item_type = 'object' and archived_at is null
                order by name asc
                """,
            )
            rows = [_row_to_dict(r) for r in cur.fetchall()]
    return _dataset_response(_items_dataset(rows, total=len(rows)))


@router.get("/views/search", response_model=None)
def view_search(q: str = "") -> JSONResponse:
    if not q or not q.strip():
        return _dataset_response(_empty_dataset())
    pattern = f"%{q.lower()}%"
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, name, item_type, state, location, notes, source_tags,
                       quantity, min_quantity, restock_quantity, unit, expires_at, kind, recipe_ref,
                       produced_at, archived_at, stock_management_type, category, created_at, updated_at
                from storagetracker.items
                where archived_at is null
                  and (lower(name)     like %s
                   or lower(location) like %s
                   or lower(notes)    like %s)
                order by name asc
                """,
                (pattern, pattern, pattern),
            )
            rows = [_row_to_dict(r) for r in cur.fetchall()]
    return _dataset_response(_items_dataset(rows, total=len(rows)))


# ── Standard CRUD ─────────────────────────────────────────────────────────────

@router.get("", response_model=None)
def list_items(
    state:      str | None = None,
    item_type:  str | None = None,
    location:   str | None = None,
    source_tag: str | None = None,
    kind:       str | None = None,
    category:   str | None = None,
    stock_management_type: str | None = None,
    archived:   str = "exclude",
) -> JSONResponse:
    """archived: exclude (default, active inventory) | include | only. Archived = depleted batches kept for history."""
    if archived not in ("exclude", "include", "only"):
        return api_error("INVALID_FILTER", "archived must be one of: exclude, include, only")
    if state and state not in VALID_STATES:
        return api_error("INVALID_FILTER", f"state must be one of: {', '.join(sorted(VALID_STATES))}")
    if item_type and item_type not in VALID_ITEM_TYPES:
        return api_error("INVALID_FILTER", f"item_type must be one of: {', '.join(sorted(VALID_ITEM_TYPES))}")

    conditions: list[str] = []
    params: list[Any] = []

    if state:
        conditions.append("state = %s")
        params.append(state)
    if item_type:
        conditions.append("item_type = %s")
        params.append(item_type)
    if location:
        conditions.append("location = %s")
        params.append(location)
    if kind:
        if kind not in VALID_KINDS:
            return api_error("INVALID_FILTER", f"kind must be one of: {', '.join(sorted(VALID_KINDS))}")
        conditions.append("kind = %s")
        params.append(kind)
    if category:
        if category not in VALID_CATEGORIES:
            return api_error("INVALID_FILTER", f"category must be one of: {', '.join(VALID_CATEGORIES)}")
        conditions.append("category = %s")
        params.append(category)
    if stock_management_type:
        if stock_management_type not in VALID_STOCK_TYPES:
            return api_error("INVALID_FILTER", f"stock_management_type must be one of: {', '.join(sorted(VALID_STOCK_TYPES))}")
        conditions.append("stock_management_type = %s")
        params.append(stock_management_type)
    if source_tag:
        conditions.append("source_tags @> %s::jsonb")
        params.append(f'["{source_tag}"]')
    if archived == "exclude":
        conditions.append("archived_at is null")
    elif archived == "only":
        conditions.append("archived_at is not null")

    where = ("where " + " and ".join(conditions)) if conditions else ""

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"select count(*) from storagetracker.items {where}", params)
            total = cur.fetchone()["count"]
            cur.execute(
                f"""
                select id, name, item_type, state, location, notes, source_tags,
                       quantity, min_quantity, restock_quantity, unit, expires_at, kind, recipe_ref,
                       produced_at, archived_at, stock_management_type, category, created_at, updated_at
                from storagetracker.items {where}
                order by created_at desc
                """,
                params,
            )
            rows = [_row_to_dict(r) for r in cur.fetchall()]

    return _dataset_response(_items_dataset(rows, total=total))


@router.post("", response_model=None)
def create_item(body: ItemCreate) -> JSONResponse:
    # Validate
    if not body.name or not body.name.strip():
        return api_error("VALIDATION_ERROR", "name must not be empty")
    if body.item_type not in VALID_ITEM_TYPES:
        return api_error("VALIDATION_ERROR", f"item_type must be one of: {', '.join(sorted(VALID_ITEM_TYPES))}")
    if body.state not in VALID_STATES:
        return api_error("VALIDATION_ERROR", f"state must be one of: {', '.join(sorted(VALID_STATES))}")
    if body.kind not in VALID_KINDS:
        return api_error("VALIDATION_ERROR", f"kind must be one of: {', '.join(sorted(VALID_KINDS))}")
    if body.stock_management_type not in VALID_STOCK_TYPES:
        return api_error("VALIDATION_ERROR", f"stock_management_type must be one of: {', '.join(sorted(VALID_STOCK_TYPES))}")
    if body.category not in VALID_CATEGORIES:
        return api_error("VALIDATION_ERROR", f"category must be one of: {', '.join(VALID_CATEGORIES)}")
    if body.stock_management_type == "KANBAN" and body.kind == "batch":
        return api_error("VALIDATION_ERROR", "batches cannot use KANBAN stock management")
    if body.quantity is not None and body.quantity < 0:
        return api_error("VALIDATION_ERROR", "quantity must be >= 0")
    if body.min_quantity is not None and body.min_quantity < 0:
        return api_error("VALIDATION_ERROR", "min_quantity must be >= 0")
    if body.restock_quantity is not None and body.restock_quantity < 0:
        return api_error("VALIDATION_ERROR", "restock_quantity must be >= 0")

    # Auto-transition: only apply if caller left state at default 'stored'. KANBAN status is manual only.
    state = body.state
    auto = (_apply_auto_transition(body.quantity, body.min_quantity)
            if body.kind != "batch" and body.stock_management_type == "QUANTITY" else None)
    if auto and state == "stored":
        state = auto

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into storagetracker.items
                    (name, item_type, state, location, notes, source_tags,
                     quantity, min_quantity, restock_quantity,
                     unit, expires_at, kind, recipe_ref, produced_at, stock_management_type, category)
                values (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                returning id, name, item_type, state, location, notes, source_tags,
                          quantity, min_quantity, restock_quantity, unit, expires_at, kind, recipe_ref,
                          produced_at, archived_at, stock_management_type, category, created_at, updated_at
                """,
                (
                    body.name.strip(),
                    body.item_type,
                    state,
                    body.location,
                    body.notes,
                    _json.dumps(body.source_tags),
                    body.quantity,
                    body.min_quantity,
                    body.restock_quantity,
                    body.unit,
                    body.expires_at,
                    body.kind,
                    body.recipe_ref,
                    body.produced_at,
                    body.stock_management_type,
                    body.category,
                ),
            )
            row = _row_to_dict(cur.fetchone())
            item_id = row["id"]
            _record_history(conn, item_id, "created", None, state)

        # Auto-create shopping task if item is low/out of stock
        if state in SHOPPING_TRIGGER_STATES and body.kind != "batch":
            _ensure_open_shopping_task(conn, item_id, row["source_tags"])

        conn.commit()

    return _dataset_response(_single_item_dataset(row))


@router.get("/{item_id}", response_model=None)
def get_item(item_id: int) -> JSONResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, name, item_type, state, location, notes, source_tags,
                       quantity, min_quantity, restock_quantity, unit, expires_at, kind, recipe_ref,
                       produced_at, archived_at, stock_management_type, category, created_at, updated_at
                from storagetracker.items where id = %s
                """,
                (item_id,),
            )
            item_row = cur.fetchone()
            if not item_row:
                return api_error("NOT_FOUND", f"Item {item_id} not found", status=404)
            row = _row_to_dict(item_row)

            # Fetch last 20 history entries
            cur.execute(
                """
                select id, item_id, timestamp, change_type, old_value, new_value, notes
                from storagetracker.item_history
                where item_id = %s
                order by timestamp desc
                limit 20
                """,
                (item_id,),
            )
            history = [_history_row_to_dict(h) for h in cur.fetchall()]
            row["history"] = history

    return _dataset_response(_single_item_dataset(row))


@router.patch("/{item_id}", response_model=None)
def update_item(item_id: int, body: ItemUpdate) -> JSONResponse:
    set_fields = body.model_fields_set

    if not set_fields:
        return api_error("VALIDATION_ERROR", "No fields provided for update")

    # Validate provided values
    if "name" in set_fields and body.name is not None and not body.name.strip():
        return api_error("VALIDATION_ERROR", "name must not be empty")
    if "state" in set_fields and body.state is not None and body.state not in VALID_STATES:
        return api_error("VALIDATION_ERROR", f"state must be one of: {', '.join(sorted(VALID_STATES))}")
    if "quantity" in set_fields and body.quantity is not None and body.quantity < 0:
        return api_error("VALIDATION_ERROR", "quantity must be >= 0")
    if "min_quantity" in set_fields and body.min_quantity is not None and body.min_quantity < 0:
        return api_error("VALIDATION_ERROR", "min_quantity must be >= 0")
    if "restock_quantity" in set_fields and body.restock_quantity is not None and body.restock_quantity < 0:
        return api_error("VALIDATION_ERROR", "restock_quantity must be >= 0")
    if "stock_management_type" in set_fields and body.stock_management_type not in VALID_STOCK_TYPES:
        return api_error("VALIDATION_ERROR", f"stock_management_type must be one of: {', '.join(sorted(VALID_STOCK_TYPES))}")
    if "category" in set_fields and body.category not in VALID_CATEGORIES:
        return api_error("VALIDATION_ERROR", f"category must be one of: {', '.join(VALID_CATEGORIES)}")
    if "source_tags" in set_fields and body.source_tags is None:
        return api_error("VALIDATION_ERROR", "source_tags cannot be null — use empty list [] to clear")

    with get_db() as conn:
        # Fetch current row for history comparisons
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, name, item_type, state, location, notes, source_tags,
                       quantity, min_quantity, restock_quantity, unit, expires_at, kind, recipe_ref,
                       produced_at, archived_at, stock_management_type, category, created_at, updated_at
                from storagetracker.items where id = %s
                """,
                (item_id,),
            )
            current = cur.fetchone()
            if not current:
                return api_error("NOT_FOUND", f"Item {item_id} not found", status=404)
            current = dict(current)

        if current["kind"] == "batch" and body.stock_management_type == "KANBAN":
            return api_error("VALIDATION_ERROR", "batches cannot use KANBAN stock management")

        # Build SET clause
        assignments: list[str] = ["updated_at = now()"]
        params: list[Any] = []

        for field in set_fields:
            val = getattr(body, field)
            if field == "source_tags":
                assignments.append("source_tags = %s::jsonb")
                params.append(_json.dumps(val))
            elif field == "name" and val is not None:
                assignments.append(f"{field} = %s")
                params.append(val.strip())
            else:
                assignments.append(f"{field} = %s")
                params.append(val)

        params.append(item_id)
        set_clause = ", ".join(assignments)

        with conn.cursor() as cur:
            cur.execute(
                f"""
                update storagetracker.items
                set {set_clause}
                where id = %s
                returning id, name, item_type, state, location, notes, source_tags,
                          quantity, min_quantity, restock_quantity, unit, expires_at, kind, recipe_ref,
                          produced_at, archived_at, stock_management_type, category, created_at, updated_at
                """,
                params,
            )
            updated = cur.fetchone()
            if not updated:
                return api_error("NOT_FOUND", f"Item {item_id} not found", status=404)
            updated = dict(updated)

        # Auto-transition: apply if quantity or min_quantity changed AND caller did not set state
        caller_set_state = "state" in set_fields
        if (not caller_set_state and current["kind"] != "batch" and updated["stock_management_type"] == "QUANTITY"
                and ("quantity" in set_fields or "min_quantity" in set_fields)):
            auto = _apply_auto_transition(updated["quantity"], updated["min_quantity"])
            if auto:
                with conn.cursor() as cur:
                    cur.execute(
                        "update storagetracker.items set state = %s, updated_at = now() where id = %s returning state",
                        (auto, item_id),
                    )
                    updated["state"] = cur.fetchone()["state"]

        # Determine final state for shopping task logic
        final_state = updated["state"]

        # Record history entries
        if "state" in set_fields or (not caller_set_state and final_state != current["state"]):
            old_s = str(current["state"]) if current["state"] is not None else None
            new_s = str(final_state) if final_state is not None else None
            if old_s != new_s:
                _record_history(conn, item_id, "state_change", old_s, new_s)

        if "location" in set_fields:
            old_l = str(current["location"]) if current["location"] is not None else None
            new_l = str(body.location) if body.location is not None else None
            if old_l != new_l:
                _record_history(conn, item_id, "location_change", old_l, new_l)

        if "quantity" in set_fields:
            old_q = str(_num(current["quantity"])) if current["quantity"] is not None else None
            new_q = str(_num(body.quantity)) if body.quantity is not None else None
            if old_q != new_q:
                _record_history(conn, item_id, "quantity_change", old_q, new_q)
                # keep ledger sum == quantity: absolute PATCH is a correction movement
                with conn.cursor() as cur:
                    delta = (body.quantity or 0) - float(current["quantity"] or 0)
                    if delta:
                        cur.execute(
                            """
                            insert into storagetracker.stock_movements
                                (item_id, delta, requested_delta, reason)
                            values (%s, %s, %s, 'patch')
                            """,
                            (item_id, delta, delta),
                        )

        # Auto-create shopping task if final state is low/out of stock
        if final_state in SHOPPING_TRIGGER_STATES and current["kind"] != "batch":
            source_tags = updated.get("source_tags") or []
            if isinstance(source_tags, str):
                import json as _json2
                source_tags = _json2.loads(source_tags)
            _ensure_open_shopping_task(conn, item_id, source_tags)

        conn.commit()

    return _dataset_response(_single_item_dataset(_row_to_dict(updated)))


@router.delete("/{item_id}", response_model=None)
def delete_item(item_id: int) -> JSONResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "delete from storagetracker.items where id = %s returning id",
                (item_id,),
            )
            deleted = cur.fetchone()
            if not deleted:
                return api_error("NOT_FOUND", f"Item {item_id} not found", status=404)
        conn.commit()

    return _dataset_response(_empty_dataset())


@router.get("/{item_id}/history", response_model=None)
def get_item_history(item_id: int) -> JSONResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            # Confirm item exists
            cur.execute("select id from storagetracker.items where id = %s", (item_id,))
            if not cur.fetchone():
                return api_error("NOT_FOUND", f"Item {item_id} not found", status=404)

            cur.execute(
                """
                select id, item_id, timestamp, change_type, old_value, new_value, notes
                from storagetracker.item_history
                where item_id = %s
                order by timestamp desc
                """,
                (item_id,),
            )
            rows = [_history_row_to_dict(r) for r in cur.fetchall()]

    return _dataset_response(_history_dataset(rows, total=len(rows)))
