"""Central shopping list: demand snapshot replacement, shortage netting, pack-size rounding, manual items."""
import os

os.environ.setdefault("ATLAS_SERVICE_TOKEN", "test-token")
H = {"X-Atlas-Service-Token": os.environ["ATLAS_SERVICE_TOKEN"]}
D = "/api/internal/demands/kitchen"


def make(client, name, qty, unit="ml", **kw):
    r = client.post("/api/items", json={"name": name, "item_type": "consumable", "quantity": qty, "unit": unit, **kw})
    assert r.status_code == 200, r.text
    return r.json()["rows"][0]


def line(ref, item_id, qty, unit="ml", **kw):
    return {"ref": ref, "item_id": item_id, "qty": qty, "unit": unit, **kw}


def put(client, lines, source="kitchen", headers=H):
    return client.put(f"/api/internal/demands/{source}", json={"lines": lines}, headers=headers)


def central(client):
    return {r["item_id"]: r for r in client.get("/api/shopping-tasks/views/central").json()["rows"]}


def stored(client, source="kitchen"):
    return client.get(f"/api/internal/demands/{source}", headers=H).json()["rows"]


# ── auth ──────────────────────────────────────────────────────────────────────

def test_internal_endpoint_requires_service_token(client):
    assert put(client, [], headers={}).status_code == 401
    assert put(client, [], headers={"X-Atlas-Service-Token": "wrong"}).status_code == 401
    assert client.get(f"{D}/status").status_code == 401


def test_internal_endpoint_fails_closed_without_configured_token(client, monkeypatch):
    monkeypatch.delenv("ATLAS_SERVICE_TOKEN")
    assert put(client, [], headers={"X-Atlas-Service-Token": ""}).status_code == 503


# ── snapshot replacement ──────────────────────────────────────────────────────

def test_acceptance_shortage_rounded_to_pack_size(client):
    """800 ml needed, 400 ml in stock, 400 ml cans -> buy one can (400 ml)."""
    cm = make(client, "Coconut milk", 400, purchase_multiple=400)
    assert put(client, [line("meal:1:a", cm["id"], 800, required_date="2030-01-07", label="Dal")]).status_code == 200
    row = central(client)[cm["id"]]
    assert (row["demand_qty"], row["usable_stock"], row["shortage"], row["purchase_qty"]) == (800, 400, 400, 400)
    assert row["origins"] == ["kitchen"] and row["needed_by"] == "2030-01-07"


def test_rounding_up_to_multiple_and_minimum_order(client):
    a = make(client, "Rice", 0, unit="g", purchase_multiple=500)
    b = make(client, "Saffron", 0, unit="g", min_purchase_qty=2)
    c = make(client, "Tofu", 0, unit="g", purchase_multiple=200, min_purchase_qty=600)
    d = make(client, "Salt", 0, unit="g")
    put(client, [line("1", a["id"], 600, "g"), line("2", b["id"], 0.5, "g"), line("3", c["id"], 100, "g"),
                 line("4", d["id"], 37.5, "g")])
    rows = central(client)
    assert rows[a["id"]]["purchase_qty"] == 1000        # 600 -> 2 packs
    assert rows[b["id"]]["purchase_qty"] == 2           # below MOQ
    assert rows[c["id"]]["purchase_qty"] == 600         # MOQ 600 is already a multiple of 200
    assert rows[d["id"]]["purchase_qty"] == 37.5        # no rule: exactly the shortage


def test_two_recipes_aggregate_and_stock_counts_once(client):
    cm = make(client, "Coconut milk", 400, purchase_multiple=400)
    put(client, [line("meal:1:a", cm["id"], 800), line("meal:2:a", cm["id"], 400)])
    row = central(client)[cm["id"]]
    assert row["demand_qty"] == 1200 and row["shortage"] == 800 and row["purchase_qty"] == 800   # not 800-400 + 400-400
    assert len(row["demands"]) == 2


def test_stock_covers_demand_means_no_row(client):
    it = make(client, "Flour", 1000, unit="g")
    put(client, [line("1", it["id"], 400, "g")])
    assert it["id"] not in central(client)


def test_inventory_change_recalculates_shortage(client):
    it = make(client, "Milk", 100, purchase_multiple=100)
    put(client, [line("1", it["id"], 500)])
    assert central(client)[it["id"]]["purchase_qty"] == 400
    client.post(f"/api/items/{it['id']}/movements", json={"delta": 250, "reason": "purchase"})
    assert central(client)[it["id"]]["purchase_qty"] == 200
    client.post(f"/api/items/{it['id']}/movements", json={"delta": 500, "reason": "purchase"})
    assert it["id"] not in central(client)


def test_expired_stock_is_not_usable(client):
    it = make(client, "Yogurt", 500, expires_at="2000-01-01")
    put(client, [line("1", it["id"], 300)])
    row = central(client)[it["id"]]
    assert row["stock"] == 500 and row["usable_stock"] == 0 and row["shortage"] == 300


def test_identical_snapshot_is_idempotent(client):
    it = make(client, "Oil", 0)
    lines = [line("1", it["id"], 100), line("2", it["id"], 50)]
    first = put(client, lines).json()
    second = put(client, lines).json()
    assert first["changed"] is True and second["changed"] is False
    assert len(stored(client)) == 2 and central(client)[it["id"]]["demand_qty"] == 150


def test_snapshot_replaces_changes_and_removes(client):
    it = make(client, "Oil", 0)
    put(client, [line("1", it["id"], 100), line("2", it["id"], 50)])
    put(client, [line("1", it["id"], 70)])                      # 2 removed, 1 changed
    assert [(r["ref"], r["qty"]) for r in stored(client)] == [("1", 70)]
    put(client, [])                                              # empty snapshot = no demand
    assert stored(client) == [] and it["id"] not in central(client)


def test_replace_only_touches_its_own_source_and_keeps_manual_items(client):
    it = make(client, "Pasta", 0, unit="g")
    other = make(client, "Salt", 0, unit="g")
    manual = make(client, "Soap", 0, unit="pcs")
    assert client.post("/api/shopping-tasks", json={"item_id": manual["id"], "notes": "the blue one"}).status_code == 201
    put(client, [line("1", it["id"], 100, "g")], source="other")
    put(client, [line("1", other["id"], 100, "g")])
    put(client, [])                                              # kitchen clears its snapshot
    assert [r["item_id"] for r in stored(client, "other")] == [it["id"]]
    rows = central(client)
    assert it["id"] in rows and other["id"] not in rows
    assert rows[manual["id"]]["origins"] == ["manual"] and rows[manual["id"]]["notes"] == "the blue one"


def test_manual_and_demand_share_one_row(client):
    it = make(client, "Eggs", 2, unit="pcs", purchase_multiple=6)
    client.post("/api/shopping-tasks", json={"item_id": it["id"]})
    put(client, [line("1", it["id"], 5, "pcs")])
    row = central(client)[it["id"]]
    assert sorted(row["origins"]) == ["kitchen", "manual"] and row["purchase_qty"] == 6
    assert row["task_id"]


def test_kanban_demand_is_ignored(client):
    it = make(client, "Pepper", None, unit="g", stock_management_type="KANBAN")
    put(client, [line("1", it["id"], 5, "g")])
    assert it["id"] not in central(client)


# ── rejection leaves the previous snapshot intact ─────────────────────────────

def test_invalid_snapshots_are_rejected_atomically(client):
    good = make(client, "Oil", 0)
    put(client, [line("1", good["id"], 100)])
    batch = client.post("/api/items", json={"name": "Dal batch", "item_type": "consumable", "kind": "batch",
                                            "quantity": 2, "unit": "portions"}).json()["rows"][0]
    cases = {
        "unknown article": [line("1", good["id"], 5), line("2", 99999999, 5)],
        "unit mismatch":   [line("1", good["id"], 5), line("2", good["id"], 5, "g")],
        "negative qty":    [line("1", good["id"], -5)],
        "zero qty":        [line("1", good["id"], 0)],
        "batch sku":       [line("1", batch["id"], 1, "portions")],
        "duplicate ref":   [line("1", good["id"], 5), line("1", good["id"], 6)],
        "bad date":        [line("1", good["id"], 5, required_date="soon")],
        "string item id":  [line("1", "7", 5)],
        "missing ref":     [{"item_id": good["id"], "qty": 5, "unit": "ml"}],
    }
    for name, lines in cases.items():
        r = put(client, lines)
        assert r.status_code == 422, name
        err = r.json()["error"]
        assert err["code"] == "DEMAND_SNAPSHOT_REJECTED" and err["detail"], name
        assert all(p["message"] for p in err["detail"]), name
        assert [(x["ref"], x["qty"]) for x in stored(client)] == [("1", 100)], name   # untouched
    assert client.put("/api/internal/demands/kitchen", content=b"not json", headers=H).status_code == 422
    assert client.put("/api/internal/demands/kitchen", json=[1, 2], headers=H).status_code == 422


def test_status_reports_rejection_then_recovers_on_retry(client):
    it = make(client, "Oil", 0)
    put(client, [line("1", it["id"], 100)])
    ok = client.get(f"{D}/status", headers=H).json()
    assert ok["line_count"] == 1 and ok["last_error"] is None
    assert put(client, [line("1", 424242, 1)]).status_code == 422
    bad = client.get(f"{D}/status", headers=H).json()
    assert bad["last_error"][0]["message"] and bad["line_count"] == 1 and bad["last_ok_at"]
    ui = client.get("/api/shopping-tasks/views/demand_status").json()["rows"]
    assert ui[0]["source"] == "kitchen" and ui[0]["last_error"]
    assert put(client, [line("1", it["id"], 100)]).status_code == 200             # retry succeeds
    assert client.get(f"{D}/status", headers=H).json()["last_error"] is None
    assert client.get("/api/shopping-tasks/views/demand_status").json()["rows"][0]["last_error"] is None


def test_deleting_an_article_drops_its_demand(client):
    it = make(client, "Oil", 0)
    put(client, [line("1", it["id"], 100)])
    client.delete(f"/api/items/{it['id']}")
    assert stored(client) == []


# ── purchase / check-off ──────────────────────────────────────────────────────

def test_bought_books_one_movement_and_row_disappears(client):
    it = make(client, "Coconut milk", 400, purchase_multiple=400, min_quantity=100)
    put(client, [line("1", it["id"], 800)])
    r = client.post("/api/shopping-tasks/purchase", json={"item_id": it["id"], "qty": 400, "idempotency_key": "p1"})
    assert r.status_code == 200 and r.json()["quantity"] == 800
    again = client.post("/api/shopping-tasks/purchase", json={"item_id": it["id"], "qty": 400, "idempotency_key": "p1"})
    assert again.json()["replayed"] is True
    assert client.get(f"/api/items/{it['id']}").json()["rows"][0]["quantity"] == 800   # booked once
    assert it["id"] not in central(client)                                              # not recreated
    mv = client.get(f"/api/items/{it['id']}/movements").json()["rows"]
    assert [m["reason"] for m in mv] == ["purchase"]


def test_bought_closes_open_task_without_restock_reset(client):
    it = make(client, "Honey", 0, unit="g", restock_quantity=999)
    client.post("/api/shopping-tasks", json={"item_id": it["id"]})
    client.post("/api/shopping-tasks/purchase", json={"item_id": it["id"], "qty": 250})
    assert client.get(f"/api/items/{it['id']}").json()["rows"][0]["quantity"] == 250   # not reset to 999
    assert it["id"] not in central(client)


def test_partial_purchase_keeps_remaining_shortage(client):
    it = make(client, "Rice", 0, unit="g")
    put(client, [line("1", it["id"], 1000, "g")])
    client.post("/api/shopping-tasks/purchase", json={"item_id": it["id"], "qty": 400})
    assert central(client)[it["id"]]["purchase_qty"] == 600


def test_task_only_row_keeps_existing_done_behaviour(client):
    it = make(client, "Soap", 0, unit="pcs", restock_quantity=4)
    client.post("/api/shopping-tasks", json={"item_id": it["id"]})
    row = central(client)[it["id"]]
    assert row["shortage"] is None and row["task_id"]
    assert client.patch(f"/api/shopping-tasks/{row['task_id']}", json={"status": "done"}).status_code == 200
    assert client.get(f"/api/items/{it['id']}").json()["rows"][0]["quantity"] == 4
    assert it["id"] not in central(client)


def test_low_stock_task_is_marked_as_low_stock_origin(client):
    it = make(client, "Tea", 1, unit="pcs", min_quantity=2)
    assert central(client)[it["id"]]["origins"] == ["low_stock"]


def test_kanban_purchase_is_refused(client):
    it = make(client, "Pepper", None, unit="g", stock_management_type="KANBAN")
    assert client.post("/api/shopping-tasks/purchase", json={"item_id": it["id"], "qty": 1}).status_code == 409


def test_purchase_rule_validation_and_clearing(client):
    assert client.post("/api/items", json={"name": "x", "item_type": "consumable", "purchase_multiple": 0}).status_code == 400
    it = make(client, "Cans", 0, purchase_multiple=400)
    r = client.patch(f"/api/items/{it['id']}", json={"purchase_multiple": None})
    assert r.status_code == 200 and r.json()["rows"][0]["purchase_multiple"] is None
