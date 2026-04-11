"""
StorageTracker Sprint02 — Shopping Tasks test suite.
Maps to scenarios in Sprint02_ShoppingTasks/10_test_spec.md.
Fixture IDs are defined in tests/fixtures.sql.
"""

# ── Fixture ID constants ───────────────────────────────────────────────────────

# Items
STORED_ITEM_ID    = "f1000010-0000-0000-0000-000000000000"  # stored, source_tags=['Rewe']
LOW_STOCK_ITEM_ID = "f1000011-0000-0000-0000-000000000000"  # low_stock, has open_task
WATCH_ITEM_ID     = "f1000012-0000-0000-0000-000000000000"  # stored, no open task
RESTOCK_MILK_ID   = "f1000013-0000-0000-0000-000000000000"  # low_stock, restock_qty=6, min=3
LOW_RESTOCK_ID    = "f1000014-0000-0000-0000-000000000000"  # low_stock, restock_qty=4, min=5
CABLE_ID          = "f1000015-0000-0000-0000-000000000000"  # out_of_stock, no restock_qty
DISMISS_ITEM_ID   = "f1000016-0000-0000-0000-000000000000"  # low_stock, has dismiss_task
CASCADE_ITEM_ID   = "f1000017-0000-0000-0000-000000000000"  # stored, has cascade_task
NOTAG_ITEM_ID     = "f1000018-0000-0000-0000-000000000000"  # low_stock, source_tags=[]
MULTI_TAG_ITEM_ID = "f1000019-0000-0000-0000-000000000000"  # low_stock, source_tags=['Rewe','Amazon']
DELETE_ITEM_ID    = "f1000020-0000-0000-0000-000000000000"  # low_stock, has delete_task

# Tasks
OPEN_TASK_ID        = "f2000001-0000-0000-0000-000000000000"  # open for LOW_STOCK_ITEM_ID
MILK_TASK_ID        = "f2000002-0000-0000-0000-000000000000"  # open for RESTOCK_MILK_ID
LOW_RESTOCK_TASK_ID = "f2000003-0000-0000-0000-000000000000"  # open for LOW_RESTOCK_ID
CABLE_TASK_ID       = "f2000004-0000-0000-0000-000000000000"  # open for CABLE_ID
DISMISS_TASK_ID     = "f2000005-0000-0000-0000-000000000000"  # open for DISMISS_ITEM_ID
CASCADE_TASK_ID     = "f2000006-0000-0000-0000-000000000000"  # open for CASCADE_ITEM_ID
NOTAG_TASK_ID       = "f2000007-0000-0000-0000-000000000000"  # open for NOTAG_ITEM_ID
MULTI_TASK_ID       = "f2000008-0000-0000-0000-000000000000"  # open for MULTI_TAG_ITEM_ID
DELETE_TASK_ID      = "f2000009-0000-0000-0000-000000000000"  # open for DELETE_ITEM_ID
DONE_TASK_ID        = "f2000010-0000-0000-0000-000000000000"  # done
DISMISSED_TASK_ID   = "f2000011-0000-0000-0000-000000000000"  # dismissed


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rows(resp) -> list:
    return resp.json().get("rows", [])


def _task_ids(resp) -> set:
    return {r["id"] for r in _rows(resp)}


# ── Manual Task Creation ──────────────────────────────────────────────────────

def test_manual_task_creation(client):
    """Given a stored item, POST creates an open task with source_tags copied from item."""
    r = client.post("/api/shopping-tasks", json={"item_id": STORED_ITEM_ID})
    assert r.status_code == 201
    rows = _rows(r)
    assert len(rows) == 1
    task = rows[0]
    assert task["status"] == "open"
    assert task["source_tags"] == ["Rewe"]
    assert task["completed_at"] is None
    assert task["item_id"] == STORED_ITEM_ID


# ── Duplicate Open Task Rejected ──────────────────────────────────────────────

def test_duplicate_open_task_rejected(client):
    """POST shopping-tasks for item that already has open task returns 409."""
    r = client.post("/api/shopping-tasks", json={"item_id": LOW_STOCK_ITEM_ID})
    assert r.status_code == 409
    assert "error" in r.json()


# ── Auto Task Creation On Low Stock Transition ────────────────────────────────

def test_auto_task_creation_on_low_stock(client):
    """PATCH item to low_stock state auto-creates a shopping task."""
    # watch_item starts stored with no open task
    r = client.patch(f"/api/items/{WATCH_ITEM_ID}", json={"state": "low_stock"})
    assert r.status_code == 200

    # There should now be an open task for watch_item
    r = client.get("/api/shopping-tasks?status=open")
    assert r.status_code == 200
    item_ids = {row["item_id"] for row in _rows(r)}
    assert WATCH_ITEM_ID in item_ids


# ── Auto Task Not Duplicated On Repeated Low Stock ────────────────────────────

def test_auto_task_not_duplicated(client):
    """PATCH an item that stays low_stock does not create a second task."""
    # low_stock_item is already low_stock with one open task
    r = client.patch(f"/api/items/{LOW_STOCK_ITEM_ID}", json={"notes": "updated notes"})
    assert r.status_code == 200

    # Count open tasks for this item — must still be exactly 1
    r = client.get("/api/shopping-tasks?status=open")
    assert r.status_code == 200
    tasks_for_item = [row for row in _rows(r) if row["item_id"] == LOW_STOCK_ITEM_ID]
    assert len(tasks_for_item) == 1


# ── Task Done With Restock Quantity ───────────────────────────────────────────

def test_task_done_with_restock_quantity(client):
    """Done task with restock_quantity: item.quantity=6, state=stored (6 > 3)."""
    r = client.patch(f"/api/shopping-tasks/{MILK_TASK_ID}", json={"status": "done"})
    assert r.status_code == 200
    task = _rows(r)[0]
    assert task["status"] == "done"
    assert task["completed_at"] is not None

    # Item should be updated
    r = client.get(f"/api/items/{RESTOCK_MILK_ID}")
    item = _rows(r)[0]
    assert item["quantity"] == 6
    assert item["state"] == "stored"


# ── Task Done Restock Still Low Stock ─────────────────────────────────────────

def test_task_done_restock_still_low_stock(client):
    """Done task where restock_qty=4 <= min_qty=5: item stays low_stock."""
    r = client.patch(f"/api/shopping-tasks/{LOW_RESTOCK_TASK_ID}", json={"status": "done"})
    assert r.status_code == 200
    task = _rows(r)[0]
    assert task["status"] == "done"

    r = client.get(f"/api/items/{LOW_RESTOCK_ID}")
    item = _rows(r)[0]
    assert item["quantity"] == 4
    assert item["state"] == "low_stock"


# ── Task Done Without Restock Quantity ────────────────────────────────────────

def test_task_done_without_restock_quantity(client):
    """Done task with no restock_quantity: item.state=stored, quantity unchanged (null)."""
    r = client.patch(f"/api/shopping-tasks/{CABLE_TASK_ID}", json={"status": "done"})
    assert r.status_code == 200
    task = _rows(r)[0]
    assert task["status"] == "done"
    assert task["completed_at"] is not None

    r = client.get(f"/api/items/{CABLE_ID}")
    item = _rows(r)[0]
    assert item["state"] == "stored"
    assert item["quantity"] is None


# ── Task Dismissed ────────────────────────────────────────────────────────────

def test_task_dismissed(client):
    """Dismissed task: task.completed_at set; item state unchanged."""
    r = client.patch(f"/api/shopping-tasks/{DISMISS_TASK_ID}", json={"status": "dismissed"})
    assert r.status_code == 200
    task = _rows(r)[0]
    assert task["status"] == "dismissed"
    assert task["completed_at"] is not None

    r = client.get(f"/api/items/{DISMISS_ITEM_ID}")
    item = _rows(r)[0]
    assert item["state"] == "low_stock"


# ── List Tasks Default Open ───────────────────────────────────────────────────

def test_list_tasks_default_open(client):
    """GET /shopping-tasks returns only open tasks by default."""
    r = client.get("/api/shopping-tasks")
    assert r.status_code == 200
    rows = _rows(r)
    statuses = {row["status"] for row in rows}
    assert statuses == {"open"}
    # Done and dismissed tasks must not appear
    assert DONE_TASK_ID not in _task_ids(r)
    assert DISMISSED_TASK_ID not in _task_ids(r)


# ── List Tasks By Status Done ─────────────────────────────────────────────────

def test_list_tasks_by_status(client):
    """GET /shopping-tasks?status=done returns only done tasks."""
    r = client.get("/api/shopping-tasks?status=done")
    assert r.status_code == 200
    rows = _rows(r)
    statuses = {row["status"] for row in rows}
    assert statuses == {"done"}
    assert DONE_TASK_ID in _task_ids(r)


# ── By Source Grouping No Tags ────────────────────────────────────────────────

def test_by_source_grouping_no_tags(client):
    """notag_task (source_tags=[]) appears in 'Other' group in by_source."""
    r = client.get("/api/shopping-tasks/views/by_source")
    assert r.status_code == 200
    rows = _rows(r)
    other_rows = [row for row in rows if row["source_tag"] == "Other"]
    other_ids = {row["id"] for row in other_rows}
    assert NOTAG_TASK_ID in other_ids


# ── By Source Grouping Single Tag ─────────────────────────────────────────────

def test_by_source_grouping_single_tag(client):
    """open_task (source_tags=['DM']) appears in 'DM' group in by_source."""
    r = client.get("/api/shopping-tasks/views/by_source")
    assert r.status_code == 200
    rows = _rows(r)
    dm_rows = [row for row in rows if row["source_tag"] == "DM"]
    dm_ids = {row["id"] for row in dm_rows}
    assert OPEN_TASK_ID in dm_ids


# ── By Source Multi Tag Duplication ──────────────────────────────────────────

def test_by_source_multi_tag_duplication(client):
    """multi_task (source_tags=['Rewe','Amazon']) appears in both 'Rewe' and 'Amazon' groups."""
    r = client.get("/api/shopping-tasks/views/by_source")
    assert r.status_code == 200
    rows = _rows(r)

    rewe_ids   = {row["id"] for row in rows if row["source_tag"] == "Rewe"}
    amazon_ids = {row["id"] for row in rows if row["source_tag"] == "Amazon"}

    assert MULTI_TASK_ID in rewe_ids
    assert MULTI_TASK_ID in amazon_ids


# ── Delete Task ───────────────────────────────────────────────────────────────

def test_delete_task(client):
    """DELETE /shopping-tasks/{id} removes task; subsequent GET does not include it."""
    r = client.delete(f"/api/shopping-tasks/{DELETE_TASK_ID}")
    assert r.status_code == 200
    assert _rows(r) == []

    # Task must not appear in open list
    r = client.get("/api/shopping-tasks?status=open")
    assert DELETE_TASK_ID not in _task_ids(r)


# ── Delete Nonexistent Task ───────────────────────────────────────────────────

def test_delete_nonexistent_task(client):
    """DELETE /shopping-tasks/{unknown-id} returns 404."""
    r = client.delete("/api/shopping-tasks/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    assert "error" in r.json()


# ── Item Delete Cascades To Tasks ─────────────────────────────────────────────

def test_item_delete_cascades_to_tasks(client):
    """DELETE /items/{id} removes the item and its open shopping task."""
    # Confirm the cascade task exists before deletion
    r = client.get("/api/shopping-tasks?status=open")
    assert CASCADE_TASK_ID in _task_ids(r)

    # Delete the item
    r = client.delete(f"/api/items/{CASCADE_ITEM_ID}")
    assert r.status_code == 200

    # The task must be gone (cascade)
    r = client.get("/api/shopping-tasks?status=open")
    assert CASCADE_TASK_ID not in _task_ids(r)
