"""
Backend tests for StorageTracker items API.
Covers TC-001 through TC-027 from 10_test_spec.md.
"""

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def create_item(client, **kwargs) -> dict:
    payload = {"name": "test item", "item_type": "object", **kwargs}
    r = client.post("/api/items", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    return data["rows"][0]


def get_item(client, item_id: str) -> dict:
    r = client.get(f"/api/items/{item_id}")
    assert r.status_code == 200, r.text
    return r.json()["rows"][0]


# ── TC-001: Create item — minimal ─────────────────────────────────────────────

def test_create_item_minimal(client):
    r = client.post("/api/items", json={"name": "old printer", "item_type": "object"})
    assert r.status_code == 200
    data = r.json()
    assert data["meta"]["object_type"] == "item"
    row = data["rows"][0]
    assert row["name"] == "old printer"
    assert row["item_type"] == "object"
    assert row["state"] == "stored"
    assert row["source_tags"] == []
    assert row["id"]


# ── TC-002: Create consumable — auto-transition to low_stock ──────────────────

def test_create_consumable_auto_low_stock(client):
    r = client.post("/api/items", json={
        "name": "milk", "item_type": "consumable",
        "quantity": 2, "min_quantity": 5,
    })
    assert r.status_code == 200
    row = r.json()["rows"][0]
    assert row["state"] == "low_stock"


# ── TC-003: Caller state wins over auto-transition ────────────────────────────

def test_create_caller_state_wins(client):
    r = client.post("/api/items", json={
        "name": "milk", "item_type": "consumable",
        "quantity": 2, "min_quantity": 5, "state": "missing",
    })
    assert r.status_code == 200
    row = r.json()["rows"][0]
    assert row["state"] == "missing"


# ── TC-004: List items — no filter ────────────────────────────────────────────

def test_list_items_no_filter(client):
    # Fixtures load 9 items. Verify all are returned and the Dataset structure is correct.
    r = client.get("/api/items")
    assert r.status_code == 200
    data = r.json()
    assert data["meta"]["total"] == 9
    assert len(data["rows"]) == 9
    assert data["meta"]["object_type"] == "item"


# ── TC-005: List items — filter by state ─────────────────────────────────────

def test_list_items_state_filter(client):
    # Fixtures contain milk (low_stock) and salt (low_stock) — no other low_stock items.
    r = client.get("/api/items?state=low_stock")
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert len(rows) == 2
    names = {row["name"] for row in rows}
    assert "milk" in names
    assert "salt" in names
    assert all(row["state"] == "low_stock" for row in rows)


# ── TC-006: Filter by source_tag ─────────────────────────────────────────────

def test_list_items_source_tag_filter(client):
    # Use a tag not present in fixtures to get a clean, predictable result.
    create_item(client, name="test item dm", item_type="consumable", source_tags=["TestStoreDM"])
    r = client.get("/api/items?source_tag=TestStoreDM")
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["name"] == "test item dm"


# ── TC-007: Invalid state filter ─────────────────────────────────────────────

def test_list_items_invalid_state(client):
    r = client.get("/api/items?state=banana")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_FILTER"


# ── TC-008: Get single item with history ──────────────────────────────────────

def test_get_single_item_with_history(client):
    item = create_item(client, name="key")
    client.patch(f"/api/items/{item['id']}", json={"state": "missing"})
    r = client.get(f"/api/items/{item['id']}")
    assert r.status_code == 200
    row = r.json()["rows"][0]
    assert "history" in row
    assert len(row["history"]) == 2  # created + state_change


# ── TC-009: Patch state — history recorded ────────────────────────────────────

def test_patch_state_records_history(client):
    item = create_item(client, name="key")
    client.patch(f"/api/items/{item['id']}", json={"state": "missing"})
    r = client.get(f"/api/items/{item['id']}/history")
    assert r.status_code == 200
    rows = r.json()["rows"]
    change_types = [h["change_type"] for h in rows]
    assert "created" in change_types
    assert "state_change" in change_types


# ── TC-010: Auto-transition on quantity patch ─────────────────────────────────

def test_auto_transition_on_quantity_patch(client):
    item = create_item(client, name="milk", item_type="consumable", quantity=10, min_quantity=5)
    assert item["state"] == "stored"
    r = client.patch(f"/api/items/{item['id']}", json={"quantity": 3})
    assert r.status_code == 200
    row = r.json()["rows"][0]
    assert row["state"] == "low_stock"

    # Confirm history has quantity_change
    hist_r = client.get(f"/api/items/{item['id']}/history")
    change_types = [h["change_type"] for h in hist_r.json()["rows"]]
    assert "quantity_change" in change_types
    assert "state_change" in change_types


# ── TC-011: Caller state wins on patch ───────────────────────────────────────

def test_patch_caller_state_wins_over_auto_transition(client):
    item = create_item(client, name="milk", item_type="consumable", quantity=10, min_quantity=5)
    r = client.patch(f"/api/items/{item['id']}", json={"quantity": 3, "state": "out_of_stock"})
    assert r.status_code == 200
    row = r.json()["rows"][0]
    assert row["state"] == "out_of_stock"


# ── TC-012: Omitted field not cleared ────────────────────────────────────────

def test_patch_omit_field_not_cleared(client):
    item = create_item(client, name="key", location="hallway")
    client.patch(f"/api/items/{item['id']}", json={"state": "missing"})
    updated = get_item(client, item["id"])
    assert updated["location"] == "hallway"


# ── TC-013: Explicit null clears nullable field ───────────────────────────────

def test_patch_explicit_null_clears_field(client):
    item = create_item(client, name="key", location="hallway")
    r = client.patch(f"/api/items/{item['id']}", json={"location": None})
    assert r.status_code == 200
    updated = get_item(client, item["id"])
    assert updated["location"] is None


# ── TC-014: source_tags null rejected ────────────────────────────────────────

def test_patch_source_tags_null_rejected(client):
    item = create_item(client)
    r = client.patch(f"/api/items/{item['id']}", json={"source_tags": None})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


# ── TC-015: Delete item ───────────────────────────────────────────────────────

def test_delete_item(client):
    item = create_item(client)
    r = client.delete(f"/api/items/{item['id']}")
    assert r.status_code == 200

    # Item is gone
    r2 = client.get(f"/api/items/{item['id']}")
    assert r2.status_code == 404


# ── TC-016: Delete cascades to history ───────────────────────────────────────

def test_delete_cascades_to_history(client):
    item = create_item(client)
    client.patch(f"/api/items/{item['id']}", json={"state": "missing"})
    client.delete(f"/api/items/{item['id']}")
    r = client.get(f"/api/items/{item['id']}/history")
    assert r.status_code == 404


# ── TC-017: View low_stock ────────────────────────────────────────────────────

def test_view_low_stock(client):
    # Fixtures: milk (low_stock), salt (low_stock), razor blades (out_of_stock).
    # View must return low_stock and out_of_stock items, exclude normal objects.
    r = client.get("/api/items/views/low_stock")
    assert r.status_code == 200
    rows = r.json()["rows"]
    names = [row["name"] for row in rows]
    assert "milk" in names
    assert "salt" in names
    assert "razor blades" in names
    assert "spare charger" not in names   # object, not consumable concern
    assert "coffee" not in names           # stored, above threshold
    # Ordered by name ASC
    assert names == sorted(names)


# ── TC-018: View recycling ────────────────────────────────────────────────────

def test_view_recycling(client):
    # Fixtures: old printer (marked_for_recycling).
    r = client.get("/api/items/views/recycling")
    assert r.status_code == 200
    rows = r.json()["rows"]
    names = [row["name"] for row in rows]
    assert "old printer" in names
    assert all(row["state"] == "marked_for_recycling" for row in rows)


# ── TC-019: View important ────────────────────────────────────────────────────

def test_view_important(client):
    # Fixtures: 4 objects (spare charger, friend's key, passport, old printer).
    r = client.get("/api/items/views/important")
    assert r.status_code == 200
    rows = r.json()["rows"]
    names = {row["name"] for row in rows}
    assert "spare charger" in names
    assert "friend's key" in names
    assert "passport" in names
    assert "old printer" in names
    assert all(row["item_type"] == "object" for row in rows)


# ── TC-020: Search — substring match ─────────────────────────────────────────

def test_view_search_substring(client):
    # Fixture has "old printer" — search for "printer" returns exactly that one.
    r = client.get("/api/items/views/search?q=printer")
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["name"] == "old printer"


# ── TC-021: Search — empty q returns empty Dataset ───────────────────────────

def test_view_search_empty_q(client):
    create_item(client, name="key")
    r = client.get("/api/items/views/search?q=")
    assert r.status_code == 200
    assert r.json()["meta"]["total"] == 0


def test_view_search_no_q(client):
    create_item(client, name="key")
    r = client.get("/api/items/views/search")
    assert r.status_code == 200
    assert r.json()["meta"]["total"] == 0


# ── TC-022: Route ordering — views not captured as {id} ──────────────────────

def test_view_routes_not_captured_as_item_id(client):
    r = client.get("/api/items/views/low_stock")
    assert r.status_code == 200
    assert r.json()["meta"]["object_type"] == "item"


# ── TC-023: Full history endpoint ─────────────────────────────────────────────

def test_full_history(client):
    item = create_item(client, name="key", location="hallway")
    client.patch(f"/api/items/{item['id']}", json={"state": "missing"})
    client.patch(f"/api/items/{item['id']}", json={"location": "garage"})
    item2 = create_item(client, name="milk", item_type="consumable", quantity=10, min_quantity=5)
    client.patch(f"/api/items/{item2['id']}", json={"quantity": 3})

    r = client.get(f"/api/items/{item['id']}/history")
    assert r.status_code == 200
    rows = r.json()["rows"]
    # created + state_change + location_change = 3
    assert len(rows) == 3
    # Ordered by timestamp DESC
    timestamps = [h["timestamp"] for h in rows]
    assert timestamps == sorted(timestamps, reverse=True)


# ── TC-024: Not found on PATCH ────────────────────────────────────────────────

def test_patch_not_found(client):
    r = client.patch(
        "/api/items/00000000-0000-0000-0000-000000000000",
        json={"state": "missing"},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


# ── TC-025: Not found on DELETE ───────────────────────────────────────────────

def test_delete_not_found(client):
    r = client.delete("/api/items/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


# ── TC-026: Empty name rejected ───────────────────────────────────────────────

def test_create_empty_name_rejected(client):
    r = client.post("/api/items", json={"name": "", "item_type": "object"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


# ── TC-027: Negative quantity rejected ───────────────────────────────────────

def test_create_negative_quantity_rejected(client):
    r = client.post("/api/items", json={"name": "milk", "item_type": "consumable", "quantity": -1})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
