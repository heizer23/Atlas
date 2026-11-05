"""
Habit definition endpoints: list, create, partial update, reorder.

Route -> internal_flow step mapping (10_architecture.json):
  GET  /habits          -> step 2 list_habits
  POST /habits          -> step 3 create_habit
  PATCH /habits/{id}    -> step 4 update_habit
  POST /habits/reorder  -> step 5 reorder_habits

/habits/reorder is declared before the dynamic PATCH /habits/{habit_id}
route per 10_scaffolding.json's route_registration_note (no actual method
collision today, but keeps a future POST /habits/{id}-shaped route safe).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from backend.database import get_db
from platform_errorhandling import api_error
from platform_contracts import ColumnSchema, Dataset, DatasetMeta

router = APIRouter(prefix="/habittracker", tags=["habittracker"])

HABIT_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="name",            label="Name",           type="string", sortable=True,  filterable=True),
    ColumnSchema(key="description",     label="Description",    type="string", sortable=False, filterable=True),
    ColumnSchema(key="default_checked", label="Default",        type="boolean"),
    ColumnSchema(key="kind",            label="Kind",           type="string"),
    ColumnSchema(key="unit",            label="Unit",           type="string"),
    ColumnSchema(key="increment",       label="Increment",      type="number"),
    ColumnSchema(key="category_id",     label="Category",       type="string", filterable=True),
    ColumnSchema(key="priority",        label="Priority",       type="number", sortable=True, filterable=True),
    ColumnSchema(key="display_order",   label="Order",          type="number", sortable=True),
    ColumnSchema(key="active_from",     label="Active From",    type="date",   sortable=True),
    ColumnSchema(key="end_date",        label="Archived (end)", type="date",   sortable=True),
    ColumnSchema(key="created_at",      label="Created",        type="date"),
    ColumnSchema(key="updated_at",      label="Updated",        type="date"),
]

# ── Request models ───────────────────────────────────────────────────────────
# Fields that must be rejectable-as-explicit-null (R-CON-AL-04) are declared
# Optional with no default meaning "valid value absent" — model_fields_set
# (not a plain `is not None` check) is what distinguishes omitted from
# explicit null in update_habit below.


class HabitCreate(BaseModel):
    name:            str | None = None
    description:     str | None = None
    default_checked: bool | None = None
    active_from:     str | None = None
    kind:            str | None = None
    unit:            str | None = None
    increment:       int | None = None
    category_id:     str | None = None
    priority:        int | None = None


class HabitUpdate(BaseModel):
    name:            str | None = None
    description:     str | None = None
    default_checked: bool | None = None
    active_from:     str | None = None
    end_date:        str | None = None
    kind:            str | None = None
    unit:            str | None = None
    increment:       int | None = None
    category_id:     str | None = None
    priority:        int | None = None


class ReorderBody(BaseModel):
    habit_ids: list[str] = []

# ── Helpers ───────────────────────────────────────────────────────────────────


def _parse_date_value(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Stringify uuid/date fields for JSON serialization, StorageTracker
    _row_to_dict convention."""
    d = dict(row)
    d["id"] = str(d["id"])
    if d.get("category_id") is not None:
        d["category_id"] = str(d["category_id"])
    if d.get("active_from") is not None:
        d["active_from"] = d["active_from"].isoformat()
    if d.get("end_date") is not None:
        d["end_date"] = d["end_date"].isoformat()
    if d.get("created_at") is not None:
        d["created_at"] = d["created_at"].isoformat()
    if d.get("updated_at") is not None:
        d["updated_at"] = d["updated_at"].isoformat()
    return d


def _check_category_priority(cur, category_id: str | None, priority: int | None) -> str | None:
    """Return an error message if the (non-null) category / priority does not exist."""
    if category_id is not None:
        try:
            cur.execute("select 1 from habittracker.habit_categories where id = %s", (category_id,))
        except Exception:
            cur.connection.rollback()
            return "category_id must be a valid category id"
        if not cur.fetchone():
            return "category_id does not exist"
    if priority is not None:
        cur.execute("select 1 from habittracker.habit_priorities where level = %s", (priority,))
        if not cur.fetchone():
            return "priority must be an existing priority level"
    return None


def _dataset_response(dataset: Dataset, status: int = 200) -> JSONResponse:
    return JSONResponse(status_code=status, content=dataset.model_dump(by_alias=True, mode="json"))

# ── GET /habits ──────────────────────────────────────────────────────────────


@router.get("/habits", response_model=None)
def list_habits() -> JSONResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select * from habittracker.habits order by display_order asc")
            rows = [_row_to_dict(r) for r in cur.fetchall()]

    dataset = Dataset(
        meta=DatasetMeta(object_type="habit", label="Habits", total=len(rows), page=1, page_size=max(len(rows), 1), row_actions=[]),
        **{"schema": HABIT_SCHEMA},
        rows=rows,
    )
    return _dataset_response(dataset)

# ── POST /habits ─────────────────────────────────────────────────────────────


@router.post("/habits", response_model=None)
def create_habit(body: HabitCreate) -> JSONResponse:
    if not body.name or not body.name.strip():
        return api_error("VALIDATION_ERROR", "name is required", status=400)

    if not body.active_from:
        return api_error("VALIDATION_ERROR", "active_from is required", status=400)
    active_from = _parse_date_value(body.active_from)
    if active_from is None:
        return api_error("VALIDATION_ERROR", "active_from must be a valid YYYY-MM-DD date", status=400)

    kind = body.kind or "binary"
    if kind not in ("binary", "quantity"):
        return api_error("VALIDATION_ERROR", "kind must be 'binary' or 'quantity'", status=400)
    increment = 1 if body.increment is None else body.increment
    if increment < 1:
        return api_error("VALIDATION_ERROR", "increment must be at least 1", status=400)
    unit = (body.unit or "").strip() or None

    with get_db() as conn:
        with conn.cursor() as cur:
            problem = _check_category_priority(cur, body.category_id, body.priority)
            if problem:
                return api_error("VALIDATION_ERROR", problem, status=400)
            cur.execute(
                """
                insert into habittracker.habits
                    (name, description, default_checked, display_order, active_from, kind, unit, increment,
                     category_id, priority)
                values (
                    %s, %s, %s,
                    coalesce((select max(display_order) from habittracker.habits), -1) + 1,
                    %s, %s, %s, %s, %s, %s
                )
                returning *
                """,
                (body.name, body.description, bool(body.default_checked), active_from,
                 kind, unit if kind == "quantity" else None, increment if kind == "quantity" else 1,
                 body.category_id, body.priority),
            )
            row = cur.fetchone()
        conn.commit()

    return JSONResponse(status_code=201, content=_row_to_dict(row))

# ── POST /habits/reorder (declared before the dynamic PATCH route) ──────────


@router.post("/habits/reorder", response_model=None)
def reorder_habits(body: ReorderBody) -> JSONResponse:
    habit_ids = body.habit_ids

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select id from habittracker.habits")
            existing_ids = {str(r["id"]) for r in cur.fetchall()}

        if len(habit_ids) != len(set(habit_ids)) or set(habit_ids) != existing_ids:
            return api_error(
                "VALIDATION_ERROR",
                "habit_ids must exactly match the current set of existing habit ids, with no duplicates",
                status=400,
            )

        with conn.cursor() as cur:
            # DEFERRABLE constraint handling: defer the uniqueness check to
            # commit time so a full permutation (including swaps) never
            # trips it mid-statement. 10_architecture.json internal_flow
            # step 5 / 10_schema.sql uq_habits_display_order.
            cur.execute("set constraints habittracker.uq_habits_display_order deferred")
            values_clause = ", ".join("(%s::uuid, %s)" for _ in habit_ids)
            params: list[Any] = []
            for index, habit_id in enumerate(habit_ids):
                params.extend([habit_id, index])
            cur.execute(
                f"""
                update habittracker.habits as h
                set display_order = v.ord, updated_at = now()
                from (values {values_clause}) as v(id, ord)
                where h.id = v.id
                """,
                params,
            )
        conn.commit()

    return Response(status_code=200)

# ── PATCH /habits/{habit_id} ──────────────────────────────────────────────────


@router.patch("/habits/{habit_id}", response_model=None)
def update_habit(habit_id: str, body: HabitUpdate) -> JSONResponse:
    fields_set = body.model_fields_set

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select * from habittracker.habits where id = %s", (habit_id,))
            existing = cur.fetchone()
        if not existing:
            return api_error("NOT_FOUND", f"Habit {habit_id} not found", status=404)

        updates: dict[str, Any] = {}

        if "name" in fields_set:
            if not body.name or not body.name.strip():
                return api_error("VALIDATION_ERROR", "name cannot be cleared", status=400)
            updates["name"] = body.name

        if "description" in fields_set:
            # Explicit null clears it; a string sets it (R-CON-AL-04).
            updates["description"] = body.description

        if "default_checked" in fields_set:
            if body.default_checked is None:
                return api_error("VALIDATION_ERROR", "default_checked cannot be cleared", status=400)
            updates["default_checked"] = body.default_checked

        if "active_from" in fields_set:
            if body.active_from is None:
                return api_error("VALIDATION_ERROR", "active_from cannot be cleared", status=400)
            parsed = _parse_date_value(body.active_from)
            if parsed is None:
                return api_error("VALIDATION_ERROR", "active_from must be a valid YYYY-MM-DD date", status=400)
            updates["active_from"] = parsed

        if "end_date" in fields_set:
            if body.end_date is None:
                # Explicit null un-archives.
                updates["end_date"] = None
            else:
                parsed = _parse_date_value(body.end_date)
                if parsed is None:
                    return api_error("VALIDATION_ERROR", "end_date must be a valid YYYY-MM-DD date", status=400)
                updates["end_date"] = parsed

        if "kind" in fields_set:
            if body.kind not in ("binary", "quantity"):
                return api_error("VALIDATION_ERROR", "kind must be 'binary' or 'quantity'", status=400)
            updates["kind"] = body.kind

        if "unit" in fields_set:
            updates["unit"] = (body.unit or "").strip() or None

        if "increment" in fields_set:
            if body.increment is None or body.increment < 1:
                return api_error("VALIDATION_ERROR", "increment must be at least 1", status=400)
            updates["increment"] = body.increment

        # Explicit null clears category / priority (legacy "uncategorised"); omitted leaves it.
        if "category_id" in fields_set:
            updates["category_id"] = body.category_id
        if "priority" in fields_set:
            updates["priority"] = body.priority
        if "category_id" in updates or "priority" in updates:
            with conn.cursor() as cur:
                problem = _check_category_priority(cur, updates.get("category_id"), updates.get("priority"))
            if problem:
                return api_error("VALIDATION_ERROR", problem, status=400)

        effective_active_from = updates.get("active_from", existing["active_from"])
        effective_end_date = updates["end_date"] if "end_date" in updates else existing["end_date"]
        if effective_end_date is not None and effective_end_date < effective_active_from:
            return api_error("VALIDATION_ERROR", "end_date must be on or after active_from", status=400)

        if not updates:
            row = existing
        else:
            set_clauses = ", ".join(f"{key} = %s" for key in updates)
            params = list(updates.values()) + [habit_id]
            with conn.cursor() as cur:
                cur.execute(
                    f"update habittracker.habits set {set_clauses}, updated_at = now() where id = %s returning *",
                    params,
                )
                row = cur.fetchone()
            conn.commit()

    return JSONResponse(status_code=200, content=_row_to_dict(row))
