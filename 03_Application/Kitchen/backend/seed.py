"""Sample recipe library (idempotent by name). NOT run at startup since the production test data was cleared
(2026-11-02); recipes come from the import. Used by tests/conftest.py as fixture data."""
from __future__ import annotations

from backend.database import get_db
from backend.recipes_repo import save_ingredients

# (name, kind, servings, shelf_life_days, location, steps, ingredients[(name, qty, unit)], bases[(base name, portions)])
SEED = [
    ("Dal", "base", 6, 4, "Kühlschrank",
     "Zwiebel, Knoblauch, Ingwer in Öl anschwitzen. Curry zugeben. Linsen, Tomaten, Kokosmilch und 600 ml Wasser dazu, 25 Min köcheln.",
     [("Rote Linsen", 300, "g"), ("Zwiebel", 2, "Stück"), ("Knoblauch", 4, "Zehe"), ("Ingwer", 30, "g"),
      ("Dosentomaten", 400, "g"), ("Kokosmilch", 400, "ml"), ("Currypulver", 2, "EL"), ("Öl", 2, "EL")], []),
    ("Vegetarische Bolognese", "base", 6, 4, "Kühlschrank",
     "Zwiebel, Karotten, Sellerie anbraten. Tomatenmark, Linsen, passierte Tomaten und 300 ml Wasser, 30 Min köcheln.",
     [("Braune Linsen", 200, "g"), ("Zwiebel", 2, "Stück"), ("Karotte", 3, "Stück"), ("Sellerie", 2, "Stange"),
      ("Passierte Tomaten", 700, "g"), ("Tomatenmark", 2, "EL"), ("Öl", 2, "EL")], []),
    ("Dal mit Hähnchen und Spinat", "derived", 2, None, None,
     "Hähnchen in Streifen braten, Spinat zugeben, Dal erhitzen und unterheben.",
     [("Hähnchenbrust", 300, "g"), ("Spinat", 200, "g")], [("Dal", 2)]),
    ("Dal mit Eiern und Spinat", "derived", 2, None, None,
     "Eier hart kochen, Spinat im Dal zusammenfallen lassen, Eier halbieren und darauf servieren.",
     [("Eier", 4, "Stück"), ("Spinat", 200, "g")], [("Dal", 2)]),
    ("Spaghetti Bolognese", "derived", 2, None, None,
     "Spaghetti kochen, Bolognese erhitzen.",
     [("Spaghetti", 200, "g")], [("Vegetarische Bolognese", 2)]),
    ("Pfannkuchen", "favorite", 2, None, None,
     "Teig rühren, 10 Min ruhen lassen, in Butter ausbacken.",
     [("Eier", 3, "Stück"), ("Mehl", 150, "g"), ("Milch", 300, "ml")], []),
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
                lines = [{"name": base, "qty": q, "unit": "Portionen", "base_recipe_id": ids[base]}
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
