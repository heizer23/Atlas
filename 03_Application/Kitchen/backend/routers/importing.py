"""Ingredient master access (read-through to StorageTracker) and recipe import preview.

Registered BEFORE routers.recipes so the static path /recipes/import-example is not captured by /recipes/{id}.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend import ingredients as ing_mod
from backend import recipe_import
from backend import storage_client as st
from backend.common import dataset_response
from backend.database import get_db
from platform_errorhandling import api_error

router = APIRouter(prefix="/kitchen", tags=["import"])


class ImportPreviewIn(BaseModel):
    text: str


class NewIngredientIn(BaseModel):
    name: str
    unit: str


@router.get("/ingredients", response_model=None)
def list_ingredients() -> JSONResponse:
    """Article master for pickers and the ChatGPT export: raw ingredients incl. zero stock, no batches."""
    try:
        items = ing_mod.master_items()
    except st.StorageError as e:
        return api_error("STORAGE_UNAVAILABLE", str(e), status=502)
    rows = [{"id": i["id"], "name": i["name"], "unit": i.get("unit"), "quantity": i["quantity"]}
            for i in sorted(items, key=lambda i: i["name"].lower())]
    return dataset_response("ingredient", rows, "Ingredients")


@router.post("/ingredients", response_model=None)
def create_ingredient(body: NewIngredientIn) -> JSONResponse:
    """Create an article in StorageTracker (stock 0, no movement). Called only on explicit user confirmation."""
    name, unit = body.name.strip(), body.unit.strip()
    if not name or not unit:
        return api_error("VALIDATION_ERROR", "name and unit must not be empty")
    try:
        for i in ing_mod.master_items():
            if ing_mod.norm(i["name"]) == ing_mod.norm(name):
                return api_error("CONFLICT", f"Article '{i['name']}' already exists — assign it instead", status=409)
        item = st.create_ingredient(name, unit)
    except st.StorageError as e:
        return api_error("STORAGE_UNAVAILABLE", str(e), status=502)
    return dataset_response("ingredient", [{"id": item["id"], "name": item["name"], "unit": item.get("unit"),
                                            "quantity": item["quantity"]}], "Ingredient", status=201)


@router.get("/recipes/import-example", response_model=None)
def import_example() -> JSONResponse:
    return dataset_response("recipe_import_example", [{"example": recipe_import.EXAMPLE}], "Import example")


@router.post("/recipes/import/preview", response_model=None)
def import_preview(body: ImportPreviewIn) -> JSONResponse:
    try:
        master_list = ing_mod.master_items()
    except st.StorageError as e:
        return api_error("STORAGE_UNAVAILABLE", str(e), status=502)
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("select id, name, yield_unit, kind from kitchen.recipes")
        rows = [dict(r) for r in cur.fetchall()]
    bases = {ing_mod.norm(r["name"]): {"id": str(r["id"]), "name": r["name"], "yield_unit": r["yield_unit"]}
             for r in rows if r["kind"] == "base"}
    names = {ing_mod.norm(r["name"]) for r in rows}
    return dataset_response("recipe_import_preview",
                            [recipe_import.build_preview(body.text, master_list, bases, names)], "Import preview")
