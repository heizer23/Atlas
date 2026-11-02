from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any, Literal

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend import service
from backend import storage_client as st
from backend.common import berlin_today, dataset_response, plain
from backend.database import get_db
from platform_errorhandling import api_error

router = APIRouter(prefix="/kitchen", tags=["plans"])

MEAL_SELECT = """
    select m.id, m.plan_id, m.recipe_id, r.name as recipe_name, r.kind as recipe_kind,
           m.kind, m.day, m.slot, m.portions, m.status, c.produced_qty, c.batch_item_id,
           r.servings as recipe_servings, r.shelf_life_days, r.freezer_shelf_life_days, r.thawed_shelf_life_days
    from kitchen.planned_meals m
    left join kitchen.recipes r on r.id = m.recipe_id
    left join kitchen.cook_events c on c.meal_id = m.id
"""


class SuggestIn(BaseModel):
    week_start:    date | None = None            # first day of the plan (despite the name); default: today (Berlin)
    days:          int = Field(default=7, ge=1, le=7)
    cook_sessions: int | None = Field(default=None, ge=0, le=3)   # default: 1 for <= 4 days, else 2


class MealIn(BaseModel):
    recipe_id: str | None = None
    day:       date
    kind:      str = "meal"
    slot:      str = "dinner"
    portions:  float | None = Field(default=None, gt=0)


class MealPatch(BaseModel):
    day:       date | None = None
    slot:      str | None = None
    recipe_id: str | None = None
    portions:  float | None = Field(default=None, gt=0)
    status:    str | None = None  # only 'skipped' (from planned)


class AllocationIn(BaseModel):
    location:        Literal["fridge", "freezer"]
    qty:             float = Field(gt=0)
    shelf_life_days: int | None = Field(default=None, ge=0)   # overrides the recipe default for this batch


class CookIn(BaseModel):
    produced_qty:        float | None = Field(default=None, gt=0)
    allocations:         list[AllocationIn] | None = None     # None = all in the fridge (legacy behaviour)
    remember_shelf_life: bool = False                         # store given days as recipe default if it has none


class EatIn(BaseModel):
    portions: float | None = Field(default=None, gt=0)
    batch_id: int | None = None                               # prefer this ready batch (article number of the batch)


class FreezeThawIn(BaseModel):
    expires_at: date                                          # explicit best-before date, never implicit


class ConsumeIn(BaseModel):
    qty:             float = Field(gt=0)
    idempotency_key: str | None = None


class StockLineIn(BaseModel):
    item_id: int   # StorageTracker article number (stable identity); qty is in the article's base unit
    qty:     float = Field(ge=0)


def _expiry_warnings(cur: Any, meals: list[dict[str, Any]], all_batches: list[dict[str, Any]] | None) -> None:
    """Set meal['expiry_warning'] when a planned meal needs a cooked base that is no longer good on its day.

    A base is fine on day D if some stocked batch has expires_at >= D, or a still-planned cooking session of that
    base on/before D yields portions that keep until D (cook day + shelf_life_days). Otherwise: warn if stock or
    a planned cook exists but would be expired; stay silent if there is simply no base at all (shopping reports
    that as missing_bases)."""
    for m in meals:
        m["expiry_warning"] = None
    if all_batches is None:
        return
    batches = [b for b in all_batches if (b["quantity"] or 0) > 0 and st.storage_of(b) == "fridge"]
    cur.execute("select recipe_id, base_recipe_id, name from kitchen.recipe_ingredients where base_recipe_id is not null")
    bases_of: dict[str, list[tuple[str, str]]] = {}
    for r in cur.fetchall():
        bases_of.setdefault(str(r["recipe_id"]), []).append((str(r["base_recipe_id"]), r["name"]))
    cur.execute("select id, shelf_life_days from kitchen.recipes")
    shelf = {str(r["id"]): r["shelf_life_days"] for r in cur.fetchall()}
    for m in meals:
        if m["kind"] != "meal" or m["status"] != "planned" or not m["recipe_id"]:
            continue
        day = m["day"]
        for base_id, name in bases_of.get(str(m["recipe_id"]), []):
            stock = [b for b in batches if b.get("recipe_ref") == base_id]
            cooks = [c for c in meals if c["kind"] == "cook" and c["status"] == "planned"
                     and str(c["recipe_id"]) == base_id and c["day"] <= day]
            def cook_exp(c: dict[str, Any]) -> Any:
                return None if shelf.get(base_id) is None else c["day"] + timedelta(days=shelf[base_id])
            if any(not b.get("expires_at") or b["expires_at"] >= day.isoformat() for b in stock):
                continue
            if any(cook_exp(c) is None or cook_exp(c) >= day for c in cooks):
                continue
            if cooks:
                m["expiry_warning"] = f"{name} cooked on {cooks[-1]['day']} keeps until {cook_exp(cooks[-1])}, before this meal"
            elif stock:
                m["expiry_warning"] = f"{name} in stock expires {max(b['expires_at'] for b in stock)}, before this meal"
            break


def _base_availability(cur: Any, meals: list[dict[str, Any]], all_batches: list[dict[str, Any]] | None) -> None:
    """meal['bases'] for planned meals that use cooked bases, one entry per base:
    ready (fridge, not expired) / will_be_cooked (a planned cook covers it) / needs_thaw (only frozen portions
    would complete it) / missing (no prepared portions in stock). Raw-ingredient fallback is a later enhancement."""
    for m in meals:
        m["bases"] = []
    if all_batches is None:
        return
    today = berlin_today().isoformat()
    cur.execute("select recipe_id, base_recipe_id, name, qty from kitchen.recipe_ingredients "
                "where base_recipe_id is not null")
    lines: dict[str, list[dict[str, Any]]] = {}
    for r in cur.fetchall():
        lines.setdefault(str(r["recipe_id"]), []).append(dict(r))
    for m in meals:
        if m["kind"] != "meal" or m["status"] != "planned" or not m["recipe_id"]:
            continue
        scale = float(m["portions"]) / float(m["recipe_servings"])
        for ln in lines.get(str(m["recipe_id"]), []):
            base_id = str(ln["base_recipe_id"])
            mine = [b for b in all_batches if b.get("recipe_ref") == base_id and (b["quantity"] or 0) > 0
                    and not st.is_expired(b, today)]
            ready = sum(float(b["quantity"]) for b in mine if st.storage_of(b) == "fridge")
            frozen = sum(float(b["quantity"]) for b in mine if st.storage_of(b) == "freezer")
            planned = sum(float(c["portions"]) for c in meals if c["kind"] == "cook" and c["status"] == "planned"
                          and str(c["recipe_id"]) == base_id and c["day"] <= m["day"])
            needed = float(ln["qty"]) * scale
            status = ("ready" if ready + 1e-9 >= needed else
                      "will_be_cooked" if ready + planned + 1e-9 >= needed else
                      "needs_thaw" if ready + planned + frozen + 1e-9 >= needed and frozen > 0 else "missing")
            m["bases"].append({"base_recipe_id": base_id, "name": ln["name"], "needed": round(needed, 4), "ready": round(ready, 4),
                               "frozen": round(frozen, 4), "planned_cook": round(planned, 4), "status": status})


def _plan_payload(cur: Any, plan_id: str) -> dict[str, Any] | None:
    cur.execute("select id, week_start, days from kitchen.plans where id = %s", (plan_id,))
    p = cur.fetchone()
    if not p:
        return None
    cur.execute(MEAL_SELECT + " where m.plan_id = %s order by m.day, m.slot, m.created_at", (plan_id,))
    meals = [dict(m) for m in cur.fetchall()]
    try:
        all_batches = st.list_items(kind="batch")
    except st.StorageError:
        all_batches = None
    _expiry_warnings(cur, meals, all_batches)
    _base_availability(cur, meals, all_batches)
    return {"id": str(p["id"]), "week_start": p["week_start"], "days": p["days"], "meals": meals}


def _meal_row(cur: Any, meal_id: str) -> dict[str, Any] | None:
    cur.execute(MEAL_SELECT + " where m.id = %s", (meal_id,))
    r = cur.fetchone()
    return dict(r) if r else None


@router.get("/plans", response_model=None)
def list_plans() -> JSONResponse:
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("select id, week_start, days from kitchen.plans order by created_at desc limit 20")
        rows = [dict(r) for r in cur.fetchall()]
    return dataset_response("plan", rows, "Plans")


@router.get("/plans/{plan_id}", response_model=None)
def get_plan(plan_id: str) -> JSONResponse:
    with get_db() as conn, conn.cursor() as cur:
        p = _plan_payload(cur, plan_id)
    if not p:
        return api_error("NOT_FOUND", f"Plan {plan_id} not found", status=404)
    return dataset_response("plan", [p], "Plan")


@router.post("/plans/suggest", response_model=None)
def suggest(body: SuggestIn) -> JSONResponse:
    start = body.week_start or berlin_today()
    with get_db() as conn:
        plan_id = service.suggest_plan(conn, start, body.cook_sessions, body.days)
        with conn.cursor() as cur:
            p = _plan_payload(cur, plan_id)
    return dataset_response("plan", [p], "Plan", status=201)


@router.post("/plans/{plan_id}/meals", response_model=None)
def add_meal(plan_id: str, body: MealIn) -> JSONResponse:
    if body.kind not in ("cook", "meal"):
        return api_error("VALIDATION_ERROR", "kind must be 'cook' or 'meal'")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select 1 from kitchen.plans where id = %s", (plan_id,))
            if not cur.fetchone():
                return api_error("NOT_FOUND", f"Plan {plan_id} not found", status=404)
            portions = body.portions
            if body.recipe_id:
                cur.execute("select servings, status from kitchen.recipes where id = %s", (body.recipe_id,))
                rec = cur.fetchone()
                if not rec:
                    return api_error("VALIDATION_ERROR", "recipe_id unknown")
                if rec["status"] != "active":
                    return api_error("CONFLICT", "Recipe is a draft: assign all ingredients to articles first",
                                     status=409)
                portions = portions or float(rec["servings"])
            cur.execute(
                """insert into kitchen.planned_meals (plan_id, recipe_id, kind, day, slot, portions)
                   values (%s, %s, %s, %s, %s, %s) returning id""",
                (plan_id, body.recipe_id, body.kind, body.day, body.slot, portions or 1))
            row = _meal_row(cur, str(cur.fetchone()["id"]))
        conn.commit()
    return dataset_response("meal", [row], "Meal", status=201)


@router.patch("/meals/{meal_id}", response_model=None)
def patch_meal(meal_id: str, body: MealPatch) -> JSONResponse:
    """Move / swap / re-portion / skip a planned meal. Pure plan edit: never touches stock."""
    fields = body.model_fields_set
    if not fields:
        return api_error("VALIDATION_ERROR", "No fields provided for update")
    if body.status is not None and body.status != "skipped":
        return api_error("VALIDATION_ERROR", "status can only be set to 'skipped'")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select status from kitchen.planned_meals where id = %s for update", (meal_id,))
            cur_row = cur.fetchone()
            if not cur_row:
                return api_error("NOT_FOUND", f"Meal {meal_id} not found", status=404)
            if cur_row["status"] != "planned":
                return api_error("CONFLICT", f"Meal is {cur_row['status']}; undo first", status=409)
            if body.recipe_id:
                cur.execute("select status from kitchen.recipes where id = %s", (body.recipe_id,))
                rec = cur.fetchone()
                if not rec:
                    return api_error("VALIDATION_ERROR", "recipe_id unknown")
                if rec["status"] != "active":
                    return api_error("CONFLICT", "Recipe is a draft: assign all ingredients to articles first",
                                     status=409)
            sets, params = ["updated_at = now()"], []
            for f in ("day", "slot", "recipe_id", "portions", "status"):
                if f in fields:
                    sets.append(f"{f} = %s")
                    params.append(getattr(body, f))
            cur.execute(f"update kitchen.planned_meals set {', '.join(sets)} where id = %s", (*params, meal_id))
            row = _meal_row(cur, meal_id)
        conn.commit()
    return dataset_response("meal", [row], "Meal")


@router.delete("/meals/{meal_id}", response_model=None)
def delete_meal(meal_id: str) -> JSONResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from kitchen.planned_meals where id = %s and status = 'planned' returning id",
                        (meal_id,))
            if not cur.fetchone():
                return api_error("CONFLICT", "Meal not found or not in status planned", status=409)
        conn.commit()
    return JSONResponse(status_code=200, content={"deleted": True})


def _run(fn) -> JSONResponse:
    """Run a booking action (fn(conn) -> dict) and map domain errors to ApiError."""
    with get_db() as conn:
        try:
            result = fn(conn)
        except LookupError:
            return api_error("NOT_FOUND", "Meal not found", status=404)
        except service.Conflict as e:
            conn.rollback()
            return api_error("CONFLICT", str(e), status=409)
        except service.ShelfLifeRequired as e:
            conn.rollback()
            return api_error("SHELF_LIFE_REQUIRED", str(e), status=422)
        except ValueError as e:
            conn.rollback()
            return api_error("VALIDATION_ERROR", str(e))
        except st.StorageError as e:
            conn.rollback()
            return api_error("STORAGE_UNAVAILABLE", str(e), status=502)
        with conn.cursor() as cur:
            result["meal"] = _meal_row(cur, result["meal_id"])
    return JSONResponse(status_code=200, content=plain(result))


@router.post("/meals/{meal_id}/cooked", response_model=None)
def cooked(meal_id: str, body: CookIn | None = None) -> JSONResponse:
    allocations = [a.model_dump() for a in body.allocations] if body and body.allocations is not None else None
    return _run(lambda c: {**service.cook(c, meal_id, body.produced_qty if body else None, allocations,
                                          bool(body and body.remember_shelf_life)), "meal_id": meal_id})


@router.post("/meals/{meal_id}/eaten", response_model=None)
def eaten(meal_id: str, body: EatIn | None = None) -> JSONResponse:
    return _run(lambda c: {**service.eat(c, meal_id, body.portions if body else None,
                                         body.batch_id if body else None), "meal_id": meal_id})


@router.post("/meals/{meal_id}/undo", response_model=None)
def undo(meal_id: str) -> JSONResponse:
    return _run(lambda c: {**service.undo(c, meal_id), "meal_id": meal_id})


# ── shopping ──────────────────────────────────────────────────────────────────

@router.get("/plans/{plan_id}/shopping", response_model=None)
def shopping(plan_id: str) -> JSONResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select 1 from kitchen.plans where id = %s", (plan_id,))
            if not cur.fetchone():
                return api_error("NOT_FOUND", f"Plan {plan_id} not found", status=404)
        try:
            data = service.compute_shopping(conn, plan_id)
        except st.StorageError as e:
            return api_error("STORAGE_UNAVAILABLE", str(e), status=502)
    return dataset_response("shopping", [data], "Shopping")


@router.post("/shopping/stocktake", response_model=None)
def stocktake(body: StockLineIn) -> JSONResponse:
    """User confirms/corrects the real amount on hand: books the difference as a 'stocktake' movement."""
    try:
        item = st.get_item(body.item_id)
        if not item:
            return api_error("NOT_FOUND", f"Article {body.item_id} not found", status=404)
        delta = body.qty - float(item["quantity"] or 0)
        if abs(delta) > 1e-9:
            st.post_movement(item["id"], delta, "stocktake", f"stocktake:{uuid.uuid4()}")
    except st.StorageError as e:
        return api_error("STORAGE_UNAVAILABLE", str(e), status=502)
    return JSONResponse(status_code=200, content={"item_id": item["id"], "quantity": body.qty})


class PurchaseIn(StockLineIn):
    idempotency_key: str | None = None


@router.post("/shopping/purchase", response_model=None)
def purchase(body: PurchaseIn) -> JSONResponse:
    """Confirmed purchase: adds `qty` to stock. Pass idempotency_key to make a retry safe."""
    if body.qty <= 0:
        return api_error("VALIDATION_ERROR", "qty must be > 0")
    try:
        item = st.get_item(body.item_id)
        if not item:
            return api_error("NOT_FOUND", f"Article {body.item_id} not found", status=404)
        res = st.post_movement(item["id"], body.qty, "purchase", body.idempotency_key or f"purchase:{uuid.uuid4()}")
    except st.StorageError as e:
        return api_error("STORAGE_UNAVAILABLE", str(e), status=502)
    return JSONResponse(status_code=200, content={"item_id": item["id"], "quantity": res["quantity"],
                                                  "replayed": res["replayed"]})


def _batch_row(b: dict[str, Any], recipes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    r = recipes.get(b.get("recipe_ref") or "", {})
    today = berlin_today()

    def plus(days: int | None) -> str | None:
        return (today + timedelta(days=days)).isoformat() if days is not None else None

    storage = st.storage_of(b)
    return {"id": b["id"], "name": b["name"], "recipe_id": b.get("recipe_ref"), "quantity": b["quantity"],
            "unit": b.get("unit"), "location": b.get("location"), "storage": storage,
            "expires_at": b.get("expires_at"), "expiry_status": b.get("expiry_status"),
            "produced_at": b.get("produced_at"),
            # policy-derived suggestions for the explicit freeze / thaw date (the user confirms or edits them)
            "suggested_freeze_expires_at": plus(r.get("freezer_shelf_life_days")) if storage == "fridge" else None,
            "suggested_thaw_expires_at": plus(r.get("thawed_shelf_life_days")) if storage == "freezer" else None}


@router.get("/batches", response_model=None)
def batches() -> JSONResponse:
    """Prepared batches with remaining portions (read from StorageTracker, the stock authority).
    Active inventory only: depleted batches are archived there and stay available in its history."""
    try:
        items = [b for b in st.list_items(kind="batch") if (b["quantity"] or 0) > 0]
    except st.StorageError as e:
        return api_error("STORAGE_UNAVAILABLE", str(e), status=502)
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("select id, freezer_shelf_life_days, thawed_shelf_life_days from kitchen.recipes")
        recipes = {str(r["id"]): dict(r) for r in cur.fetchall()}
    rows = [_batch_row(b, recipes) for b in sorted(items, key=lambda b: (b.get("expires_at") or "9999-12-31"))]
    return dataset_response("batch", rows, "Batches")


def _relocate(item_id: int, event: str, body: FreezeThawIn) -> JSONResponse:
    """freeze: fridge -> freezer, thaw: freezer -> fridge; always with the user's explicit best-before date."""
    try:
        item = st.get_item(item_id)
        if not item or item.get("kind") != "batch":
            return api_error("NOT_FOUND", f"Batch {item_id} not found", status=404)
        want_from = "fridge" if event == "freeze" else "freezer"
        if st.storage_of(item) != want_from:
            return api_error("CONFLICT", f"Batch is already in the {st.storage_of(item)}", status=409)
        if st.is_expired(item, berlin_today().isoformat()):
            return api_error("CONFLICT", "Batch is expired: discard it instead", status=409)
        row = st.relocate(item_id, st.location_label("freezer" if event == "freeze" else "fridge"), event,
                          body.expires_at.isoformat())
    except st.StorageError as e:
        return api_error("STORAGE_UNAVAILABLE", str(e), status=502)
    return dataset_response("batch", [{"id": row["id"], "location": row["location"], "storage": st.storage_of(row),
                                       "expires_at": row["expires_at"], "quantity": row["quantity"]}], "Batch")


@router.post("/batches/{item_id}/freeze", response_model=None)
def freeze_batch(item_id: int, body: FreezeThawIn) -> JSONResponse:
    return _relocate(item_id, "freeze", body)


@router.post("/batches/{item_id}/thaw", response_model=None)
def thaw_batch(item_id: int, body: FreezeThawIn) -> JSONResponse:
    return _relocate(item_id, "thaw", body)


@router.post("/batches/{item_id}/consume", response_model=None)
def consume_batch(item_id: int, body: ConsumeIn) -> JSONResponse:
    """Take portions from one specific batch without a planned meal (leftovers, a snack, ...)."""
    try:
        item = st.get_item(item_id)
        if not item or item.get("kind") != "batch":
            return api_error("NOT_FOUND", f"Batch {item_id} not found", status=404)
        if st.storage_of(item) == "freezer":
            return api_error("CONFLICT", "Batch is frozen: thaw it first", status=409)
        if st.is_expired(item, berlin_today().isoformat()):
            return api_error("CONFLICT", "Batch is expired: discard it instead", status=409)
        if body.qty > float(item["quantity"] or 0) + 1e-9:
            return api_error("CONFLICT", f"Only {item['quantity']} left in this batch", status=409)
        res = st.post_movement(item_id, -body.qty, "consumed", body.idempotency_key or f"consume:{uuid.uuid4()}")
    except st.StorageError as e:
        return api_error("STORAGE_UNAVAILABLE", str(e), status=502)
    return JSONResponse(status_code=200, content={"item_id": item_id, "quantity": res["quantity"],
                                                  "replayed": res["replayed"]})


@router.post("/batches/{item_id}/discard", response_model=None)
def discard_expired_batch(item_id: int) -> JSONResponse:
    """User-confirmed removal of an EXPIRED batch: books -quantity as an 'expired' ledger movement (reversible).
    Same idempotency key as the StorageTracker UI, so confirming in both places cannot double-book."""
    try:
        item = st.get_item(item_id)
        if not item or item.get("kind") != "batch":
            return api_error("NOT_FOUND", f"Batch {item_id} not found", status=404)
        if item.get("expiry_status") != "expired":
            return api_error("CONFLICT", "Only expired batches can be discarded here", status=409)
        res = st.post_movement(item_id, -float(item["quantity"]), "expired", f"expired:{item_id}:{item['expires_at']}")
    except st.StorageError as e:
        return api_error("STORAGE_UNAVAILABLE", str(e), status=502)
    return JSONResponse(status_code=200, content={"item_id": item_id, "quantity": res["quantity"],
                                                  "replayed": res["replayed"]})
