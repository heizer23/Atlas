"""Booking logic: cook (backflush), eat, undo, plus plan suggestion and shopping computation.

Idempotency contract: every StorageTracker movement carries a key
`<purpose>:<meal_id>:<revision>:<line>`. Repeating a request replays the same
movements (no double booking). Undo reverses the recorded movements and bumps
the meal revision so a later re-confirmation books fresh.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from backend import ingredients as ing_mod
from backend import storage_client as st
from backend.common import berlin_today
from backend.recipes_repo import load_recipe


class Conflict(Exception):
    pass


def _require_bookable(recipe: dict[str, Any]) -> None:
    """Draft recipes (unresolved articles) must never drive stock, shopping or planning."""
    if recipe["status"] != "active":
        raise Conflict(f"Recipe '{recipe['name']}' is a draft: assign all ingredients to articles first")


def _book(cur: Any, meal_id: str, purpose: str, item_id: int, delta: float, key: str, reason: str) -> dict[str, Any]:
    res = st.post_movement(item_id, delta, reason, key, ref=f"meal:{meal_id}")
    cur.execute(
        """insert into kitchen.meal_bookings (meal_id, purpose, item_id, movement_id)
           values (%s, %s, %s, %s) on conflict (movement_id) do nothing""",
        (meal_id, purpose, item_id, res["movement"]["id"]),
    )
    return res


def _lock_meal(cur: Any, meal_id: str) -> dict[str, Any] | None:
    cur.execute("select * from kitchen.planned_meals where id = %s for update", (meal_id,))
    r = cur.fetchone()
    return dict(r) if r else None


# ── cook ──────────────────────────────────────────────────────────────────────

class ShelfLifeRequired(ValueError):
    """A shelf life is needed to give a batch an honest best-before date (never assume 'forever')."""


def plan_allocations(recipe: dict[str, Any], produced: float, allocations: list[dict[str, Any]] | None,
                     cooked_on: date) -> list[dict[str, Any]]:
    """Validate the split of `produced` portions and resolve each batch's best-before date.

    allocations: [{location: 'fridge'|'freezer', qty, shelf_life_days?}]; None = everything in the fridge
    (backward compatible). Every portion must be allocated exactly once. Shelf life per batch: explicit value,
    else the recipe default (fridge: shelf_life_days, may stay empty = no best-before as before;
    freezer: freezer_shelf_life_days, REQUIRED - there is no implicit indefinite freezer life)."""
    if allocations is None:
        allocations = [{"location": "fridge", "qty": produced}]
    if not allocations:
        raise ValueError("allocations must not be empty")
    seen: set[str] = set()
    for a in allocations:
        if a["location"] not in ("fridge", "freezer"):
            raise ValueError("location must be 'fridge' or 'freezer'")
        if a["location"] in seen:
            raise ValueError(f"location '{a['location']}' is allocated twice")
        seen.add(a["location"])
        if not a["qty"] or a["qty"] <= 0:
            raise ValueError("allocation qty must be > 0 (omit locations that get nothing)")
    total = sum(a["qty"] for a in allocations)
    if abs(total - produced) > 1e-6:
        raise ValueError(f"All portions must be allocated exactly once: allocated {total:g} of {produced:g}")
    plan = []
    for a in allocations:
        default = recipe["freezer_shelf_life_days"] if a["location"] == "freezer" else recipe["shelf_life_days"]
        days = a.get("shelf_life_days") if a.get("shelf_life_days") is not None else default
        if days is None and a["location"] == "freezer":
            raise ShelfLifeRequired("Freezer shelf life (days) is required: enter it for this batch "
                                    "(optionally save it as the recipe default)")
        plan.append({"location": a["location"], "qty": float(a["qty"]), "shelf_life_days": days,
                     "expires_at": (cooked_on + timedelta(days=days)).isoformat() if days is not None else None})
    return plan


def cook(conn: Any, meal_id: str, produced_qty: float | None, allocations: list[dict[str, Any]] | None = None,
         remember_shelf_life: bool = False) -> dict[str, Any]:
    with conn.cursor() as cur:
        meal = _lock_meal(cur, meal_id)
        if not meal:
            raise LookupError("meal not found")
        if meal["kind"] != "cook" or not meal["recipe_id"]:
            raise Conflict("Only cooking sessions can be marked as cooked")
        if meal["status"] == "cooked":
            cur.execute("select item_id, location, qty from kitchen.cook_batches where meal_id = %s order by location",
                        (meal_id,))
            batches = [dict(r) for r in cur.fetchall()]
            cur.execute("select produced_qty from kitchen.cook_events where meal_id = %s", (meal_id,))
            return {"replayed": True, "produced_qty": cur.fetchone()["produced_qty"], "batches": batches,
                    "batch_item_id": batches[0]["item_id"] if batches else None}
        if meal["status"] != "planned":
            raise Conflict(f"Meal is {meal['status']}")

        recipe = load_recipe(cur, str(meal["recipe_id"]))
        _require_bookable(recipe)
        produced = float(produced_qty if produced_qty is not None else meal["portions"])
        if produced <= 0:
            raise ValueError("produced_qty must be > 0")
        cooked_on = berlin_today()
        plan = plan_allocations(recipe, produced, allocations, cooked_on)   # validate BEFORE any booking
        scale = produced / float(recipe["servings"])
        rev = meal["revision"]

        for ing in recipe["ingredients"]:
            _book(cur, meal_id, "cook", ing["item_id"], -float(ing["qty"]) * scale,
                  f"cook:{meal_id}:{rev}:{ing['id']}", f"cook {recipe['name']}")

        existing = {next((t.split(":", 1)[1] for t in (b.get("source_tags") or []) if t.startswith("alloc:")), None): b
                    for b in st.find_batches_for_meal(meal_id)}
        made = []
        for a in plan:
            label = st.location_label(a["location"])
            batch = existing.get(a["location"])
            if batch is None:
                batch = st.create_batch(f"{recipe['name']} {cooked_on.isoformat()}", str(recipe["id"]),
                                        recipe["yield_unit"], label, a["expires_at"], cooked_on.isoformat(),
                                        meal_id, a["location"])
            elif (batch["quantity"] or 0) == 0:
                # re-cooking after an undo: the old (archived) batch is reused with fresh location/date
                batch = st.update_item(batch["id"], {"location": label, "expires_at": a["expires_at"],
                                                     "produced_at": cooked_on.isoformat()})
            _book(cur, meal_id, "cook", batch["id"], a["qty"], f"cook:{meal_id}:{rev}:batch:{a['location']}",
                  f"cooked {recipe['name']} ({a['location']})")
            cur.execute("insert into kitchen.cook_batches (meal_id, item_id, location, qty) values (%s, %s, %s, %s) "
                        "on conflict (meal_id, location) do update set item_id = excluded.item_id, qty = excluded.qty",
                        (meal_id, batch["id"], a["location"], a["qty"]))
            made.append({"item_id": batch["id"], "location": a["location"], "qty": a["qty"],
                         "expires_at": a["expires_at"]})

        if remember_shelf_life:   # fill recipe defaults that were missing, never overwrite configured ones
            for a in plan:
                col = "freezer_shelf_life_days" if a["location"] == "freezer" else "shelf_life_days"
                if recipe[col] is None and a["shelf_life_days"] is not None:
                    cur.execute(f"update kitchen.recipes set {col} = %s where id = %s",
                                (a["shelf_life_days"], recipe["id"]))

        cur.execute("insert into kitchen.cook_events (meal_id, produced_qty, batch_item_id) values (%s, %s, %s)",
                    (meal_id, produced, made[0]["item_id"]))
        cur.execute("update kitchen.planned_meals set status = 'cooked', updated_at = now() where id = %s",
                    (meal_id,))
    conn.commit()
    return {"replayed": False, "produced_qty": produced, "batches": made, "batch_item_id": made[0]["item_id"]}


# ── eat ───────────────────────────────────────────────────────────────────────

def eat(conn: Any, meal_id: str, portions: float | None, batch_id: int | None = None) -> dict[str, Any]:
    """Consume prepared base portions + the dish's own raw ingredients (the base's raw ingredients were already
    booked when it was cooked, so they are NOT deducted again).

    Auto selection uses ready batches only (fridge, not expired), earliest best-before first. `batch_id`
    prefers one specific batch for the base it belongs to; a frozen batch must be thawed first, an expired one
    discarded - both are refused explicitly rather than silently skipped."""
    with conn.cursor() as cur:
        meal = _lock_meal(cur, meal_id)
        if not meal:
            raise LookupError("meal not found")
        if meal["kind"] != "meal":
            raise Conflict("Cooking sessions are not eaten; mark them as cooked")
        if meal["status"] == "eaten":
            cur.execute("select * from kitchen.consumption_events where meal_id = %s", (meal_id,))
            ev = dict(cur.fetchone())
            return {"replayed": True, "portions": ev["portions"], "shortfall": []}
        if meal["status"] != "planned":
            raise Conflict(f"Meal is {meal['status']}")

        eaten = float(portions if portions is not None else meal["portions"])
        if eaten <= 0:
            raise ValueError("portions must be > 0")
        shortfall: list[dict[str, Any]] = []
        rev = meal["revision"]
        today = berlin_today().isoformat()
        chosen = None
        if batch_id is not None:
            chosen = next((b for b in st.list_items(kind="batch") if b["id"] == batch_id), None)
            if chosen is None or (chosen["quantity"] or 0) <= 0:
                raise Conflict(f"Batch {batch_id} not found or empty")
            if st.storage_of(chosen) == "freezer":
                raise Conflict(f"Batch {batch_id} is frozen: thaw it first")
            if st.is_expired(chosen, today):
                raise Conflict(f"Batch {batch_id} is expired: discard it instead")
        if meal["recipe_id"]:
            recipe = load_recipe(cur, str(meal["recipe_id"]))
            _require_bookable(recipe)
            if chosen is not None and not any(str(i["base_recipe_id"]) == chosen.get("recipe_ref")
                                              for i in recipe["ingredients"] if i["base_recipe_id"]):
                raise Conflict(f"Batch {batch_id} is not a base of {recipe['name']}")
            scale = eaten / float(recipe["servings"])
            for ing in recipe["ingredients"]:
                need = float(ing["qty"]) * scale
                if ing["base_recipe_id"]:
                    left = need
                    ready = st.find_batches(str(ing["base_recipe_id"]))
                    if chosen is not None and chosen.get("recipe_ref") == str(ing["base_recipe_id"]):
                        ready = [chosen] + [b for b in ready if b["id"] != chosen["id"]]
                    for batch in ready:
                        take = min(left, float(batch["quantity"]))
                        _book(cur, meal_id, "eat", batch["id"], -take,
                              f"eat:{meal_id}:{rev}:{ing['id']}:{batch['id']}", f"ate {recipe['name']}")
                        left -= take
                        if left <= 1e-9:
                            break
                    if left > 1e-9:
                        every = st.find_batches(str(ing["base_recipe_id"]), include_expired=True, storage=None)
                        shortfall.append({
                            "name": ing["name"], "missing": round(left, 4),
                            "expired_in_stock": round(sum(float(b["quantity"]) for b in every if st.is_expired(b, today)), 4),
                            "frozen_in_stock": round(sum(float(b["quantity"]) for b in every
                                                         if st.storage_of(b) == "freezer" and not st.is_expired(b, today)), 4)})
                else:
                    _book(cur, meal_id, "eat", ing["item_id"], -need,
                          f"eat:{meal_id}:{rev}:{ing['id']}", f"ate {recipe['name']}")

        cur.execute("insert into kitchen.consumption_events (meal_id, portions) values (%s, %s)", (meal_id, eaten))
        cur.execute("update kitchen.planned_meals set status = 'eaten', updated_at = now() where id = %s", (meal_id,))
    conn.commit()
    return {"replayed": False, "portions": eaten, "shortfall": shortfall}


# ── undo ──────────────────────────────────────────────────────────────────────

def undo(conn: Any, meal_id: str) -> dict[str, Any]:
    with conn.cursor() as cur:
        meal = _lock_meal(cur, meal_id)
        if not meal:
            raise LookupError("meal not found")
        if meal["status"] not in ("cooked", "eaten"):
            raise Conflict("Nothing to undo")
        if meal["status"] == "cooked":
            cur.execute("select item_id, qty from kitchen.cook_batches where meal_id = %s", (meal_id,))
            produced = {r["item_id"]: float(r["qty"]) for r in cur.fetchall()}
            for b in st.list_items(kind="batch", archived="include"):
                if b["id"] in produced and float(b["quantity"] or 0) + 1e-9 < produced[b["id"]]:
                    raise Conflict("A batch was already (partly) consumed; undo the meals that used it first")
        cur.execute("select movement_id from kitchen.meal_bookings where meal_id = %s order by created_at desc",
                    (meal_id,))
        for b in cur.fetchall():
            st.reverse_movement(str(b["movement_id"]))
        cur.execute("delete from kitchen.meal_bookings where meal_id = %s", (meal_id,))
        cur.execute("delete from kitchen.cook_events where meal_id = %s", (meal_id,))
        cur.execute("delete from kitchen.cook_batches where meal_id = %s", (meal_id,))
        cur.execute("delete from kitchen.consumption_events where meal_id = %s", (meal_id,))
        cur.execute("update kitchen.planned_meals set status = 'planned', revision = revision + 1, "
                    "updated_at = now() where id = %s", (meal_id,))
    conn.commit()
    return {"status": "planned"}


# ── shopping ──────────────────────────────────────────────────────────────────

def compute_shopping(conn: Any, plan_id: str) -> dict[str, Any]:
    """Needs of all still-planned meals vs. StorageTracker stock, keyed by article id.

    buy:          shortfall per article.
    probably_have: stock that covers (part of) the need; user confirms/corrects it.
    missing_bases: prepared bases required but neither stocked nor cooked in this plan.
    draft_recipes: planned recipes skipped because they still have unresolved articles.
    """
    master = ing_mod.master_by_id()
    with conn.cursor() as cur:
        cur.execute("select id, recipe_id, kind, portions from kitchen.planned_meals "
                    "where plan_id = %s and status = 'planned' and recipe_id is not null", (plan_id,))
        meals = [dict(m) for m in cur.fetchall()]
        need: dict[int, dict[str, Any]] = {}
        base_need: dict[str, dict[str, Any]] = {}
        cooked_here: dict[str, float] = {}
        drafts: set[str] = set()
        for m in meals:
            recipe = load_recipe(cur, str(m["recipe_id"]))
            if recipe["status"] != "active":
                drafts.add(recipe["name"])
                continue
            scale = float(m["portions"]) / float(recipe["servings"])
            if m["kind"] == "cook":
                cooked_here[str(recipe["id"])] = cooked_here.get(str(recipe["id"]), 0) + float(m["portions"])
            for ing in recipe["ingredients"]:
                q = float(ing["qty"]) * scale
                if ing["base_recipe_id"]:
                    b = base_need.setdefault(str(ing["base_recipe_id"]), {"name": ing["name"], "need": 0.0})
                    b["need"] += q
                else:
                    line = need.setdefault(ing["item_id"], {"unit": ing["unit"], "needed": 0.0})
                    line["needed"] += q

    buy, have = [], []
    for item_id, n in sorted(need.items(), key=lambda kv: master.get(kv[0], {}).get("name", "").lower()):
        item = master.get(item_id)
        if item is None:
            continue
        stock = float(item["quantity"] or 0)
        line = {"item_id": item_id, "name": item["name"], "unit": n["unit"], "needed": round(n["needed"], 4),
                "stock": round(stock, 4)}
        if stock > 0:
            have.append({**line, "covered": round(min(stock, n["needed"]), 4)})
        if stock < n["needed"] - 1e-9:
            buy.append({**line, "to_buy": round(n["needed"] - stock, 4)})

    missing_bases = []
    for rid, b in base_need.items():
        avail = sum(float(x["quantity"]) for x in st.find_batches(rid)) + cooked_here.get(rid, 0)
        if avail + 1e-9 < b["need"]:
            frozen = sum(float(x["quantity"]) for x in st.find_batches(rid, storage="freezer"))
            missing_bases.append({"name": b["name"], "needed": round(b["need"], 4), "available": round(avail, 4),
                                  "frozen": round(frozen, 4)})   # frozen portions: usable after thawing
    return {"buy": buy, "probably_have": have, "missing_bases": missing_bases, "draft_recipes": sorted(drafts)}


# ── plan suggestion ───────────────────────────────────────────────────────────

COOK_DAYS = (0, 3, 5)  # day offsets of the 1st, 2nd, 3rd cooking session


def default_cook_sessions(days: int) -> int:
    """Short plans (<= 4 days, e.g. one shopping round) get one big cook; longer plans two."""
    return 1 if days <= 4 else 2


def suggest_plan(conn: Any, week_start: date, cook_sessions: int | None = None, days: int = 7) -> str:
    """`days` (1-7) dinners starting at `week_start`: `cook_sessions` base cooks (on COOK_DAYS that fall inside
    the plan), derived meals draw down the portions that are still good on their day, favorites fill gaps,
    anything left is a flexible day (recipe null). Portions left over stay in stock for the next plan."""
    if not 1 <= days <= 7:
        raise ValueError("days must be between 1 and 7")
    if cook_sessions is None:
        cook_sessions = default_cook_sessions(days)
    with conn.cursor() as cur:
        cur.execute("select * from kitchen.recipes where status = 'active' order by name")
        recipes = [dict(r) for r in cur.fetchall()]
        ing_by: dict[str, list[dict[str, Any]]] = {}
        cur.execute("select * from kitchen.recipe_ingredients where base_recipe_id is not null")
        for i in cur.fetchall():
            ing_by.setdefault(str(i["recipe_id"]), []).append(dict(i))

        bases = [r for r in recipes if r["kind"] == "base"]
        # lots per base: portions with their last good day (None = no date). Stock lots come from
        # unexpired batches; cooks planned below add lots expiring day + shelf_life_days.
        lots: dict[str, list[dict[str, Any]]] = {}
        for r in bases:
            lots[str(r["id"])] = [
                {"exp": date.fromisoformat(b["expires_at"]) if b.get("expires_at") else None, "qty": float(b["quantity"])}
                for b in st.find_batches(str(r["id"]))]
        stocked = {rid: sum(l["qty"] for l in ls) for rid, ls in lots.items()}
        bases.sort(key=lambda r: (stocked[str(r["id"])], r["name"]))
        chosen = bases[:cook_sessions]

        def avail_on(base_id: str, d: date) -> float:
            return sum(l["qty"] for l in lots.get(base_id, []) if l["exp"] is None or l["exp"] >= d)

        def consume(base_id: str, qty: float, d: date) -> None:
            for l in sorted((l for l in lots[base_id] if l["exp"] is None or l["exp"] >= d),
                            key=lambda l: (l["exp"] is None, l["exp"] or date.max)):
                take = min(qty, l["qty"])
                l["qty"] -= take
                qty -= take
                if qty <= 1e-9:
                    return

        cook_days = [d for d in COOK_DAYS if d < days][:len(chosen)]
        derived = [r for r in recipes if r["kind"] == "derived"]
        favorites = [r for r in recipes if r["kind"] == "favorite"]
        cur.execute("insert into kitchen.plans (week_start, days) values (%s, %s) returning id", (week_start, days))
        plan_id = str(cur.fetchone()["id"])

        def add(recipe: dict | None, kind: str, day: int, portions: float) -> None:
            cur.execute(
                "insert into kitchen.planned_meals (plan_id, recipe_id, kind, day, portions) "
                "values (%s, %s, %s, %s, %s)",
                (plan_id, recipe["id"] if recipe else None, kind, week_start + timedelta(days=day), portions))

        used: set[str] = set()
        fav_i = 0
        for day in range(days):
            for base, cd in zip(chosen, cook_days):
                if cd == day:
                    add(base, "cook", day, float(base["servings"]))
                    shelf = base["shelf_life_days"]
                    lots[str(base["id"])].append({
                        "exp": week_start + timedelta(days=day + shelf) if shelf is not None else None,
                        "qty": float(base["servings"])})
            pick = None
            meal_day = week_start + timedelta(days=day)
            for d in derived:
                needs = ing_by.get(str(d["id"]), [])
                if needs and str(d["id"]) not in used and all(
                        avail_on(str(n["base_recipe_id"]), meal_day) >= float(n["qty"]) for n in needs):
                    pick = d
                    break
            if pick:
                for n in ing_by[str(pick["id"])]:
                    consume(str(n["base_recipe_id"]), float(n["qty"]), meal_day)
                used.add(str(pick["id"]))
                add(pick, "meal", day, float(pick["servings"]))
            elif favorites and day in (2, 5):
                add(favorites[fav_i % len(favorites)], "meal", day, float(favorites[fav_i % len(favorites)]["servings"]))
                fav_i += 1
            else:
                add(None, "meal", day, 1)
    conn.commit()
    return plan_id


