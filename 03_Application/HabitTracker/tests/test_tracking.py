"""Tests for everyday tracking: /today, entries (log/undo), /history, habit kind fields."""

BASE = "/api/habittracker"
WORKED_OUT = "10000001-0000-0000-0000-000000000001"
NO_SWEETS = "10000002-0000-0000-0000-000000000002"
DAY = "2026-03-10"


def _make_quantity(client, name="Wall angels", unit="reps", increment=5):
    r = client.post(f"{BASE}/habits", json={
        "name": name, "active_from": "2026-01-01", "kind": "quantity", "unit": unit, "increment": increment})
    assert r.status_code == 201
    return r.json()


def _today(client, day=DAY):
    return {h["habit_id"]: h for h in client.get(f"{BASE}/today", params={"date": day}).json()["habits"]}


def test_create_quantity_habit_and_track_immediately(client):
    h = _make_quantity(client)
    assert (h["kind"], h["unit"], h["increment"]) == ("quantity", "reps", 5)
    assert _today(client)[h["id"]]["total"] == 0


def test_quantity_accumulates_per_tap_and_undo_corrects(client):
    h = _make_quantity(client)
    for _ in range(3):
        assert client.post(f"{BASE}/habits/{h['id']}/entries", json={"date": DAY}).status_code == 201
    t = _today(client)[h["id"]]
    assert (t["total"], t["done"]) == (15, True)
    r = client.delete(f"{BASE}/habits/{h['id']}/entries/last", params={"date": DAY})
    assert r.json()["total"] == 10
    for _ in range(2):
        client.delete(f"{BASE}/habits/{h['id']}/entries/last", params={"date": DAY})
    t = _today(client)[h["id"]]
    assert (t["total"], t["done"]) == (0, False)
    # undo on empty day is a harmless no-op
    assert client.delete(f"{BASE}/habits/{h['id']}/entries/last", params={"date": DAY}).json()["total"] == 0


def test_binary_is_idempotent_and_undoable(client):
    assert client.post(f"{BASE}/habits/{WORKED_OUT}/entries", json={"date": DAY}).status_code == 201
    r = client.post(f"{BASE}/habits/{WORKED_OUT}/entries", json={"date": DAY})
    assert r.json()["total"] == 1
    assert _today(client)[WORKED_OUT]["done"] is True
    client.delete(f"{BASE}/habits/{WORKED_OUT}/entries/last", params={"date": DAY})
    assert _today(client)[WORKED_OUT]["done"] is False


def test_entries_are_per_day_and_persist(client):
    client.post(f"{BASE}/habits/{WORKED_OUT}/entries", json={"date": DAY})
    assert _today(client, "2026-03-11")[WORKED_OUT]["done"] is False
    assert _today(client, DAY)[WORKED_OUT]["done"] is True


def test_today_excludes_archived_habits(client):
    ids = _today(client).keys()
    assert "10000006-0000-0000-0000-000000000006" not in ids
    assert WORKED_OUT in ids


def test_unknown_habit_and_bad_date(client):
    bogus = "99999999-0000-0000-0000-000000000000"
    assert client.post(f"{BASE}/habits/{bogus}/entries", json={}).status_code == 404
    assert client.post(f"{BASE}/habits/{WORKED_OUT}/entries", json={"date": "nope"}).status_code == 400
    assert client.get(f"{BASE}/history", params={"days": 0}).status_code == 400


def test_history_counts_done_over_tracked(client, db_conn):
    h = _make_quantity(client)
    client.post(f"{BASE}/habits/{h['id']}/entries", json={"date": DAY})
    client.post(f"{BASE}/habits/{WORKED_OUT}/entries", json={"date": DAY})
    # legacy evening-review data also counts
    with db_conn.cursor() as cur:
        cur.execute("insert into habittracker.daily_reviews (review_date, status) values (%s, 'confirmed')", (DAY,))
        cur.execute("insert into habittracker.habit_results (review_date, habit_id, checked) values (%s, %s, true)",
                    (DAY, NO_SWEETS))
    days = client.get(f"{BASE}/history", params={"days": 3, "end": "2026-03-11"}).json()["days"]
    assert [d["date"] for d in days] == ["2026-03-09", "2026-03-10", "2026-03-11"]
    assert (days[0]["done"], days[1]["done"], days[2]["done"]) == (0, 3, 0)
    assert days[1]["tracked"] == 6  # 5 starters + new habit; archived one excluded


def test_update_kind_fields_and_validation(client):
    r = client.patch(f"{BASE}/habits/{WORKED_OUT}", json={"kind": "quantity", "unit": "min", "increment": 10})
    assert r.status_code == 200 and r.json()["increment"] == 10
    assert client.patch(f"{BASE}/habits/{WORKED_OUT}", json={"increment": 0}).status_code == 400
    assert client.patch(f"{BASE}/habits/{WORKED_OUT}", json={"kind": "weird"}).status_code == 400


# ── Linked habits (EssayCards) ────────────────────────────────────────────────

def _linked(db_conn, source, name, active_from="2026-01-01"):
    with db_conn.cursor() as cur:
        cur.execute("""insert into habittracker.habits (name, display_order, active_from, source)
                       values (%s, (select max(display_order) + 1 from habittracker.habits), %s, %s) returning id""", (name, active_from, source))
        return str(cur.fetchone()["id"])


def _fake_activity(monkeypatch, flash=(), oral=()):
    from backend import essaycards_activity
    monkeypatch.setattr(essaycards_activity, "done_days", lambda s, e: {
        "essaycards_flashcards": {d for d in flash if s.isoformat() <= d <= e.isoformat()},
        "essaycards_oral": {d for d in oral if s.isoformat() <= d <= e.isoformat()}})


def test_linked_habits_follow_essaycards_and_reject_manual_logging(client, db_conn, monkeypatch):
    fc = _linked(db_conn, "essaycards_flashcards", "Flashcards")
    oral = _linked(db_conn, "essaycards_oral", "Oral practice")
    _fake_activity(monkeypatch, flash=[DAY])
    t = _today(client)
    assert t[fc]["done"] is True and t[fc]["linked"] is True
    assert t[oral]["done"] is False
    assert client.post(f"{BASE}/habits/{fc}/entries", json={"date": DAY}).status_code == 400
    assert client.delete(f"{BASE}/habits/{fc}/entries/last", params={"date": DAY}).status_code == 400


def test_history_counts_each_linked_habit_once(client, db_conn, monkeypatch):
    _linked(db_conn, "essaycards_flashcards", "Flashcards")
    _linked(db_conn, "essaycards_oral", "Oral practice")
    _fake_activity(monkeypatch, flash=[DAY], oral=[DAY, "2026-03-09"])
    days = {d["date"]: d for d in client.get(f"{BASE}/history", params={"days": 3, "end": "2026-03-11"}).json()["days"]}
    assert days[DAY]["done"] == 2 and days["2026-03-09"]["done"] == 1 and days["2026-03-11"]["done"] == 0
    assert days[DAY]["tracked"] == 7


def test_essaycards_unreachable_degrades_to_not_done(client, db_conn, monkeypatch):
    from backend import essaycards_activity
    fc = _linked(db_conn, "essaycards_flashcards", "Flashcards")
    monkeypatch.setattr(essaycards_activity, "_fetch", lambda s, e: None)
    assert _today(client)[fc]["done"] is False
    assert client.get(f"{BASE}/history", params={"days": 3}).status_code == 200


def test_seed_linked_habits_is_once_per_source(client, db_conn, monkeypatch):
    from backend import database, essaycards_activity
    monkeypatch.setattr(essaycards_activity, "first_day", lambda src: None)
    database.seed_linked_habits()
    database.seed_linked_habits()
    with db_conn.cursor() as cur:
        cur.execute("select source, count(*) n from habittracker.habits where source is not null group by source")
        assert {r["source"]: r["n"] for r in cur.fetchall()} == {"essaycards_flashcards": 1, "essaycards_oral": 1}
