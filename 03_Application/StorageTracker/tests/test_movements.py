"""Stock-movement ledger tests (Kitchen Sprint01, Slice 1)."""


def make_item(client, **kw):
    r = client.post("/api/items", json={"name": "Linsen", "item_type": "consumable",
                                        "quantity": 500, "unit": "g", **kw})
    assert r.status_code == 200, r.text
    return r.json()["rows"][0]


def mv(client, item_id, delta, **kw):
    return client.post(f"/api/items/{item_id}/movements",
                       json={"delta": delta, "reason": "test", **kw})


def qty(client, item_id):
    return client.get(f"/api/items/{item_id}").json()["rows"][0]["quantity"]


def test_movement_updates_quantity_and_keeps_unit(client):
    item = make_item(client)
    r = mv(client, item["id"], -200)
    assert r.status_code == 201
    assert r.json()["quantity"] == 300
    row = client.get(f"/api/items/{item['id']}").json()["rows"][0]
    assert row["quantity"] == 300 and row["unit"] == "g"


def test_idempotency_key_replays_without_double_booking(client):
    item = make_item(client)
    a = mv(client, item["id"], -100, idempotency_key="k1")
    b = mv(client, item["id"], -100, idempotency_key="k1")
    assert a.status_code == 201 and b.status_code == 200
    assert b.json()["replayed"] is True
    assert b.json()["movement"]["id"] == a.json()["movement"]["id"]
    assert qty(client, item["id"]) == 400


def test_delta_clamped_at_zero(client):
    item = make_item(client)
    r = mv(client, item["id"], -900)
    m = r.json()["movement"]
    assert m["delta"] == -500 and m["requested_delta"] == -900
    assert qty(client, item["id"]) == 0


def test_reverse_restores_and_only_once(client):
    item = make_item(client)
    m = mv(client, item["id"], -200).json()["movement"]
    r = client.post(f"/api/movements/{m['id']}/reverse")
    assert r.status_code == 201 and qty(client, item["id"]) == 500
    assert client.post(f"/api/movements/{m['id']}/reverse").status_code == 409
    rev = r.json()["movement"]
    assert client.post(f"/api/movements/{rev['id']}/reverse").status_code == 409


def test_patch_quantity_writes_correction_movement(client):
    item = make_item(client)
    client.patch(f"/api/items/{item['id']}", json={"quantity": 350})
    rows = client.get(f"/api/items/{item['id']}/movements").json()["rows"]
    assert len(rows) == 1 and rows[0]["delta"] == -150 and rows[0]["reason"] == "patch"


def test_batch_zero_creates_no_shopping_task(client):
    b = client.post("/api/items", json={"name": "Dal", "item_type": "consumable", "kind": "batch",
                                        "quantity": 2, "unit": "Portionen", "min_quantity": 1}).json()["rows"][0]
    assert b["state"] == "stored"
    mv(client, b["id"], -2)
    row = client.get(f"/api/items/{b['id']}").json()["rows"][0]
    assert row["quantity"] == 0 and row["state"] == "stored"
    tasks = client.get("/api/shopping-tasks").json()["rows"]
    assert all(t["item_id"] != b["id"] for t in tasks)


def test_ingredient_low_stock_still_triggers_task(client):
    item = make_item(client, min_quantity=100)
    mv(client, item["id"], -450)
    assert client.get(f"/api/items/{item['id']}").json()["rows"][0]["state"] == "low_stock"


def test_fractional_quantity_roundtrip(client):
    item = make_item(client)
    mv(client, item["id"], -0.25)
    assert qty(client, item["id"]) == 499.75


def test_unknown_item_404(client):
    assert mv(client, 999999999, 1).status_code == 404
