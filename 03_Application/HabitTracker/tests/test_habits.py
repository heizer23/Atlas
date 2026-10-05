"""
Tests for GET/POST /habits, PATCH /habits/{id}, POST /habits/reorder.

Scenario -> test function mapping (10_test_spec.md):
  Habit list — starter seed present on first run
    -> test_habit_list_starter_seed_on_first_run
  Habit list — seeding is a one-time, table-emptiness check
    -> test_habit_list_seeding_is_one_time_table_emptiness_check
  Create habit — success -> test_create_habit_success
  Create habit — missing name is rejected -> test_create_habit_missing_name_rejected
  Update habit — partial update leaves other fields unchanged
    -> test_update_habit_partial_update_leaves_other_fields_unchanged
  Update habit — explicit null clears description
    -> test_update_habit_explicit_null_clears_description
  Update habit — omitting description leaves it unchanged
    -> test_update_habit_omitting_description_leaves_it_unchanged
  Update habit — explicit null on name is rejected
    -> test_update_habit_explicit_null_on_name_is_rejected
  Update habit — archiving via end_date -> test_update_habit_archiving_via_end_date
  Update habit — un-archiving by explicit null
    -> test_update_habit_unarchiving_by_explicit_null
  Update habit — end_date before active_from is rejected
    -> test_update_habit_end_date_before_active_from_is_rejected
  Update habit — unknown id -> test_update_habit_unknown_id
  Reorder habits — full permutation including a swap
    -> test_reorder_habits_full_permutation_including_a_swap
  Reorder habits — mismatched id set is rejected
    -> test_reorder_habits_mismatched_id_set_is_rejected
"""

BASE = "/api/habittracker"

WORKED_OUT_ID = "10000001-0000-0000-0000-000000000001"
NO_SWEETS_ID  = "10000002-0000-0000-0000-000000000002"
NO_VAPING_ID  = "10000003-0000-0000-0000-000000000003"
BP_ID         = "10000004-0000-0000-0000-000000000004"
ESSAYCARDS_ID = "10000005-0000-0000-0000-000000000005"
ARCHIVED_ID   = "10000006-0000-0000-0000-000000000006"

ALL_FIXTURE_IDS = [WORKED_OUT_ID, NO_SWEETS_ID, NO_VAPING_ID, BP_ID, ESSAYCARDS_ID, ARCHIVED_ID]

STARTER_NAMES = [
    "Worked out",
    "No sweets",
    "No vaping",
    "Measured blood pressure",
    "Reviewed EssayCards",
]


# ── Habit list / seeding ──────────────────────────────────────────────────────

def test_habit_list_starter_seed_on_first_run(client, db_conn):
    """Deviation (logged as EVD-2026-10-01-001 in agent_rule_evidence.md):
    this scenario requires a genuinely empty habits table at GET-time, which
    the standard fixtures.sql-based per-test reset cannot provide alongside
    the named habit fixtures every other scenario needs (fixtures.sql always
    populates 6 named habits before each test). Truncating locally here,
    within this one test only, and reseeding directly, is how this scenario
    is made testable without disturbing the shared fixtures.sql convention.
    """
    with db_conn.cursor() as cur:
        cur.execute("truncate habittracker.daily_reviews, habittracker.habits cascade")

    import backend.database as db_module
    db_module.seed_starter_habits()

    r = client.get(f"{BASE}/habits")
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert len(rows) == 5
    assert [row["name"] for row in rows] == STARTER_NAMES
    assert all(row["default_checked"] is False for row in rows)
    orders = [row["display_order"] for row in rows]
    assert orders == sorted(orders)


def test_habit_list_seeding_is_one_time_table_emptiness_check(client, db_conn):
    r = client.patch(f"{BASE}/habits/{WORKED_OUT_ID}", json={"name": "Exercised today"})
    assert r.status_code == 200

    with db_conn.cursor() as cur:
        cur.execute("select count(*) as n from habittracker.habits")
        before = cur.fetchone()["n"]

    import backend.database as db_module
    db_module.seed_starter_habits()

    with db_conn.cursor() as cur:
        cur.execute("select count(*) as n from habittracker.habits")
        after = cur.fetchone()["n"]
    assert after == before

    r2 = client.get(f"{BASE}/habits")
    renamed = next(h for h in r2.json()["rows"] if h["id"] == WORKED_OUT_ID)
    assert renamed["name"] == "Exercised today"


# ── Create ────────────────────────────────────────────────────────────────────

def test_create_habit_success(client):
    r = client.post(f"{BASE}/habits", json={
        "name": "Read 10 pages",
        "default_checked": False,
        "active_from": "2026-10-01",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Read 10 pages"
    assert body["display_order"] == 6  # one past the current max (0..5 already used)


def test_create_habit_missing_name_rejected(client, db_conn):
    with db_conn.cursor() as cur:
        cur.execute("select count(*) as n from habittracker.habits")
        before = cur.fetchone()["n"]

    r = client.post(f"{BASE}/habits", json={
        "default_checked": False,
        "active_from": "2026-10-01",
    })
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"

    with db_conn.cursor() as cur:
        cur.execute("select count(*) as n from habittracker.habits")
        after = cur.fetchone()["n"]
    assert after == before


# ── Update ────────────────────────────────────────────────────────────────────

def test_update_habit_partial_update_leaves_other_fields_unchanged(client):
    before = client.get(f"{BASE}/habits").json()["rows"]
    before_row = next(h for h in before if h["id"] == NO_SWEETS_ID)
    assert before_row["description"] is None

    r = client.patch(f"{BASE}/habits/{NO_SWEETS_ID}", json={"default_checked": True})
    assert r.status_code == 200
    body = r.json()
    assert body["default_checked"] is True
    assert body["name"] == before_row["name"]
    assert body["description"] is None
    assert body["active_from"] == before_row["active_from"]


def test_update_habit_explicit_null_clears_description(client):
    r = client.patch(f"{BASE}/habits/{NO_SWEETS_ID}", json={"description": "Avoid dessert and candy"})
    assert r.status_code == 200
    assert r.json()["description"] == "Avoid dessert and candy"

    r2 = client.patch(f"{BASE}/habits/{NO_SWEETS_ID}", json={"description": None})
    assert r2.status_code == 200
    assert r2.json()["description"] is None


def test_update_habit_omitting_description_leaves_it_unchanged(client):
    r = client.patch(f"{BASE}/habits/{NO_SWEETS_ID}", json={"description": "Avoid dessert and candy"})
    assert r.status_code == 200

    r2 = client.patch(f"{BASE}/habits/{NO_SWEETS_ID}", json={"default_checked": True})
    assert r2.status_code == 200
    assert r2.json()["description"] == "Avoid dessert and candy"


def test_update_habit_explicit_null_on_name_is_rejected(client):
    r = client.patch(f"{BASE}/habits/{NO_SWEETS_ID}", json={"name": None})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"

    r2 = client.get(f"{BASE}/habits")
    row = next(h for h in r2.json()["rows"] if h["id"] == NO_SWEETS_ID)
    assert row["name"] == "No sweets"


def test_update_habit_archiving_via_end_date(client):
    r = client.patch(f"{BASE}/habits/{NO_VAPING_ID}", json={"end_date": "2026-10-15"})
    assert r.status_code == 200
    assert r.json()["end_date"] == "2026-10-15"

    r2 = client.get(f"{BASE}/habits")
    ids = [h["id"] for h in r2.json()["rows"]]
    assert NO_VAPING_ID in ids


def test_update_habit_unarchiving_by_explicit_null(client):
    r = client.patch(f"{BASE}/habits/{ARCHIVED_ID}", json={"end_date": None})
    assert r.status_code == 200
    assert r.json()["end_date"] is None


def test_update_habit_end_date_before_active_from_is_rejected(client):
    r = client.patch(f"{BASE}/habits/{NO_VAPING_ID}", json={"end_date": "2025-12-31"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"

    r2 = client.get(f"{BASE}/habits")
    row = next(h for h in r2.json()["rows"] if h["id"] == NO_VAPING_ID)
    assert row["end_date"] is None


def test_update_habit_unknown_id(client):
    r = client.patch(f"{BASE}/habits/00000000-0000-0000-0000-000000000000", json={"default_checked": True})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


# ── Reorder ───────────────────────────────────────────────────────────────────

def test_reorder_habits_full_permutation_including_a_swap(client):
    reversed_ids = list(reversed(ALL_FIXTURE_IDS))
    r = client.post(f"{BASE}/habits/reorder", json={"habit_ids": reversed_ids})
    assert r.status_code == 200

    r2 = client.get(f"{BASE}/habits")
    rows = r2.json()["rows"]
    assert [row["id"] for row in rows] == reversed_ids
    orders = [row["display_order"] for row in rows]
    assert orders == list(range(len(ALL_FIXTURE_IDS)))
    assert len(set(orders)) == len(orders)


def test_reorder_habits_mismatched_id_set_is_rejected(client):
    r = client.post(f"{BASE}/habits/reorder", json={"habit_ids": ALL_FIXTURE_IDS[:4]})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"

    r2 = client.get(f"{BASE}/habits")
    rows = r2.json()["rows"]
    orders = sorted(row["display_order"] for row in rows)
    assert orders == list(range(len(ALL_FIXTURE_IDS)))
