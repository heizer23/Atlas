"""
HTTP tests for PersonalDevelopment Sprint01-Core.

Tests run inside the atlas-tasktracker-test container against atlas_test DB.
Fixtures are loaded by conftest.py clean_tables before each test.

Fixture IDs:
  00000000-0000-0000-0000-000000000001 = fix-unit-1 (Learn Python, open, high)
  00000000-0000-0000-0000-000000000002 = fix-child-1 (Python Session 1, done, completed_at=2026-04-01)
  00000000-0000-0000-0000-000000000003 = fix-child-2 (Python Session 2, open)
  00000000-0000-0000-0000-000000000004 = fix-unit-done (Learn Rust, done, medium)
  00000000-0000-0000-0000-000000000005 = fix-unit-open-low (Learn SQL, open, low)
  00000000-0000-0000-0000-000000000006 = fix-normal-1 (Buy groceries, normal)
"""

UNIT_1  = "00000000-0000-0000-0000-000000000001"
CHILD_1 = "00000000-0000-0000-0000-000000000002"
CHILD_2 = "00000000-0000-0000-0000-000000000003"
UNIT_DONE = "00000000-0000-0000-0000-000000000004"
UNIT_LOW  = "00000000-0000-0000-0000-000000000005"
NORMAL_1  = "00000000-0000-0000-0000-000000000006"


# ── Training Units — Empty Result ─────────────────────────────────────────────

def test_training_units_empty_result(client, db_conn):
    """Training Units — Empty Result"""
    # Clear all tasks including fixtures
    with db_conn.cursor() as cur:
        cur.execute("truncate tasktracker.tasks cascade")

    r = client.get("/api/tasks/training-units")
    assert r.status_code == 200
    body = r.json()
    assert body["rows"] == []
    assert body["meta"]["total"] == 0


# ── Training Units — Single Unit No Children ──────────────────────────────────

def test_training_units_single_unit_no_children(client, db_conn):
    """Training Units — Single Unit No Children"""
    # Clear all, insert only one unit with no children
    with db_conn.cursor() as cur:
        cur.execute("truncate tasktracker.tasks cascade")
        cur.execute(
            """
            insert into tasktracker.tasks (id, title, status, priority, task_type)
            values (%s, 'Solo Unit', 'open', 'high', 'training_unit')
            """,
            ("00000000-0000-0000-0000-000000000099",),
        )

    r = client.get("/api/tasks/training-units")
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert len(rows) == 1
    row = rows[0]
    assert row["completed_child_count"] == 0
    assert row["total_child_count"] == 0
    assert row["last_child_completed_at"] is None


# ── Training Units — Unit With Mixed Children ─────────────────────────────────

def test_training_units_unit_with_mixed_children(client):
    """Training Units — Unit With Mixed Children"""
    r = client.get("/api/tasks/training-units")
    assert r.status_code == 200
    rows = r.json()["rows"]

    unit1_row = next((row for row in rows if row["id"] == UNIT_1), None)
    assert unit1_row is not None
    assert unit1_row["completed_child_count"] == 1
    assert unit1_row["total_child_count"] == 2
    assert unit1_row["last_child_completed_at"] is not None
    assert "2026-04-01" in unit1_row["last_child_completed_at"]


# ── Training Units — Sort Order ───────────────────────────────────────────────

def test_training_units_sort_order_done_before_open_then_priority(client):
    """Training Units — Sort Order: Done Before Open, Then By Priority"""
    r = client.get("/api/tasks/training-units")
    assert r.status_code == 200
    rows = r.json()["rows"]

    ids = [row["id"] for row in rows]
    done_idx      = ids.index(UNIT_DONE)
    unit1_idx     = ids.index(UNIT_1)    # open, high
    unit_low_idx  = ids.index(UNIT_LOW)  # open, low

    # Done comes first
    assert done_idx < unit1_idx
    assert done_idx < unit_low_idx
    # High priority before low priority (both open)
    assert unit1_idx < unit_low_idx


# ── Training Units — Labels Embedded ─────────────────────────────────────────

def test_training_units_labels_embedded(client):
    """Training Units — Labels Embedded (labels field exists and is a list)"""
    r = client.get("/api/tasks/training-units")
    assert r.status_code == 200
    rows = r.json()["rows"]
    for row in rows:
        assert "labels" in row
        assert isinstance(row["labels"], list)


# ── Main Task List Excludes Training Units ────────────────────────────────────

def test_main_task_list_excludes_training_units(client):
    """Main Task List Excludes Training Units"""
    r = client.get("/api/tasks")
    assert r.status_code == 200
    rows = r.json()["rows"]
    ids = [row["id"] for row in rows]

    # Normal and training_session tasks should be present
    assert NORMAL_1 in ids
    assert CHILD_1 in ids
    assert CHILD_2 in ids

    # Training units must be absent
    assert UNIT_1 not in ids
    assert UNIT_DONE not in ids
    assert UNIT_LOW not in ids


# ── Main Task List Excludes Training Units — Active View ─────────────────────

def test_main_task_list_active_view_excludes_training_units(client):
    """Main Task List Excludes Training Units — Active View"""
    r = client.get("/api/tasks?view=active")
    assert r.status_code == 200
    rows = r.json()["rows"]
    ids = [row["id"] for row in rows]

    assert UNIT_1 not in ids
    assert UNIT_DONE not in ids
    assert UNIT_LOW not in ids


# ── Create Training Unit Task ─────────────────────────────────────────────────

def test_create_training_unit_task(client):
    """Create Training Unit Task"""
    r = client.post("/api/tasks", json={
        "title":     "Learn Python",
        "task_type": "training_unit",
        "status":    "open",
        "priority":  "high",
    })
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert len(rows) == 1
    row = rows[0]
    assert row["task_type"] == "training_unit"
    assert row["status"] == "open"
    # id should be a UUID (36 chars with dashes)
    assert len(row["id"]) == 36


# ── Create Training Session With Parent ───────────────────────────────────────

def test_create_training_session_with_parent(client):
    """Create Training Session With Parent"""
    r = client.post("/api/tasks", json={
        "title":          "Session 1",
        "task_type":      "training_session",
        "parent_task_id": UNIT_1,
        "status":         "open",
        "priority":       "medium",
    })
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert len(rows) == 1
    row = rows[0]
    assert row["task_type"] == "training_session"
    assert row["parent_task_id"] == UNIT_1


# ── PATCH — completed_at Set Server-Side On Done Transition ──────────────────

def test_patch_completed_at_set_on_done_transition(client):
    """PATCH — completed_at Set Server-Side On Done Transition"""
    r = client.patch(f"/api/tasks/{CHILD_2}", json={"status": "done"})
    assert r.status_code == 200
    row = r.json()["rows"][0]
    assert row["status"] == "done"
    assert row["completed_at"] is not None


# ── PATCH — completed_at Not Overwritten If Already Set ──────────────────────

def test_patch_completed_at_not_overwritten(client):
    """PATCH — completed_at Not Overwritten If Already Set"""
    # CHILD_1 is already done with completed_at = 2026-04-01T10:00:00Z
    r = client.patch(f"/api/tasks/{CHILD_1}", json={"title": "Updated title"})
    assert r.status_code == 200
    row = r.json()["rows"][0]
    assert "2026-04-01" in row["completed_at"]


# ── PATCH — completed_at Not Set When Transitioning To Non-Done ───────────────

def test_patch_completed_at_not_set_for_non_done(client):
    """PATCH — completed_at Not Set When Transitioning To Non-Done Status"""
    # CHILD_2 is open with completed_at = null
    r = client.patch(f"/api/tasks/{CHILD_2}", json={"status": "in_progress"})
    assert r.status_code == 200
    row = r.json()["rows"][0]
    assert row["status"] == "in_progress"
    assert row["completed_at"] is None


# ── PATCH — actual_duration_minutes Update ────────────────────────────────────

def test_patch_actual_duration_minutes(client):
    """PATCH — actual_duration_minutes Update"""
    r = client.patch(f"/api/tasks/{CHILD_2}", json={"actual_duration_minutes": 45})
    assert r.status_code == 200
    row = r.json()["rows"][0]
    assert row["actual_duration_minutes"] == 45


# ── Child task list via parent_task_id filter ─────────────────────────────────

def test_get_tasks_by_parent_task_id(client):
    """GET /api/tasks?task_type=training_session&parent_task_id fetches child tasks."""
    r = client.get(f"/api/tasks?task_type=training_session&parent_task_id={UNIT_1}")
    assert r.status_code == 200
    rows = r.json()["rows"]
    ids = [row["id"] for row in rows]
    assert CHILD_1 in ids
    assert CHILD_2 in ids
    # Should not include the unit itself
    assert UNIT_1 not in ids
