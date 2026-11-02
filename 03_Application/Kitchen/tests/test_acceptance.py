"""Sprint01 acceptance flow (Vision §7, criteria 1-9) against real StorageTracker on atlas_test."""
import os

import httpx

ST = os.environ.get("STORAGETRACKER_URL", "http://atlas-storagetracker-test:8000") + "/api"


def item_id(name):
    rows = httpx.get(f"{ST}/items", params={"kind": "ingredient"}).json()["rows"]
    return next(r["id"] for r in rows if r["name"].lower() == name.lower())


def buy(client, name, qty):
    return client.post("/api/kitchen/shopping/purchase", json={"item_id": item_id(name), "qty": qty})


def stock(name, unit=None):
    rows = httpx.get(f"{ST}/items").json()["rows"]
    return sum(r["quantity"] or 0 for r in rows if r["name"].lower() == name.lower())


def batches():
    return httpx.get(f"{ST}/items", params={"kind": "batch"}).json()["rows"]


def recipe_id(client, name):
    rows = client.get("/api/kitchen/recipes").json()["rows"]
    return next(r["id"] for r in rows if r["name"] == name)


def add_meal(client, plan_id, recipe, day, kind="meal", portions=None):
    r = client.post(f"/api/kitchen/plans/{plan_id}/meals",
                    json={"recipe_id": recipe_id(client, recipe), "day": day, "kind": kind, "portions": portions})
    assert r.status_code == 201, r.text
    return r.json()["rows"][0]["id"]


def new_plan(client):
    r = client.post("/api/kitchen/plans/suggest", json={"week_start": "2030-01-07", "cook_sessions": 0})
    assert r.status_code == 201, r.text
    plan = r.json()["rows"][0]
    for m in plan["meals"]:
        client.delete(f"/api/kitchen/meals/{m['id']}")
    return plan["id"]


def test_full_flow(client):
    # 1 plan with Dal + Bolognese as bases, derived meals
    pid = new_plan(client)
    cook_dal = add_meal(client, pid, "Dal", "2030-01-07", "cook")
    add_meal(client, pid, "Vegetarian Bolognese", "2030-01-08", "cook")
    m_eggs = add_meal(client, pid, "Dal with Eggs and Spinach", "2030-01-09")
    m_chicken = add_meal(client, pid, "Dal with Chicken and Spinach", "2030-01-10")
    m_moved = add_meal(client, pid, "Spaghetti Bolognese", "2030-01-11")

    # 2 consolidated shopping list; Spinach (2 meals) summed, bases not shopped
    shop = client.get(f"/api/kitchen/plans/{pid}/shopping").json()["rows"][0]
    spinat = next(l for l in shop["buy"] if l["name"] == "Spinach")
    assert spinat["to_buy"] == 400
    assert shop["missing_bases"] == []
    assert not shop["probably_have"]

    # 3 buy + confirm on-hand: lentils 300 g bought; onions "probably have" corrected
    buy(client, "Red lentils", 500)
    client.post("/api/kitchen/shopping/stocktake", json={"item_id": item_id("Onion"), "qty": 6})
    for n, q in [("Garlic", 10), ("Ginger", 100), ("Canned tomatoes", 800), ("Coconut milk", 800),
                 ("Curry powder", 10), ("Olive oil", 20), ("Chicken breast", 300), ("Spinach", 400), ("Eggs", 6)]:
        buy(client, n, q)
    shop = client.get(f"/api/kitchen/plans/{pid}/shopping").json()["rows"][0]
    assert any(l["name"] == "Red lentils" for l in shop["probably_have"])

    # 4/5 cook 6 portions Dal -> batch, raw ingredients backflushed
    r = client.post(f"/api/kitchen/meals/{cook_dal}/cooked", json={"produced_qty": 6})
    assert r.status_code == 200, r.text
    assert stock("Red lentils") == 200 and stock("Onion") == 4 and stock("Coconut milk") == 400
    b = batches()
    assert len(b) == 1 and b[0]["quantity"] == 6 and b[0]["unit"] == "portions"

    # repeat confirm: no double booking
    r2 = client.post(f"/api/kitchen/meals/{cook_dal}/cooked", json={"produced_qty": 6})
    assert r2.json()["replayed"] is True
    assert stock("Red lentils") == 200 and batches()[0]["quantity"] == 6

    # 6/7 eat eggs and chicken Dal
    assert client.post(f"/api/kitchen/meals/{m_eggs}/eaten").status_code == 200
    assert client.post(f"/api/kitchen/meals/{m_chicken}/eaten").status_code == 200
    assert stock("Eggs") == 2 and stock("Chicken breast") == 0 and stock("Spinach") == 0
    # repeat eat: still no double booking
    client.post(f"/api/kitchen/meals/{m_eggs}/eaten")
    # 8 two portions remain
    assert batches()[0]["quantity"] == 2
    left = client.get("/api/kitchen/batches").json()["rows"]
    assert left[0]["quantity"] == 2

    # 9 move a meal: no stock movement
    before = {r["id"]: r["quantity"] for r in httpx.get(f"{ST}/items").json()["rows"]}
    r = client.patch(f"/api/kitchen/meals/{m_moved}", json={"day": "2030-01-13"})
    assert r.status_code == 200 and r.json()["rows"][0]["day"] == "2030-01-13"
    after = {r["id"]: r["quantity"] for r in httpx.get(f"{ST}/items").json()["rows"]}
    assert before == after


def test_undo_eat_restores_batch(client):
    pid = new_plan(client)
    cook = add_meal(client, pid, "Dal", "2030-01-07", "cook")
    eat = add_meal(client, pid, "Dal with Eggs and Spinach", "2030-01-08")
    client.post(f"/api/kitchen/meals/{cook}/cooked")
    client.post(f"/api/kitchen/meals/{eat}/eaten")
    assert batches()[0]["quantity"] == 4
    assert client.post(f"/api/kitchen/meals/{cook}/undo").status_code == 409  # batch partly consumed
    assert client.post(f"/api/kitchen/meals/{eat}/undo").status_code == 200
    assert batches()[0]["quantity"] == 6
    assert client.post(f"/api/kitchen/meals/{eat}/eaten", json={"portions": 1}).status_code == 200
    assert batches()[0]["quantity"] == 5


def test_skipped_meal_creates_no_movement(client):
    pid = new_plan(client)
    m = add_meal(client, pid, "Pancakes", "2030-01-07")
    assert client.patch(f"/api/kitchen/meals/{m}", json={"status": "skipped"}).status_code == 200
    assert client.post(f"/api/kitchen/meals/{m}/eaten").status_code == 409
    assert all(r["quantity"] == 0 for r in httpx.get(f"{ST}/items").json()["rows"])


def test_suggest_plan_shape(client):
    r = client.post("/api/kitchen/plans/suggest", json={"week_start": "2030-01-07"})
    meals = r.json()["rows"][0]["meals"]
    assert sum(1 for m in meals if m["kind"] == "cook") == 2
    assert sum(1 for m in meals if m["kind"] == "meal") == 7
    # portions drawn from cooked bases never exceed what is produced
    shop = client.get(f"/api/kitchen/plans/{r.json()['rows'][0]['id']}/shopping").json()["rows"][0]
    assert shop["missing_bases"] == []


def test_recipe_crud(client):
    r = client.post("/api/kitchen/recipes", json={"name": "Test", "kind": "favorite", "servings": 2,
                    "ingredients": [{"name": "Reis", "qty": 200, "unit": "g"}]})
    assert r.status_code == 201
    rid = r.json()["rows"][0]["id"]
    r = client.patch(f"/api/kitchen/recipes/{rid}", json={"steps": "kochen"})
    assert r.json()["rows"][0]["steps"] == "kochen" and len(r.json()["rows"][0]["ingredients"]) == 1
    assert client.delete(f"/api/kitchen/recipes/{rid}").status_code == 200
