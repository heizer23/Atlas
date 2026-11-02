from __future__ import annotations

from typing import Any

ING_COLS = "id, position, name, qty, unit, base_recipe_id"


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
            """insert into kitchen.recipe_ingredients (recipe_id, position, name, qty, unit, base_recipe_id)
               values (%s, %s, %s, %s, %s, %s)""",
            (recipe_id, pos, ing["name"].strip(), ing["qty"], ing["unit"].strip(), ing.get("base_recipe_id")),
        )
