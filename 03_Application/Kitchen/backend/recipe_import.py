"""Recipe import (format atlas.kitchen.recipe v1): parse, validate, resolve against the article master.

Preview only: nothing is written. Saving goes through POST /kitchen/recipes with the (possibly
user-resolved) article ids, which re-validates. Import never creates articles or stock movements.
"""

from __future__ import annotations

import json
import re
from typing import Any

from backend import ingredients as ing_mod

FORMAT = "atlas.kitchen.recipe"
MASTER_FORMAT = "atlas.kitchen.ingredient_master"
VERSION = 1
KINDS = ("base", "derived", "favorite")
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)

_COMMENT = ("kind: base | derived | favorite. Ingredients: copy 'item_id', 'name' and 'unit' of existing articles from the "
            "exported ingredient master; 'unit' must equal the article's base unit. For an ingredient without an article "
            "leave 'item_id' null (you assign or create the article during import). A derived dish may reference a "
            "cooked base via 'base_recipe' (the exact recipe name) instead of item_id.")


def make_example(master_list: list[dict[str, Any]]) -> dict[str, Any]:
    """Importable example. Uses up to two real articles of the household (id + name + unit, as in the master
    export) and one new ingredient without article, so every field and both line kinds are demonstrated."""
    real = sorted((i for i in master_list if i.get("unit")), key=lambda i: i["name"].lower())[:2]
    lines: list[dict[str, Any]] = [
        {"item_id": i["id"], "name": i["name"], "qty": 250 if n == 0 else 1, "unit": i["unit"]}
        for n, i in enumerate(real)
    ]
    lines.append({"item_id": None, "name": "Gemüsebrühe (neu, noch kein Artikel)", "qty": 800, "unit": "ml"})
    return {
        "format": FORMAT,
        "version": VERSION,
        "_comment": _COMMENT,
        "recipe": {
            "name": "Beispiel: Einfache Suppe",
            "description": "Beispielrezept mit Artikeln aus dem Bestand und einer neuen Zutat.",
            "kind": "favorite",
            "servings": 4,
            "yield_unit": "Portionen",
            "prep_minutes": 10,
            "cook_minutes": 25,
            "shelf_life_days": 3,
            "storage_location": "Kühlschrank",
            "ingredients": lines,
            "steps": [
                "Zutaten vorbereiten und in etwas Öl anschwitzen.",
                "Mit Brühe aufgießen, 20 Minuten köcheln.",
                "Pürieren und abschmecken.",
            ],
        },
    }


def _err(errors: list[dict[str, str]], path: str, msg: str) -> None:
    errors.append({"path": path, "message": msg})


def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _opt_int(rec: dict, key: str, errors: list, path: str) -> int | None:
    v = rec.get(key)
    if v is None:
        return None
    if not isinstance(v, int) or isinstance(v, bool) or v < 0:
        _err(errors, f"{path}.{key}", "must be an integer >= 0")
        return None
    return v


def _opt_str(rec: dict, key: str, errors: list, path: str) -> str | None:
    v = rec.get(key)
    if v is None:
        return None
    if not isinstance(v, str):
        _err(errors, f"{path}.{key}", "must be a string")
        return None
    return v.strip() or None


def parse_recipe(text: str, base_recipes: dict[str, dict[str, Any]]) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    """Returns (normalized recipe or None, errors). base_recipes: normalized name -> {id, name, yield_unit}."""
    errors: list[dict[str, str]] = []
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return None, [{"path": "$", "message": f"Invalid JSON: {e.msg} (line {e.lineno}, column {e.colno})"}]
    if not isinstance(data, dict):
        return None, [{"path": "$", "message": "Top level must be a JSON object"}]
    if "format" in data and data["format"] != FORMAT:
        what = "an ingredient master export, not a recipe" if data["format"] == MASTER_FORMAT else f"'{data['format']}'"
        return None, [{"path": "format", "message": f"Expected '{FORMAT}', got {what}"}]
    if data.get("version", VERSION) != VERSION:
        return None, [{"path": "version", "message": f"Unsupported version {data.get('version')} (supported: {VERSION})"}]
    rec = data["recipe"] if isinstance(data.get("recipe"), dict) else data if "recipe" not in data else None
    if rec is None:
        return None, [{"path": "recipe", "message": "'recipe' must be an object"}]

    p = "recipe"
    name = rec.get("name")
    if not isinstance(name, str) or not name.strip():
        _err(errors, f"{p}.name", "required, non-empty string")
    kind = rec.get("kind")
    if kind not in KINDS:
        _err(errors, f"{p}.kind", f"must be one of: {', '.join(KINDS)}")
    servings = rec.get("servings")
    if not _is_num(servings) or servings <= 0:
        _err(errors, f"{p}.servings", "required number > 0")
    yield_unit = _opt_str(rec, "yield_unit", errors, p) or "Portionen"
    description = _opt_str(rec, "description", errors, p)
    storage = _opt_str(rec, "storage_location", errors, p)
    prep, cook, shelf = (_opt_int(rec, k, errors, p) for k in ("prep_minutes", "cook_minutes", "shelf_life_days"))

    steps_raw = rec.get("steps", [])
    if isinstance(steps_raw, str):
        steps_raw = [steps_raw]
    if not isinstance(steps_raw, list) or not all(isinstance(x, str) for x in steps_raw):
        _err(errors, f"{p}.steps", "must be a list of strings")
        steps_raw = []

    lines: list[dict[str, Any]] = []
    raw_lines = rec.get("ingredients")
    if not isinstance(raw_lines, list) or not raw_lines:
        _err(errors, f"{p}.ingredients", "required non-empty list")
        raw_lines = []
    for i, ln in enumerate(raw_lines):
        lp = f"{p}.ingredients[{i}]"
        if not isinstance(ln, dict):
            _err(errors, lp, "must be an object")
            continue
        qty = ln.get("qty")
        if not _is_num(qty) or qty <= 0:
            _err(errors, f"{lp}.qty", "required number > 0")
        base_name = ln.get("base_recipe")
        item_id = ln.get("item_id")
        if item_id is not None and (not isinstance(item_id, str) or not _UUID.match(item_id)):
            _err(errors, f"{lp}.item_id", "must be an article id (UUID) or null")
            item_id = None
        line: dict[str, Any] = {"qty": qty, "item_id": item_id.lower() if item_id else None, "base_recipe_id": None}
        if base_name is not None:
            base = base_recipes.get(ing_mod.norm(str(base_name)))
            line["name"] = str(base_name).strip()
            line["unit"] = base["yield_unit"] if base else "Portionen"
            line["item_id"] = None
            if base:
                line["base_recipe_id"] = base["id"]
            else:
                line["unknown_base"] = True
        else:
            unit = ln.get("unit")
            nm = ln.get("name")
            if not isinstance(unit, str) or not unit.strip():
                _err(errors, f"{lp}.unit", "required, non-empty string")
                unit = ""
            if nm is not None and not isinstance(nm, str):
                _err(errors, f"{lp}.name", "must be a string")
                nm = None
            if not (nm or "").strip() and not item_id:
                _err(errors, f"{lp}.name", "required when no item_id is given")
            line["name"] = (nm or "").strip()
            line["unit"] = unit.strip()
        lines.append(line)

    if errors:
        return None, errors
    return {
        "name": name.strip(), "kind": kind, "servings": servings, "yield_unit": yield_unit,
        "description": description, "prep_minutes": prep, "cook_minutes": cook, "shelf_life_days": shelf,
        "storage_location": storage, "steps": "\n".join(s.strip() for s in steps_raw if s.strip()),
        "ingredients": lines,
    }, []


def build_preview(text: str, master_list: list[dict[str, Any]], base_recipes: dict[str, dict[str, Any]],
                  existing_names: set[str]) -> dict[str, Any]:
    recipe, errors = parse_recipe(text, base_recipes)
    if recipe is None:
        return {"ok": False, "errors": errors, "recipe": None, "name_exists": False, "unresolved": 0,
                "status_if_saved": None}
    master = {i["id"]: i for i in master_list}
    unresolved = 0
    for ln in recipe["ingredients"]:
        status = "unknown_base" if ln.pop("unknown_base", False) else ing_mod.line_status(ln, master)
        item = master.get(ln["item_id"]) if ln["item_id"] else None
        if item and not ln["name"]:
            ln["name"] = item["name"]
        ln["line_status"] = status
        ln["item_name"] = item["name"] if item else None
        ln["item_unit"] = item.get("unit") if item else None
        ln["suggestions"] = ing_mod.suggestions(ln["name"], master_list) if status in ("unresolved", "unknown_id") else []
        if status not in ("matched", "base"):
            unresolved += 1
    return {"ok": True, "errors": [], "recipe": recipe, "unresolved": unresolved,
            "name_exists": ing_mod.norm(recipe["name"]) in existing_names,
            "status_if_saved": "active" if unresolved == 0 else "draft"}
