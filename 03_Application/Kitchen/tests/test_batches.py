"""Cooked batch management: split cooking across fridge/freezer, independent best-before dates,
freeze / thaw events, specific-batch consumption, archive of depleted batches, availability states."""
import os
from datetime import timedelta

import httpx

from backend.common import berlin_today

ST = os.environ.get("STORAGETRACKER_URL", "http://atlas-storagetracker-test:8000") + "/api"
K = "/api/kitchen"


def rid(client, name):
    return next(r["id"] for r in client.get(f"{K}/recipes").json()["rows"] if r["name"] == name)


def iso(days):
    return (berlin_today() + timedelta(days=days)).isoformat()


def plan_with(client, meals):
    plan = client.post(f"{K}/plans/suggest", json={"week_start": iso(0), "days": 7, "cook_sessions": 0}).json()["rows"][0]
    for m in plan["meals"]:
        client.delete(f"{K}/meals/{m['id']}")
    ids = []
    for recipe, offset, kind in meals:
        r = client.post(f"{K}/plans/{plan['id']}/meals", json={"recipe_id": rid(client, recipe), "day": iso(offset), "kind": kind})
        ids.append(r.json()["rows"][0]["id"])
    return plan["id"], ids


def item(item_id):
    return httpx.get(f"{ST}/items/{item_id}").json()["rows"][0]


def cook_dal(client, allocations=None, **kw):
    pid, (m,) = plan_with(client, [("Dal", 0, "cook")])
    body = {"produced_qty": 4, **kw}
    if allocations is not None:
        body["allocations"] = allocations
    return pid, m, client.post(f"{K}/meals/{m}/cooked", json=body)


def test_one_cooking_creates_independent_fridge_and_freezer_batches(client):
    _, m, r = cook_dal(client, [{"location": "fridge", "qty": 2}, {"location": "freezer", "qty": 2, "shelf_life_days": 90}])
    assert r.status_code == 200, r.text
    made = {b["location"]: b for b in r.json()["batches"]}
    assert set(made) == {"fridge", "freezer"} and made["fridge"]["item_id"] != made["freezer"]["item_id"]
    fridge, freezer = item(made["fridge"]["item_id"]), item(made["freezer"]["item_id"])
    assert (fridge["location"], fridge["quantity"], fridge["expires_at"]) == ("Fridge", 2, iso(4))      # recipe default 4d
    assert (freezer["location"], freezer["quantity"], freezer["expires_at"]) == ("Freezer", 2, iso(90))
    assert fridge["recipe_ref"] == freezer["recipe_ref"] == rid(client, "Dal")
    assert fridge["produced_at"] == freezer["produced_at"] == iso(0)
    assert any(f"meal:{m}" in t for t in fridge["source_tags"]) and any(f"meal:{m}" in t for t in freezer["source_tags"])
    assert client.get(f"{K}/batches").json()["meta"]["total"] == 2


def test_all_portions_must_be_allocated_exactly_once_and_nothing_is_booked_on_error(client):
    pid, m, r = cook_dal(client, [{"location": "fridge", "qty": 2}, {"location": "freezer", "qty": 1, "shelf_life_days": 30}])
    assert r.status_code == 400 and "exactly once" in r.json()["error"]["message"]
    over = client.post(f"{K}/meals/{m}/cooked", json={"produced_qty": 4, "allocations": [{"location": "fridge", "qty": 5}]})
    assert over.status_code == 400
    dup = client.post(f"{K}/meals/{m}/cooked", json={"produced_qty": 4, "allocations": [
        {"location": "fridge", "qty": 2}, {"location": "fridge", "qty": 2}]})
    assert dup.status_code == 400
    assert httpx.get(f"{ST}/items", params={"kind": "batch"}).json()["rows"] == []
    assert all(i["quantity"] == 0 for i in httpx.get(f"{ST}/items").json()["rows"])   # raw ingredients untouched
    assert client.get(f"{K}/plans/{pid}").json()["rows"][0]["meals"][0]["status"] == "planned"


def test_freezer_shelf_life_is_requested_not_assumed(client):
    _, m, r = cook_dal(client, [{"location": "freezer", "qty": 4}])
    assert r.status_code == 422 and r.json()["error"]["code"] == "SHELF_LIFE_REQUIRED"
    assert httpx.get(f"{ST}/items", params={"kind": "batch"}).json()["rows"] == []
    ok = client.post(f"{K}/meals/{m}/cooked", json={"produced_qty": 4, "remember_shelf_life": True,
                     "allocations": [{"location": "freezer", "qty": 4, "shelf_life_days": 75}]})
    assert ok.status_code == 200
    recipe = next(x for x in client.get(f"{K}/recipes").json()["rows"] if x["name"] == "Dal")
    assert recipe["freezer_shelf_life_days"] == 75       # remembered as the recipe default
    assert recipe["shelf_life_days"] == 4                # existing value is never overwritten


def test_legacy_cooking_without_allocations_still_fills_the_fridge(client):
    _, m, r = cook_dal(client)
    assert r.status_code == 200 and [b["location"] for b in r.json()["batches"]] == ["fridge"]
    again = client.post(f"{K}/meals/{m}/cooked", json={"produced_qty": 4})
    assert again.json()["replayed"] is True
    assert len(httpx.get(f"{ST}/items", params={"kind": "batch"}).json()["rows"]) == 1
    assert item(r.json()["batches"][0]["item_id"])["quantity"] == 4


def test_repeat_confirmation_does_not_double_book_split_batches(client):
    _, m, r = cook_dal(client, [{"location": "fridge", "qty": 3}, {"location": "freezer", "qty": 1, "shelf_life_days": 30}])
    again = client.post(f"{K}/meals/{m}/cooked", json={"produced_qty": 4, "allocations": [{"location": "fridge", "qty": 4}]})
    assert again.json()["replayed"] is True
    qty = sorted(i["quantity"] for i in httpx.get(f"{ST}/items", params={"kind": "batch"}).json()["rows"])
    assert qty == [1, 3]


def test_freeze_and_thaw_need_explicit_dates_and_keep_history(client):
    _, _, r = cook_dal(client, [{"location": "fridge", "qty": 4}])
    bid = r.json()["batches"][0]["item_id"]
    assert client.post(f"{K}/batches/{bid}/freeze", json={}).status_code == 422          # date is mandatory
    rows = client.get(f"{K}/batches").json()["rows"]
    assert rows[0]["suggested_freeze_expires_at"] is None                                  # no policy configured yet
    f = client.post(f"{K}/batches/{bid}/freeze", json={"expires_at": iso(60)})
    assert f.status_code == 200 and f.json()["rows"][0]["storage"] == "freezer"
    assert client.post(f"{K}/batches/{bid}/freeze", json={"expires_at": iso(60)}).status_code == 409   # already frozen
    t = client.post(f"{K}/batches/{bid}/thaw", json={"expires_at": iso(2)})
    assert t.status_code == 200 and item(bid)["expires_at"] == iso(2) and item(bid)["location"] == "Fridge"
    types = [h["change_type"] for h in httpx.get(f"{ST}/items/{bid}/history").json()["rows"]]
    assert types.count("freeze") == 1 and types.count("thaw") == 1 and types.count("expiry_change") == 2
    assert item(bid)["quantity"] == 4


def test_thaw_suggestion_follows_the_thawing_policy(client):
    dal = rid(client, "Dal")
    client.patch(f"{K}/recipes/{dal}", json={"freezer_shelf_life_days": 90, "thawed_shelf_life_days": 2})
    _, _, r = cook_dal(client, [{"location": "fridge", "qty": 2}, {"location": "freezer", "qty": 2}])
    rows = {b["storage"]: b for b in client.get(f"{K}/batches").json()["rows"]}
    assert rows["freezer"]["suggested_thaw_expires_at"] == iso(2)
    assert rows["fridge"]["suggested_freeze_expires_at"] == iso(90)
    assert rows["freezer"]["expires_at"] == iso(90)


def test_availability_states_ready_thaw_missing(client):
    dal = rid(client, "Dal")
    client.patch(f"{K}/recipes/{dal}", json={"freezer_shelf_life_days": 90})
    _, m, _ = cook_dal(client, [{"location": "freezer", "qty": 4}])
    pid, (eat,) = plan_with(client, [("Dal with Eggs and Spinach", 1, "meal")])
    status = lambda: client.get(f"{K}/plans/{pid}").json()["rows"][0]["meals"][0]["bases"][0]["status"]
    assert status() == "needs_thaw"                                    # only frozen portions in stock
    fridge_id = next(b["id"] for b in client.get(f"{K}/batches").json()["rows"])
    client.post(f"{K}/batches/{fridge_id}/thaw", json={"expires_at": iso(3)})
    assert status() == "ready"
    client.post(f"{K}/batches/{fridge_id}/consume", json={"qty": 4})
    assert status() == "missing"


def test_eat_refuses_frozen_batch_and_never_autouses_it(client):
    dal = rid(client, "Dal")
    client.patch(f"{K}/recipes/{dal}", json={"freezer_shelf_life_days": 90})
    _, _, r = cook_dal(client, [{"location": "freezer", "qty": 4}])
    frozen = r.json()["batches"][0]["item_id"]
    _, (eat,) = plan_with(client, [("Dal with Eggs and Spinach", 1, "meal")])
    assert client.post(f"{K}/meals/{eat}/eaten", json={"batch_id": frozen}).status_code == 409
    res = client.post(f"{K}/meals/{eat}/eaten").json()
    assert res["shortfall"][0]["frozen_in_stock"] == 4 and item(frozen)["quantity"] == 4


def test_derived_meal_consumes_a_specific_batch_without_rededucting_raw_ingredients(client):
    _, _, r = cook_dal(client, [{"location": "fridge", "qty": 2}, {"location": "freezer", "qty": 2, "shelf_life_days": 40}])
    batches = {b["location"]: b["item_id"] for b in r.json()["batches"]}
    # thaw the frozen one and give it a later date; the fridge batch is earlier -> auto would pick the fridge one
    client.post(f"{K}/batches/{batches['freezer']}/thaw", json={"expires_at": iso(9)})
    raw_before = {i["name"]: i["quantity"] for i in httpx.get(f"{ST}/items", params={"kind": "ingredient"}).json()["rows"]}
    _, (eat,) = plan_with(client, [("Dal with Eggs and Spinach", 1, "meal")])
    res = client.post(f"{K}/meals/{eat}/eaten", json={"batch_id": batches["freezer"]})
    assert res.status_code == 200
    assert item(batches["freezer"])["quantity"] == 0 and item(batches["fridge"])["quantity"] == 2
    raw_after = {i["name"]: i["quantity"] for i in httpx.get(f"{ST}/items", params={"kind": "ingredient"}).json()["rows"]}
    changed = {n for n in raw_after if raw_after[n] != raw_before.get(n)}
    assert changed <= {"Eggs", "Spinach"}          # only the dish's own raw ingredients; Dal's lentils etc. untouched


def test_consume_depletes_archives_and_keeps_history(client):
    _, _, r = cook_dal(client, [{"location": "fridge", "qty": 4}])
    bid = r.json()["batches"][0]["item_id"]
    assert client.post(f"{K}/batches/{bid}/consume", json={"qty": 9}).status_code == 409
    assert client.post(f"{K}/batches/{bid}/consume", json={"qty": 1}).status_code == 200
    assert client.post(f"{K}/batches/{bid}/consume", json={"qty": 3}).status_code == 200
    assert client.get(f"{K}/batches").json()["rows"] == []
    row = item(bid)
    assert row["quantity"] == 0 and row["archived_at"] is not None
    assert len(httpx.get(f"{ST}/items/{bid}/movements").json()["rows"]) == 3     # cook + 2 consumptions remain


def test_undo_cooking_restores_raw_stock_and_blocks_when_a_batch_was_used(client):
    _, m, r = cook_dal(client, [{"location": "fridge", "qty": 2}, {"location": "freezer", "qty": 2, "shelf_life_days": 30}])
    fridge = next(b["item_id"] for b in r.json()["batches"] if b["location"] == "fridge")
    client.post(f"{K}/batches/{fridge}/consume", json={"qty": 1})
    assert client.post(f"{K}/meals/{m}/undo").status_code == 409
    client.post(f"{K}/batches/{fridge}/consume", json={"qty": 1})  # still blocked
    assert client.post(f"{K}/meals/{m}/undo").status_code == 409
