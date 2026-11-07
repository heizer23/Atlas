"""Kitchen -> Storage demand sync, end to end against the real StorageTracker test instance.

Kitchen sends GROSS raw-ingredient demand only; Storage nets it against stock, applies pack sizes and owns the list.
"""
import os

import httpx
import pytest

ST = os.environ.get("STORAGETRACKER_URL", "http://atlas-storagetracker-test:8000") + "/api"
K = "/api/kitchen"
TOKEN = {"X-Atlas-Service-Token": os.environ.get("ATLAS_SERVICE_TOKEN", "test-token")}


def article(name, unit, qty=0, **kw):
    r = httpx.post(f"{ST}/items", json={"name": name, "item_type": "consumable", "unit": unit, "quantity": qty,
                                        "source_tags": ["kitchen"], **kw})
    assert r.status_code == 200, r.text
    return r.json()["rows"][0]


def recipe(client, name, kind, servings, lines):
    """lines: (article, qty) raw or ('base', recipe_id, qty)."""
    ings = []
    for l in lines:
        if l[0] == "base":
            ings.append({"name": "base", "qty": l[2], "unit": "portions", "base_recipe_id": l[1]})
        else:
            ings.append({"name": l[0]["name"], "qty": l[1], "unit": l[0]["unit"], "item_id": l[0]["id"]})
    r = client.post(f"{K}/recipes", json={"name": name, "kind": kind, "servings": servings, "shelf_life_days": 3,
                                          "ingredients": ings})
    assert r.status_code == 201, r.text
    return r.json()["rows"][0]["id"]


def empty_plan(client):
    plan = client.post(f"{K}/plans/suggest", json={"week_start": "2032-01-05", "cook_sessions": 0}).json()["rows"][0]
    for m in plan["meals"]:
        client.delete(f"{K}/meals/{m['id']}")
    return plan["id"]


def add(client, plan, rid, day, kind, portions=None):
    r = client.post(f"{K}/plans/{plan}/meals", json={"recipe_id": rid, "day": day, "kind": kind, "portions": portions})
    assert r.status_code == 201, r.text
    return r.json()["rows"][0]["id"]


def central():
    return {r["item_id"]: r for r in httpx.get(f"{ST}/shopping-tasks/views/central").json()["rows"]}


def storage_lines():
    return httpx.get(f"{ST}/internal/demands/kitchen", headers=TOKEN).json()["rows"]


def status(client):
    return client.get(f"{K}/demand/status").json()["rows"][0]


@pytest.fixture(autouse=True)
def clean_demand(db_conn):
    with db_conn.cursor() as cur:
        cur.execute("truncate storagetracker.demands")
        cur.execute("update kitchen.demand_sync set status = 'pending', last_error = null, problems = '[]', issues = '[]'")
    yield


def test_dal_shortage_rounded_to_can_size(client):
    cm = article("Coconut milk", "ml", 400, purchase_multiple=400)
    dal = recipe(client, "Dal X", "base", 6, [(cm, 400)])
    plan = empty_plan(client)
    add(client, plan, dal, "2032-01-05", "cook", 12)            # 12 portions = 800 ml
    row = central()[cm["id"]]
    assert (row["demand_qty"], row["usable_stock"], row["shortage"], row["purchase_qty"]) == (800, 400, 400, 400)
    assert row["origins"] == ["kitchen"] and row["needed_by"] == "2032-01-05"
    assert status(client)["status"] == "ok"


def test_two_recipes_aggregate_and_stock_is_counted_once(client):
    cm = article("Coconut milk", "ml", 400, purchase_multiple=400)
    r1 = recipe(client, "Dal X", "base", 6, [(cm, 400)])
    r2 = recipe(client, "Curry X", "favorite", 2, [(cm, 400)])
    plan = empty_plan(client)
    add(client, plan, r1, "2032-01-05", "cook", 12)
    add(client, plan, r2, "2032-01-06", "meal", 2)
    row = central()[cm["id"]]
    assert row["demand_qty"] == 1200 and row["shortage"] == 800 and row["purchase_qty"] == 800
    assert len(storage_lines()) == 2


def test_plan_edits_update_demand_and_keep_manual_items(client):
    cm = article("Coconut milk", "ml", 0, purchase_multiple=400)
    soap = article("Soap", "pcs", 0)
    httpx.post(f"{ST}/shopping-tasks", json={"item_id": soap["id"], "notes": "blue"})
    dal = recipe(client, "Dal X", "base", 6, [(cm, 400)])
    plan = empty_plan(client)
    meal = add(client, plan, dal, "2032-01-05", "cook", 6)
    assert central()[cm["id"]]["purchase_qty"] == 400
    client.patch(f"{K}/meals/{meal}", json={"portions": 12})                 # re-portion
    assert central()[cm["id"]]["purchase_qty"] == 800
    client.patch(f"{K}/meals/{meal}", json={"day": "2032-01-07"})            # move
    assert central()[cm["id"]]["needed_by"] == "2032-01-07"
    client.patch(f"{K}/meals/{meal}", json={"status": "skipped"})            # skip
    assert cm["id"] not in central()
    meal2 = add(client, plan, dal, "2032-01-08", "cook", 6)
    assert central()[cm["id"]]["purchase_qty"] == 400
    assert client.delete(f"{K}/meals/{meal2}").status_code == 200            # delete
    rows = central()
    assert cm["id"] not in rows and rows[soap["id"]]["origins"] == ["manual"] and rows[soap["id"]]["notes"] == "blue"


def test_cook_removes_fulfilled_demand_and_consumes_exactly_once(client):
    cm = article("Coconut milk", "ml", 1000, purchase_multiple=400)
    dal = recipe(client, "Dal X", "base", 6, [(cm, 400)])
    plan = empty_plan(client)
    meal = add(client, plan, dal, "2032-01-05", "cook", 12)
    assert cm["id"] not in central()                                          # stock covers the 800 ml
    assert len(storage_lines()) == 1
    r = client.post(f"{K}/meals/{meal}/cooked", json={"produced_qty": 12})
    assert r.status_code == 200, r.text
    assert storage_lines() == [] and cm["id"] not in central()                # demand fulfilled, not double counted
    mv = httpx.get(f"{ST}/items/{cm['id']}/movements").json()["rows"]
    assert [(m["delta"], m["reason"]) for m in mv if m["reason"].startswith("cook")] == [(-800, "cook Dal X")]
    assert httpx.get(f"{ST}/items/{cm['id']}").json()["rows"][0]["quantity"] == 200
    client.post(f"{K}/meals/{meal}/cooked", json={"produced_qty": 12})        # repeat confirmation
    assert httpx.get(f"{ST}/items/{cm['id']}").json()["rows"][0]["quantity"] == 200
    # undo: the cook is reverted and the demand is open again
    assert client.post(f"{K}/meals/{meal}/undo").status_code == 200
    assert len(storage_lines()) == 1


def test_base_cook_with_two_derived_meals_counts_base_ingredients_once(client):
    lent = article("Lentils", "g", 0)
    egg = article("Eggs", "piece", 0)
    spin = article("Spinach", "g", 0)
    dal = recipe(client, "Dal X", "base", 6, [(lent, 300)])
    d1 = recipe(client, "Dal Eggs X", "derived", 2, [("base", dal, 2), (egg, 4)])
    d2 = recipe(client, "Dal Spinach X", "derived", 2, [("base", dal, 2), (spin, 200)])
    plan = empty_plan(client)
    add(client, plan, dal, "2032-01-05", "cook", 6)
    add(client, plan, d1, "2032-01-06", "meal", 2)
    add(client, plan, d2, "2032-01-07", "meal", 2)
    rows = central()
    assert rows[lent["id"]]["demand_qty"] == 300                              # once, not three times
    assert rows[egg["id"]]["demand_qty"] == 4 and rows[spin["id"]]["demand_qty"] == 200
    assert len(storage_lines()) == 3
    assert not [i for i in status(client)["issues"] if i["type"] == "missing_base"]


def test_missing_base_is_flagged_not_purchased(client):
    lent = article("Lentils", "g", 0)
    egg = article("Eggs", "piece", 0)
    dal = recipe(client, "Dal X", "base", 6, [(lent, 300)])
    d1 = recipe(client, "Dal Eggs X", "derived", 2, [("base", dal, 2), (egg, 4)])
    plan = empty_plan(client)
    add(client, plan, d1, "2032-01-06", "meal", 2)                            # no cooking session, no batch
    assert lent["id"] not in central()
    assert [i["type"] for i in status(client)["issues"]] == ["missing_base"]


def test_identical_resend_is_idempotent(client):
    cm = article("Coconut milk", "ml", 0)
    dal = recipe(client, "Dal X", "base", 6, [(cm, 400)])
    add(client, empty_plan(client), dal, "2032-01-05", "cook", 6)
    before = (storage_lines(), central()[cm["id"]]["purchase_qty"])
    for _ in range(2):
        assert client.post(f"{K}/demand/sync").json()["rows"][0]["status"] == "ok"
    assert (storage_lines(), central()[cm["id"]]["purchase_qty"]) == before
    assert len(before[0]) == 1


def test_failed_sync_keeps_previous_demand_is_visible_and_retry_succeeds(client, monkeypatch):
    from backend import storage_client as st
    cm = article("Coconut milk", "ml", 0)
    dal = recipe(client, "Dal X", "base", 6, [(cm, 400)])
    plan = empty_plan(client)
    meal = add(client, plan, dal, "2032-01-05", "cook", 6)
    assert central()[cm["id"]]["purchase_qty"] == 400

    def down(lines):
        raise st.StorageError("StorageTracker unreachable: connection refused")
    monkeypatch.setattr(st, "put_demands", down)
    r = client.patch(f"{K}/meals/{meal}", json={"portions": 12})
    assert r.status_code == 200                                               # planning itself is unaffected
    s = status(client)
    assert s["status"] == "error" and "unreachable" in s["last_error"]
    assert central()[cm["id"]]["purchase_qty"] == 400                         # previous valid snapshot intact
    monkeypatch.undo()
    assert client.post(f"{K}/demand/sync").json()["rows"][0]["status"] == "ok"   # retry
    assert central()[cm["id"]]["purchase_qty"] == 800
    assert status(client)["last_error"] is None


def test_rejected_snapshot_shows_actionable_problem_and_recovers(client, monkeypatch):
    from backend import service
    cm = article("Coconut milk", "ml", 0)
    dal = recipe(client, "Dal X", "base", 6, [(cm, 400)])
    plan = empty_plan(client)
    add(client, plan, dal, "2032-01-05", "cook", 6)
    good = service.compute_demand

    def bad(conn):
        lines, issues = good(conn)
        return lines + [{"ref": "x", "item_id": 987654321, "qty": 1, "unit": "ml", "required_date": None, "label": "x"}], issues
    monkeypatch.setattr(service, "compute_demand", bad)
    s = client.post(f"{K}/demand/sync").json()["rows"][0]
    assert s["status"] == "error" and "rejected" in s["last_error"]
    assert s["problems"][0]["field"] == "item_id" and "987654321" in s["problems"][0]["message"]
    assert len(storage_lines()) == 1 and central()[cm["id"]]["purchase_qty"] == 400   # untouched
    monkeypatch.undo()
    assert client.post(f"{K}/demand/sync").json()["rows"][0]["status"] == "ok"


def test_draft_recipe_in_plan_is_flagged_and_excluded(client):
    cm = article("Coconut milk", "ml", 0)
    r = recipe(client, "Soup X", "favorite", 2, [(cm, 400)])
    add(client, empty_plan(client), r, "2032-01-05", "meal", 2)
    assert cm["id"] in central()
    # an ingredient loses its article assignment -> recipe becomes a draft while still planned
    client.patch(f"{K}/recipes/{r}", json={"ingredients": [{"name": "Mystery", "qty": 1, "unit": "g"}]})
    s = status(client)
    assert s["status"] == "ok" and s["issues"][0]["type"] == "draft_recipe" and "Mystery" in s["issues"][0]["ingredients"]
    assert cm["id"] not in central() and storage_lines() == []


def test_startup_recovery_republishes_snapshot(client):
    from backend import demand_sync
    cm = article("Coconut milk", "ml", 0)
    dal = recipe(client, "Dal X", "base", 6, [(cm, 400)])
    add(client, empty_plan(client), dal, "2032-01-05", "cook", 6)
    httpx.put(f"{ST}/internal/demands/kitchen", json={"lines": []}, headers=TOKEN)   # Storage lost the snapshot
    assert cm["id"] not in central()
    assert demand_sync.sync_demand()["status"] == "ok"
    assert central()[cm["id"]]["purchase_qty"] == 400


def test_kitchen_no_longer_has_a_shopping_list_or_stock_endpoints(client):
    for method, path in (("get", f"{K}/plans/x/shopping"), ("post", f"{K}/shopping/purchase"),
                         ("post", f"{K}/shopping/stocktake")):
        assert getattr(client, method)(path).status_code in (404, 405)
