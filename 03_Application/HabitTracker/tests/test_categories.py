"""Tests for categories, priorities and derived category progress."""

import pytest

from backend.category_progress import category_levels

BASE = "/api/habittracker"
DAY = "2026-03-10"


def _cat(client, name="Body", kind="achievement"):
    cats = {c["name"]: c for c in client.get(f"{BASE}/categories").json()["rows"]}
    if name in cats:
        return cats[name]
    r = client.post(f"{BASE}/categories", json={"name": name, "kind": kind})
    assert r.status_code == 201
    return r.json()


def _habit(client, name, cat, priority):
    r = client.post(f"{BASE}/habits", json={
        "name": name, "active_from": "2026-01-01", "category_id": cat["id"], "priority": priority})
    assert r.status_code == 201, r.text
    return r.json()


def _tap(client, habit, day=DAY):
    assert client.post(f"{BASE}/habits/{habit['id']}/entries", json={"date": day}).status_code in (200, 201)


def _level(client, cat, day=DAY):
    cats = client.get(f"{BASE}/today", params={"date": day}).json()["categories"]
    return {c["id"]: c["level"] for c in cats}[cat["id"]]


@pytest.fixture
def body(client, db_conn):
    # Isolated category with only our habits (fixtures' own habits stay uncategorised).
    with db_conn.cursor() as cur:
        cur.execute("delete from habittracker.habit_categories where name = 'TestBody'")
    return _cat(client, "TestBody")


def test_seeded_categories_and_priorities(client):
    data = client.get(f"{BASE}/categories").json()
    assert {"Body", "Mind", "Organization", "Discipline"} <= {c["name"] for c in data["rows"]}
    assert [p["level"] for p in data["priorities"]] == [1, 2, 3]


def test_highest_priority_wins_and_minor_habits_do_not_add_up(client, body):
    wall = _habit(client, "Wall angels", body, 1)
    stretch = _habit(client, "Stretching", body, 2)
    other_minor = _habit(client, "Minor two", body, 1)
    full = _habit(client, "Full workout", body, 3)
    assert _level(client, body) == 0
    _tap(client, wall)
    assert _level(client, body) == 1
    _tap(client, other_minor)
    assert _level(client, body) == 1          # many minor habits never outweigh a bigger one
    _tap(client, stretch)
    assert _level(client, body) == 2
    _tap(client, full)
    assert _level(client, body) == 3


def test_major_alone_gives_level_three(client, body):
    _habit(client, "Wall angels", body, 1)
    full = _habit(client, "Full workout", body, 3)
    _tap(client, full)
    assert _level(client, body) == 3


def test_undo_lowers_level_and_category_progress_history(client, body):
    wall = _habit(client, "Wall angels", body, 1)
    full = _habit(client, "Full workout", body, 3)
    _tap(client, wall, "2026-03-09")
    _tap(client, full, DAY)
    r = client.get(f"{BASE}/category-progress", params={"days": 3, "end": "2026-03-11", "category_id": body["id"]})
    assert r.status_code == 200
    assert r.json()["dates"] == ["2026-03-09", "2026-03-10", "2026-03-11"]
    assert r.json()["categories"][0]["levels"] == [1, 3, 0]
    client.delete(f"{BASE}/habits/{full['id']}/entries/last", params={"date": DAY})
    assert _level(client, body) == 0


def test_category_progress_validation(client):
    assert client.get(f"{BASE}/category-progress", params={"days": 0}).status_code == 400
    assert client.get(f"{BASE}/category-progress",
                      params={"category_id": "00000000-0000-0000-0000-000000000000"}).status_code == 404


def test_null_before_habits_are_active(client, body):
    _habit(client, "Wall angels", body, 1)
    levels = client.get(f"{BASE}/category-progress",
                        params={"days": 2, "end": "2025-12-31", "category_id": body["id"]}).json()
    assert levels["categories"][0]["levels"] == [None, None]


def test_uncategorised_habit_ignored_and_assignment_roundtrip(client, body):
    h = client.post(f"{BASE}/habits", json={"name": "Legacy", "active_from": "2026-01-01"}).json()
    assert h["category_id"] is None and h["priority"] is None
    _tap(client, h)
    assert _level(client, body) is None       # no habit of the category is active
    r = client.patch(f"{BASE}/habits/{h['id']}", json={"category_id": body["id"], "priority": 2})
    assert (r.json()["category_id"], r.json()["priority"]) == (body["id"], 2)
    assert _level(client, body) == 2
    r = client.patch(f"{BASE}/habits/{h['id']}", json={"priority": None})        # explicit null clears
    assert r.json()["priority"] is None and r.json()["category_id"] == body["id"]
    r = client.patch(f"{BASE}/habits/{h['id']}", json={"name": "Legacy2"})        # omitted leaves it
    assert r.json()["category_id"] == body["id"]
    assert _level(client, body) == 0          # done, but unranked habit contributes no level
    assert client.patch(f"{BASE}/habits/{h['id']}", json={"priority": 9}).status_code == 400
    assert client.patch(f"{BASE}/habits/{h['id']}", json={"category_id": "nope"}).status_code == 400
    r = client.patch(f"{BASE}/habits/{h['id']}", json={"category_id": None})
    assert r.json()["category_id"] is None


def test_history_category_filter(client, body):
    h = _habit(client, "Only one", body, 1)
    _tap(client, h)
    days = client.get(f"{BASE}/history", params={"days": 1, "end": DAY, "category_id": body["id"]}).json()["days"]
    assert (days[0]["done"], days[0]["tracked"]) == (1, 1)


def test_category_crud_validation(client):
    assert client.post(f"{BASE}/categories", json={"name": ""}).status_code == 400
    assert client.post(f"{BASE}/categories", json={"name": "X", "kind": "bogus"}).status_code == 400
    c = _cat(client, "TestRename")
    r = client.patch(f"{BASE}/categories/{c['id']}", json={"name": "TestRename2"})
    assert r.json()["name"] == "TestRename2"
    assert client.patch(f"{BASE}/priorities/2", json={"label": "Solid"}).json()["label"] == "Solid"
    assert client.patch(f"{BASE}/priorities/7", json={"label": "x"}).status_code == 404
    client.patch(f"{BASE}/priorities/2", json={"label": "Meaningful"})


def test_discipline_counts_only_explicit_done():
    cats = [{"id": "d", "kind": "discipline"}]
    # No confirmation (done False) is not success; explicit one counts by priority.
    assert category_levels(cats, [{"category_id": "d", "priority": 3, "done": False}])["d"] == 0
    assert category_levels(cats, [{"category_id": "d", "priority": 2, "done": True},
                                  {"category_id": "d", "priority": 3, "done": False}])["d"] == 2
    assert category_levels(cats, [])["d"] is None
