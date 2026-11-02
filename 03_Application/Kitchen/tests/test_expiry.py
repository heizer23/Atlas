"""Expiry: earliest-first consumption, expired batches are never auto-consumed, planner respects shelf life,
warnings on meals, user-confirmed discard."""
import os
from datetime import timedelta

import httpx

from backend.common import berlin_today

ST = os.environ.get("STORAGETRACKER_URL", "http://atlas-storagetracker-test:8000") + "/api"
K = "/api/kitchen"


def rid(client, name):
    return next(r["id"] for r in client.get(f"{K}/recipes").json()["rows"] if r["name"] == name)


def batch(client, qty, days, name="Dal batch"):
    d = berlin_today() + timedelta(days=days)
    r = httpx.post(f"{ST}/items", json={"name": name, "item_type": "consumable", "kind": "batch", "quantity": qty,
                                        "unit": "portions", "recipe_ref": rid(client, "Dal"),
                                        "expires_at": d.isoformat()})
    assert r.status_code == 200, r.text
    return r.json()["rows"][0]


def qty(item_id):
    return httpx.get(f"{ST}/items/{item_id}").json()["rows"][0]["quantity"]


def plan_with_meals(client, meals, week_start=None):
    ws = (week_start or berlin_today()).isoformat()
    plan = client.post(f"{K}/plans/suggest", json={"week_start": ws, "cook_sessions": 0}).json()["rows"][0]
    for m in plan["meals"]:
        client.delete(f"{K}/meals/{m['id']}")
    ids = []
    for recipe, day_offset, kind in meals:
        day = ((week_start or berlin_today()) + timedelta(days=day_offset)).isoformat()
        r = client.post(f"{K}/plans/{plan['id']}/meals", json={"recipe_id": rid(client, recipe), "day": day, "kind": kind})
        ids.append(r.json()["rows"][0]["id"])
    return plan["id"], ids


def test_eat_takes_earliest_expiry_first_and_never_touches_expired(client):
    expired = batch(client, 3, -1, "Expired dal")
    late = batch(client, 4, 5, "Late dal")
    early = batch(client, 2, 1, "Early dal")
    _, (m1, m2, m3) = plan_with_meals(client, [("Dal with Eggs and Spinach", 0, "meal"),
                                               ("Dal with Chicken and Spinach", 1, "meal"),
                                               ("Dal with Eggs and Spinach", 2, "meal")])
    assert client.post(f"{K}/meals/{m1}/eaten").status_code == 200
    assert (qty(early["id"]), qty(late["id"]), qty(expired["id"])) == (0, 4, 3)
    assert client.post(f"{K}/meals/{m2}/eaten").status_code == 200
    assert (qty(late["id"]), qty(expired["id"])) == (2, 3)
    assert client.post(f"{K}/meals/{m3}/eaten").status_code == 200
    assert (qty(late["id"]), qty(expired["id"])) == (0, 3)


def test_only_expired_left_reports_shortfall_and_books_nothing(client):
    expired = batch(client, 3, -2)
    _, (m,) = plan_with_meals(client, [("Dal with Eggs and Spinach", 0, "meal")])
    r = client.post(f"{K}/meals/{m}/eaten").json()
    assert r["shortfall"][0]["missing"] == 2 and r["shortfall"][0]["expired_in_stock"] == 3
    assert qty(expired["id"]) == 3


def test_discard_requires_expired_and_is_idempotent_with_storage_ui(client):
    expired = batch(client, 3, -1)
    fresh = batch(client, 2, 4)
    assert client.post(f"{K}/batches/{fresh['id']}/discard").status_code == 409
    r = client.post(f"{K}/batches/{expired['id']}/discard")
    assert r.status_code == 200 and r.json()["quantity"] == 0
    mv = httpx.get(f"{ST}/items/{expired['id']}/movements").json()["rows"]
    assert len(mv) == 1 and mv[0]["reason"] == "expired"
    # the StorageTracker UI uses the same key: confirming there afterwards is a replay, not a second booking
    again = httpx.post(f"{ST}/items/{expired['id']}/movements", json={
        "delta": -3, "reason": "expired", "idempotency_key": f"expired:{expired['id']}:{expired['expires_at']}"})
    assert again.status_code == 200 and again.json()["replayed"] is True


def test_batches_list_exposes_expiry(client):
    batch(client, 3, -1, "Gone")
    batch(client, 2, 1, "Soon")
    batch(client, 2, 9, "Later")
    rows = client.get(f"{K}/batches").json()["rows"]
    assert [r["name"] for r in rows] == ["Gone", "Soon", "Later"]
    assert [r["expiry_status"] for r in rows] == ["expired", "expiring_soon", None]


def test_plan_warns_when_stock_expires_before_meal(client):
    batch(client, 6, 1)
    pid, (m_ok, m_late) = plan_with_meals(client, [("Dal with Eggs and Spinach", 1, "meal"),
                                                   ("Dal with Chicken and Spinach", 3, "meal")])
    meals = {m["id"]: m for m in client.get(f"{K}/plans/{pid}").json()["rows"][0]["meals"]}
    assert meals[m_ok]["expiry_warning"] is None
    assert "expires" in meals[m_late]["expiry_warning"] and "before this meal" in meals[m_late]["expiry_warning"]


def test_planned_cook_covers_meal_within_shelf_life_only(client):
    # Dal shelf life is 4 days: cooked on day 0 it keeps until day 4
    pid, (cook, ok, late) = plan_with_meals(client, [("Dal", 0, "cook"),
                                                     ("Dal with Eggs and Spinach", 3, "meal"),
                                                     ("Dal with Chicken and Spinach", 5, "meal")])
    meals = {m["id"]: m for m in client.get(f"{K}/plans/{pid}").json()["rows"][0]["meals"]}
    assert meals[ok]["expiry_warning"] is None
    assert "keeps until" in meals[late]["expiry_warning"]


def test_suggest_only_plans_dal_meals_while_stock_is_good(client):
    batch(client, 6, 1)  # good through tomorrow
    ws = berlin_today()
    plan = client.post(f"{K}/plans/suggest", json={"week_start": ws.isoformat(), "cook_sessions": 0}).json()["rows"][0]
    dal_meals = [m for m in plan["meals"] if m["recipe_name"] and m["recipe_name"].startswith("Dal with")]
    assert dal_meals and all(m["day"] <= (ws + timedelta(days=1)).isoformat() for m in dal_meals)


def test_suggest_with_cook_respects_shelf_life(client):
    ws = berlin_today()
    plan = client.post(f"{K}/plans/suggest", json={"week_start": ws.isoformat()}).json()["rows"][0]
    cooks = {m["recipe_name"]: m["day"] for m in plan["meals"] if m["kind"] == "cook"}
    for m in plan["meals"]:
        if m["recipe_name"] == "Dal with Eggs and Spinach" or m["recipe_name"] == "Dal with Chicken and Spinach":
            assert m["expiry_warning"] is None
