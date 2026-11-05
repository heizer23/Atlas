"""
Category + priority configuration.

  GET   /categories        -> Dataset of categories; sibling field `priorities` (level/label/description)
  POST  /categories        -> create {name, kind?}
  PATCH /categories/{id}   -> partial update {name?, kind?, display_order?}
  PATCH /priorities/{level} -> edit label/description (levels themselves are fixed 1..3)

Category progress itself lives in tracking.py (`/today`, `/category-progress`).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.database import get_db
from platform_contracts import ColumnSchema, Dataset, DatasetMeta
from platform_errorhandling import api_error

router = APIRouter(prefix="/habittracker", tags=["habittracker"])

KINDS = ("achievement", "discipline")

CATEGORY_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="name",          label="Name",  type="string", sortable=True),
    ColumnSchema(key="kind",          label="Kind",  type="string"),
    ColumnSchema(key="display_order", label="Order", type="number", sortable=True),
]


class CategoryCreate(BaseModel):
    name: str | None = None
    kind: str | None = None


class CategoryUpdate(BaseModel):
    name: str | None = None
    kind: str | None = None
    display_order: int | None = None


class PriorityUpdate(BaseModel):
    label: str | None = None
    description: str | None = None


def _cat(row: Any) -> dict[str, Any]:
    d = dict(row)
    d["id"] = str(d["id"])
    d["created_at"] = d["created_at"].isoformat()
    return d


@router.get("/categories", response_model=None)
def list_categories() -> JSONResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select * from habittracker.habit_categories order by display_order, name")
            rows = [_cat(r) for r in cur.fetchall()]
            cur.execute("select level, label, description from habittracker.habit_priorities order by level")
            priorities = [dict(r) for r in cur.fetchall()]
    dataset = Dataset(
        meta=DatasetMeta(object_type="habit_category", label="Categories", total=len(rows), page=1,
                         page_size=max(len(rows), 1), row_actions=[]),
        **{"schema": CATEGORY_SCHEMA},
        rows=rows,
    )
    return JSONResponse({**dataset.model_dump(by_alias=True, mode="json"), "priorities": priorities})


@router.post("/categories", response_model=None)
def create_category(body: CategoryCreate) -> JSONResponse:
    if not body.name or not body.name.strip():
        return api_error("VALIDATION_ERROR", "name is required", status=400)
    kind = body.kind or "achievement"
    if kind not in KINDS:
        return api_error("VALIDATION_ERROR", f"kind must be one of {', '.join(KINDS)}", status=400)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select 1 from habittracker.habit_categories where name = %s", (body.name.strip(),))
            if cur.fetchone():
                return api_error("VALIDATION_ERROR", "a category with this name already exists", status=400)
            cur.execute(
                """
                insert into habittracker.habit_categories (name, kind, display_order)
                values (%s, %s, coalesce((select max(display_order) from habittracker.habit_categories), -1) + 1)
                returning *
                """,
                (body.name.strip(), kind),
            )
            row = cur.fetchone()
        conn.commit()
    return JSONResponse(status_code=201, content=_cat(row))


@router.patch("/categories/{category_id}", response_model=None)
def update_category(category_id: str, body: CategoryUpdate) -> JSONResponse:
    fields = body.model_fields_set
    updates: dict[str, Any] = {}
    if "name" in fields:
        if not body.name or not body.name.strip():
            return api_error("VALIDATION_ERROR", "name cannot be cleared", status=400)
        updates["name"] = body.name.strip()
    if "kind" in fields:
        if body.kind not in KINDS:
            return api_error("VALIDATION_ERROR", f"kind must be one of {', '.join(KINDS)}", status=400)
        updates["kind"] = body.kind
    if "display_order" in fields:
        if body.display_order is None:
            return api_error("VALIDATION_ERROR", "display_order cannot be cleared", status=400)
        updates["display_order"] = body.display_order
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select * from habittracker.habit_categories where id = %s", (category_id,))
            row = cur.fetchone()
            if not row:
                return api_error("NOT_FOUND", f"Category {category_id} not found", status=404)
            if "name" in updates:
                cur.execute("select 1 from habittracker.habit_categories where name = %s and id <> %s",
                            (updates["name"], category_id))
                if cur.fetchone():
                    return api_error("VALIDATION_ERROR", "a category with this name already exists", status=400)
            if updates:
                sets = ", ".join(f"{k} = %s" for k in updates)
                cur.execute(f"update habittracker.habit_categories set {sets} where id = %s returning *",
                            list(updates.values()) + [category_id])
                row = cur.fetchone()
        conn.commit()
    return JSONResponse(_cat(row))


@router.patch("/priorities/{level}", response_model=None)
def update_priority(level: int, body: PriorityUpdate) -> JSONResponse:
    fields = body.model_fields_set
    updates: dict[str, Any] = {}
    if "label" in fields:
        if not body.label or not body.label.strip():
            return api_error("VALIDATION_ERROR", "label cannot be cleared", status=400)
        updates["label"] = body.label.strip()
    if "description" in fields:
        updates["description"] = (body.description or "").strip() or None
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select 1 from habittracker.habit_priorities where level = %s", (level,))
            if not cur.fetchone():
                return api_error("NOT_FOUND", f"Priority level {level} not found", status=404)
            if updates:
                sets = ", ".join(f"{k} = %s" for k in updates)
                cur.execute(f"update habittracker.habit_priorities set {sets} where level = %s", list(updates.values()) + [level])
            cur.execute("select level, label, description from habittracker.habit_priorities where level = %s", (level,))
            row = dict(cur.fetchone())
        conn.commit()
    return JSONResponse(row)
