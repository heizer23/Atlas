"""Stock management type (QUANTITY | KANBAN) and article categories."""


def make(client, **kw):
    body = {"name": "Paprika", "item_type": "consumable", **kw}
    r = client.post("/api/items", json=body)
    assert r.status_code == 200, r.text
    return r.json()["rows"][0]


def get(client, item_id):
    return client.get(f"/api/items/{item_id}").json()["rows"][0]


def open_task_item_ids(client):
    return {t["item_id"] for t in client.get("/api/shopping-tasks").json()["rows"]}


def test_defaults_are_quantity_and_other(client):
    item = make(client, quantity=3)
    assert item["stock_management_type"] == "QUANTITY" and item["category"] == "Other"


def test_invalid_type_and_category_rejected(client):
    for extra in ({"stock_management_type": "FIFO"}, {"category": "Snacks"}):
        r = client.post("/api/items", json={"name": "x", "item_type": "consumable", **extra})
        assert r.status_code == 400, r.text
    item = make(client)
    assert client.patch(f"/api/items/{item['id']}", json={"category": "Snacks"}).status_code == 400


def test_category_assign_change_and_filter(client):
    a = make(client, name="Apfel", category="Vegetables & Fruit")
    b = make(client, name="Zimt", category="Spices")
    assert client.patch(f"/api/items/{b['id']}", json={"category": "Dry Goods"}).status_code == 200
    assert get(client, b["id"])["category"] == "Dry Goods"
    ids = {r["id"] for r in client.get("/api/items?category=Vegetables%20%26%20Fruit").json()["rows"]}
    assert a["id"] in ids and b["id"] not in ids
    assert client.get("/api/items?category=Nope").status_code == 400


def test_kanban_ignores_quantity_auto_transition(client):
    item = make(client, stock_management_type="KANBAN", quantity=0, min_quantity=2)
    assert item["state"] == "stored"
    assert item["id"] not in open_task_item_ids(client)


def test_kanban_movement_is_recorded_but_never_deducts(client):
    item = make(client, name="Salz", stock_management_type="KANBAN", quantity=5)
    r = client.post(f"/api/items/{item['id']}/movements",
                    json={"delta": -3, "reason": "cook", "idempotency_key": "k-kanban-1"})
    assert r.status_code == 201, r.text
    mvt = r.json()["movement"]
    assert mvt["delta"] == 0 and mvt["requested_delta"] == -3
    row = get(client, item["id"])
    assert row["quantity"] == 5 and row["state"] == "stored"
    assert item["id"] not in open_task_item_ids(client)
    # idempotent replay and reversal still work
    assert client.post(f"/api/items/{item['id']}/movements",
                       json={"delta": -3, "reason": "cook", "idempotency_key": "k-kanban-1"}).status_code == 200
    assert client.post(f"/api/movements/{mvt['id']}/reverse").status_code == 201
    assert get(client, item["id"])["quantity"] == 5


def test_kanban_low_and_out_create_one_task_and_done_resets_status(client):
    item = make(client, name="Oregano", stock_management_type="KANBAN", restock_quantity=10)
    assert client.patch(f"/api/items/{item['id']}", json={"state": "low_stock"}).status_code == 200
    assert item["id"] in open_task_item_ids(client)
    assert client.patch(f"/api/items/{item['id']}", json={"state": "out_of_stock"}).status_code == 200
    tasks = [t for t in client.get("/api/shopping-tasks").json()["rows"] if t["item_id"] == item["id"]]
    assert len(tasks) == 1
    r = client.patch(f"/api/shopping-tasks/{tasks[0]['id']}", json={"status": "done"})
    assert r.status_code == 200, r.text
    row = get(client, item["id"])
    assert row["state"] == "stored" and row["quantity"] is None   # restock_quantity ignored for Kanban


def test_quantity_article_unchanged_by_new_fields(client):
    item = make(client, name="Eier", quantity=6, min_quantity=2, unit="Stk", category="Dairy")
    client.post(f"/api/items/{item['id']}/movements", json={"delta": -5, "reason": "cook"})
    row = get(client, item["id"])
    assert row["quantity"] == 1 and row["state"] == "low_stock"
    assert item["id"] in open_task_item_ids(client)


def test_switching_type_keeps_history_and_quantity(client):
    item = make(client, name="Pfeffer", quantity=4)
    client.post(f"/api/items/{item['id']}/movements", json={"delta": -1, "reason": "cook"})
    assert client.patch(f"/api/items/{item['id']}", json={"stock_management_type": "KANBAN"}).status_code == 200
    assert get(client, item["id"])["quantity"] == 3
    assert len(client.get(f"/api/items/{item['id']}/movements").json()["rows"]) == 1


def test_batch_cannot_be_kanban(client):
    r = client.post("/api/items", json={"name": "Dal", "item_type": "consumable", "kind": "batch",
                                        "stock_management_type": "KANBAN"})
    assert r.status_code == 400
