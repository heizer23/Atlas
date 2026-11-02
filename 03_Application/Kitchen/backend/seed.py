"""Sample recipe library (idempotent by name). NOT run at startup since the production test data was cleared
(2026-11-02); recipes come from the import. Used by tests/conftest.py as fixture data."""
from __future__ import annotations

from backend.database import get_db
from backend.recipes_repo import save_ingredients

# (name, kind, servings, shelf_life_days, location, steps, ingredients[(name, qty, unit)], bases[(base name, portions)])
SEED = [
    ("Dal", "base", 6, 4, "Fridge",
     "Sauté onion, garlic and ginger in oil. Add curry powder. Add lentils, tomatoes, coconut milk and 600 ml water, simmer 25 min.",
     [("Red lentils", 300, "g"), ("Onion", 2, "piece"), ("Garlic", 4, "clove"), ("Ginger", 30, "g"),
      ("Canned tomatoes", 400, "g"), ("Coconut milk", 400, "ml"), ("Curry powder", 2, "tbsp"), ("Olive oil", 2, "tbsp")], []),
    ("Vegetarian Bolognese", "base", 6, 4, "Fridge",
     "Fry onion, carrots and celery. Add tomato paste, lentils, passata and 300 ml water, simmer 30 min.",
     [("Brown lentils", 200, "g"), ("Onion", 2, "piece"), ("Carrot", 3, "piece"), ("Celery", 2, "stalk"),
      ("Passata", 700, "g"), ("Tomato paste", 2, "tbsp"), ("Olive oil", 2, "tbsp")], []),
    ("Dal with Chicken and Spinach", "derived", 2, None, None,
     "Fry chicken strips, add spinach, heat the dal and fold in.",
     [("Chicken breast", 300, "g"), ("Spinach", 200, "g")], [("Dal", 2)]),
    ("Dal with Eggs and Spinach", "derived", 2, None, None,
     "Hard-boil eggs, wilt spinach into the dal, halve the eggs and serve on top.",
     [("Eggs", 4, "piece"), ("Spinach", 200, "g")], [("Dal", 2)]),
    ("Spaghetti Bolognese", "derived", 2, None, None,
     "Cook spaghetti, heat the bolognese.",
     [("Spaghetti", 200, "g")], [("Vegetarian Bolognese", 2)]),
    ("Pancakes", "favorite", 2, None, None,
     "Mix the batter, rest 10 min, fry in butter.",
     [("Eggs", 3, "piece"), ("Flour", 150, "g"), ("Milk", 300, "ml")], []),
]


def seed_recipes() -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            ids: dict[str, str] = {}
            for name, kind, servings, shelf, loc, steps, ings, bases in SEED:
                cur.execute("select id from kitchen.recipes where name = %s", (name,))
                row = cur.fetchone()
                if row:
                    ids[name] = str(row["id"])
                    continue
                cur.execute(
                    """insert into kitchen.recipes (name, kind, servings, steps, shelf_life_days, storage_location)
                       values (%s, %s, %s, %s, %s, %s) returning id""",
                    (name, kind, servings, steps, shelf, loc),
                )
                rid = str(cur.fetchone()["id"])
                ids[name] = rid
                lines = [{"name": base, "qty": q, "unit": "portions", "base_recipe_id": ids[base]}
                         for base, q in bases]
                lines += [{"name": n, "qty": q, "unit": u} for n, q, u in ings]
                save_ingredients(cur, rid, lines)
        conn.commit()


def migrate_legacy_ingredients() -> None:
    """One-time/idempotent: give recipe lines without article id (seed + pre-1.1 recipes) a StorageTracker
    article id, then recompute every recipe's status.

    Matching uses the legacy name+unit lookup against existing articles; if none exists the article is
    created with stock 0 (this reproduces what Sprint 1 did implicitly at first booking). If StorageTracker is
    unreachable nothing changes and the migration is retried on the next start.
    Imports never use this path.
    """
    from backend import ingredients as ing_mod
    from backend import storage_client as st
    from backend.recipes_repo import recompute_status

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select id, name, unit from kitchen.recipe_ingredients "
                        "where item_id is null and base_recipe_id is null")
            todo = [dict(r) for r in cur.fetchall()]
            try:
                known = st.list_items(kind="ingredient")
                for line in todo:
                    item = next((i for i in known if ing_mod.norm(i["name"]) == ing_mod.norm(line["name"])
                                 and i.get("unit") in (None, line["unit"])), None)
                    if item is None:
                        item = st.create_ingredient(line["name"], line["unit"])
                        known.append(item)
                    cur.execute("update kitchen.recipe_ingredients set item_id = %s where id = %s",
                                (item["id"], line["id"]))
                master = ing_mod.master_by_id()
            except st.StorageError:
                master = None  # keep stored statuses; retried on next start
            if master is not None:
                cur.execute("select id from kitchen.recipes")
                for r in cur.fetchall():
                    recompute_status(cur, str(r["id"]), master)
        conn.commit()
