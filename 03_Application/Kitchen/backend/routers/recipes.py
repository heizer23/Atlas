from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend import ingredients as ing_mod
from backend import storage_client as st
from backend.common import dataset_response
from backend.database import get_db
from backend.recipes_repo import annotate_lines, load_recipe, recompute_status, save_ingredients
from platform_errorhandling import api_error

router = APIRouter(prefix="/kitchen", tags=["recipes"])

KINDS = {"base", "derived", "favorite"}


class IngredientIn(BaseModel):
    name:           str
    qty:            float = Field(gt=0)
    unit:           str
    base_recipe_id: str | None = None
    item_id:        str | None = None   # StorageTracker article id; null = unresolved (recipe stays draft)


class RecipeIn(BaseModel):
    name:             str
    kind:             str
    servings:         float = Field(default=1, gt=0)
    description:      str | None = None
    prep_minutes:     int | None = Field(default=None, ge=0)
    cook_minutes:     int | None = Field(default=None, ge=0)
    steps:            str = ""
    shelf_life_days:  int | None = None
    storage_location: str | None = None
    ingredients:      list[IngredientIn] = []


class RecipePatch(BaseModel):
    name:             str | None = None
    kind:             str | None = None
    servings:         float | None = Field(default=None, gt=0)
    description:      str | None = None
    prep_minutes:     int | None = Field(default=None, ge=0)
    cook_minutes:     int | None = Field(default=None, ge=0)
    steps:            str | None = None
    shelf_life_days:  int | None = None
    storage_location: str | None = None
    ingredients:      list[IngredientIn] | None = None


def _validate(kind: str | None, name: str | None, ingredients: list[IngredientIn] | None) -> JSONResponse | None:
    if kind is not None and kind not in KINDS:
        return api_error("VALIDATION_ERROR", f"kind must be one of: {', '.join(sorted(KINDS))}")
    if name is not None and not name.strip():
        return api_error("VALIDATION_ERROR", "name must not be empty")
    for ing in ingredients or []:
        if not ing.name.strip() or not ing.unit.strip():
            return api_error("VALIDATION_ERROR", "ingredient name and unit must not be empty")
    return None


def _check_items(ingredients: list[IngredientIn] | None) -> tuple[dict[str, Any], JSONResponse | None]:
    """Load the article master and reject ids that do not exist. Unit mismatches are kept (recipe stays draft)."""
    try:
        master = ing_mod.master_by_id()
    except st.StorageError as e:
        return {}, api_error("STORAGE_UNAVAILABLE", str(e), status=502)
    for ing in ingredients or []:
        if ing.item_id and not ing.base_recipe_id and ing.item_id not in master:
            return master, api_error("VALIDATION_ERROR", f"Unknown article id {ing.item_id} ({ing.name})")
    return master, None


def _list_row(r: dict[str, Any]) -> dict[str, Any]:
    return {k: r[k] for k in ("id", "name", "kind", "status", "servings", "yield_unit", "shelf_life_days")}


@router.get("/recipes", response_model=None)
def list_recipes(kind: str | None = None) -> JSONResponse:
    if kind and kind not in KINDS:
        return api_error("INVALID_FILTER", f"kind must be one of: {', '.join(sorted(KINDS))}")
    with get_db() as conn, conn.cursor() as cur:
        if kind:
            cur.execute("select * from kitchen.recipes where kind = %s order by name", (kind,))
        else:
            cur.execute("select * from kitchen.recipes order by kind, name")
        rows = [_list_row(dict(r)) for r in cur.fetchall()]
    return dataset_response("recipe", rows, "Recipes")


@router.get("/recipes/{recipe_id}", response_model=None)
def get_recipe(recipe_id: str) -> JSONResponse:
    with get_db() as conn, conn.cursor() as cur:
        r = load_recipe(cur, recipe_id)
    if not r:
        return api_error("NOT_FOUND", f"Recipe {recipe_id} not found", status=404)
    try:
        annotate_lines(r, ing_mod.master_by_id())
    except st.StorageError as e:
        return api_error("STORAGE_UNAVAILABLE", str(e), status=502)
    return dataset_response("recipe", [r], "Recipe")


@router.post("/recipes", response_model=None)
def create_recipe(body: RecipeIn) -> JSONResponse:
    if (err := _validate(body.kind, body.name, body.ingredients)):
        return err
    master, err = _check_items(body.ingredients)
    if err:
        return err
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select 1 from kitchen.recipes where lower(name) = lower(%s)", (body.name.strip(),))
            if cur.fetchone():
                return api_error("CONFLICT", "A recipe with this name exists", status=409)
            cur.execute(
                """insert into kitchen.recipes (name, kind, servings, description, prep_minutes, cook_minutes,
                                               steps, shelf_life_days, storage_location, status)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'draft') returning id""",
                (body.name.strip(), body.kind, body.servings, body.description, body.prep_minutes,
                 body.cook_minutes, body.steps, body.shelf_life_days, body.storage_location),
            )
            rid = str(cur.fetchone()["id"])
            save_ingredients(cur, rid, [i.model_dump() for i in body.ingredients])
            recompute_status(cur, rid, master)
            r = annotate_lines(load_recipe(cur, rid), master)
        conn.commit()
    return dataset_response("recipe", [r], "Recipe", status=201)


@router.patch("/recipes/{recipe_id}", response_model=None)
def update_recipe(recipe_id: str, body: RecipePatch) -> JSONResponse:
    fields = body.model_fields_set
    if not fields:
        return api_error("VALIDATION_ERROR", "No fields provided for update")
    if (err := _validate(body.kind, body.name, body.ingredients)):
        return err
    master, err = _check_items(body.ingredients)
    if err:
        return err
    with get_db() as conn:
        with conn.cursor() as cur:
            if not load_recipe(cur, recipe_id):
                return api_error("NOT_FOUND", f"Recipe {recipe_id} not found", status=404)
            sets, params = ["updated_at = now()"], []
            for f in ("name", "kind", "servings", "description", "prep_minutes", "cook_minutes", "steps",
                      "shelf_life_days", "storage_location"):
                if f in fields:
                    val = getattr(body, f)
                    if val is None and f in ("name", "kind", "servings", "steps"):
                        return api_error("VALIDATION_ERROR", f"{f} cannot be null")
                    sets.append(f"{f} = %s")
                    params.append(val.strip() if f == "name" else val)
            cur.execute(f"update kitchen.recipes set {', '.join(sets)} where id = %s", (*params, recipe_id))
            if "ingredients" in fields and body.ingredients is not None:
                save_ingredients(cur, recipe_id, [i.model_dump() for i in body.ingredients])
            if not master:  # ingredients not part of this patch: still need the master for the status
                try:
                    master = ing_mod.master_by_id()
                except st.StorageError as e:
                    return api_error("STORAGE_UNAVAILABLE", str(e), status=502)
            recompute_status(cur, recipe_id, master)
            r = annotate_lines(load_recipe(cur, recipe_id), master)
        conn.commit()
    return dataset_response("recipe", [r], "Recipe")


@router.delete("/recipes/{recipe_id}", response_model=None)
def delete_recipe(recipe_id: str) -> JSONResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select 1 from kitchen.planned_meals where recipe_id = %s limit 1", (recipe_id,))
            if cur.fetchone():
                return api_error("CONFLICT", "Recipe is used by planned meals", status=409)
            cur.execute("select 1 from kitchen.recipe_ingredients where base_recipe_id = %s limit 1", (recipe_id,))
            if cur.fetchone():
                return api_error("CONFLICT", "Recipe is used as a base by other recipes", status=409)
            cur.execute("delete from kitchen.recipes where id = %s returning id", (recipe_id,))
            if not cur.fetchone():
                return api_error("NOT_FOUND", f"Recipe {recipe_id} not found", status=404)
        conn.commit()
    return JSONResponse(status_code=200, content={"deleted": True})
