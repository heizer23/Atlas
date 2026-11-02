from __future__ import annotations

from typing import Any

ING_COLS = "id, position, name, qty, unit, base_recipe_id, item_id"


def load_recipe(cur: Any, recipe_id: str) -> dict[str, Any] | None:
    cur.execute("select * from kitchen.recipes where id = %s", (recipe_id,))
    r = cur.fetchone()
    if not r:
        return None
    r = dict(r)
    cur.execute(f"select {ING_COLS} from kitchen.recipe_ingredients where recipe_id = %s order by position",
                (recipe_id,))
    r["ingredients"] = [dict(i) for i in cur.fetchall()]
    return r


def save_ingredients(cur: Any, recipe_id: str, ingredients: list[dict[str, Any]]) -> None:
    cur.execute("delete from kitchen.recipe_ingredients where recipe_id = %s", (recipe_id,))
    for pos, ing in enumerate(ingredients):
        cur.execute(
            """insert into kitchen.recipe_ingredients (recipe_id, position, name, qty, unit, base_recipe_id, item_id)
               values (%s, %s, %s, %s, %s, %s, %s)""",
            (recipe_id, pos, ing["name"].strip(), ing["qty"], ing["unit"].strip(), ing.get("base_recipe_id"),
             None if ing.get("base_recipe_id") else ing.get("item_id")),
        )


def recompute_status(cur: Any, recipe_id: str, master: dict[str, dict[str, Any]]) -> str:
    """Set recipes.status from the lines: active iff all lines are base/matched (see ingredients.py)."""
    from backend.ingredients import recipe_status
    cur.execute(f"select {ING_COLS} from kitchen.recipe_ingredients where recipe_id = %s", (recipe_id,))
    status = recipe_status([dict(i) for i in cur.fetchall()], master)
    cur.execute("update kitchen.recipes set status = %s where id = %s", (status, recipe_id))
    return status


def annotate_lines(recipe: dict[str, Any], master: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Add live per-line status and the article's current name/unit (names may change; ids do not)."""
    from backend.ingredients import line_status
    for ing in recipe["ingredients"]:
        ing["line_status"] = line_status(ing, master)
        item = master.get(str(ing["item_id"])) if ing.get("item_id") else None
        ing["item_name"] = item["name"] if item else None
        ing["item_unit"] = item.get("unit") if item else None
    return recipe
