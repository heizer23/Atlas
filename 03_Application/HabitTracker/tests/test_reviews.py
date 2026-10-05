"""
Tests for GET/PUT /reviews/{date}.

Scenario -> test function mapping (10_test_spec.md). A few sequential
scenarios that build on each other's preconditions (same date, same
confirmed row) are combined into one test function, noted below.

  Daily review — unreviewed day uses current defaults
    -> test_unreviewed_day_uses_current_defaults
  Daily review — draft save preserves edited values and merges new habits
  Daily review — editing a habit's default does not change an existing draft
    -> test_draft_preserves_edited_values_and_merges_newly_active_habit
  Daily review — confirming a day stamps confirmed_at and counts it
  Daily review — confirmed day display is frozen against later habit edits
  Daily review — PUT is idempotent
    -> test_confirm_freezes_display_and_is_idempotent
  Daily review — PUT rejects a habit_results set that omits an expected habit
  Daily review — PUT rejects a habit_results set that adds an unexpected habit
    -> test_put_rejects_mismatched_habit_sets
  Daily review — re-confirming accepts exactly the previously saved set even
  after the active window changes
    -> test_reconfirm_accepts_frozen_set_after_active_window_changes
  Daily review — editing an already-confirmed day downgrades it to draft
    -> test_editing_confirmed_day_downgrades_to_draft
  Daily review — malformed date is rejected
    -> test_malformed_date_is_rejected
"""

BASE = "/api/habittracker"

WORKED_OUT_ID = "10000001-0000-0000-0000-000000000001"
NO_SWEETS_ID  = "10000002-0000-0000-0000-000000000002"
NO_VAPING_ID  = "10000003-0000-0000-0000-000000000003"
BP_ID         = "10000004-0000-0000-0000-000000000004"
ESSAYCARDS_ID = "10000005-0000-0000-0000-000000000005"
ARCHIVED_ID   = "10000006-0000-0000-0000-000000000006"

STARTER_IDS = [WORKED_OUT_ID, NO_SWEETS_ID, NO_VAPING_ID, BP_ID, ESSAYCARDS_ID]


def _get_review(client, date):
    r = client.get(f"{BASE}/reviews/{date}")
    assert r.status_code == 200
    return r.json()["rows"][0]


def _full_set_results(habits, checked_by_id=None, default_checked=False):
    checked_by_id = checked_by_id or {}
    return [
        {"habit_id": h["habit_id"], "checked": checked_by_id.get(h["habit_id"], default_checked)}
        for h in habits
    ]


# ── Unreviewed defaults ───────────────────────────────────────────────────────

def test_unreviewed_day_uses_current_defaults(client):
    row = _get_review(client, "2026-10-05")
    assert row["status"] == "unreviewed"
    worked_out = next(h for h in row["habits"] if h["habit_id"] == WORKED_OUT_ID)
    assert worked_out["checked"] is False


# ── Draft merge + default-change-after-draft ─────────────────────────────────

def test_draft_preserves_edited_values_and_merges_newly_active_habit(client):
    date = "2026-10-06"
    row = _get_review(client, date)
    assert row["status"] == "unreviewed"
    results = _full_set_results(row["habits"], checked_by_id={WORKED_OUT_ID: True})

    r = client.put(f"{BASE}/reviews/{date}", json={"status": "draft", "habit_results": results})
    assert r.status_code == 200
    assert r.json()["rows"][0]["status"] == "draft"

    # A habit created AFTER this draft was first saved never had a chance to
    # be part of that save — it has no saved row yet on this date, so a
    # fresh GET picks up its current default_checked (false).
    new_habit = client.post(f"{BASE}/habits", json={
        "name": "Stretch", "default_checked": False, "active_from": "2026-01-01",
    }).json()

    row2 = _get_review(client, date)
    assert row2["status"] == "draft"
    worked_out = next(h for h in row2["habits"] if h["habit_id"] == WORKED_OUT_ID)
    new_entry = next(h for h in row2["habits"] if h["habit_id"] == new_habit["id"])
    assert worked_out["checked"] is True  # saved draft value, not re-derived
    assert new_entry["checked"] is False  # current default, no saved row yet

    # Editing the new habit's default does not change the existing draft
    # value for worked-out, and the new habit (still no saved row on this
    # date) now picks up its UPDATED default.
    client.patch(f"{BASE}/habits/{new_habit['id']}", json={"default_checked": True})

    row3 = _get_review(client, date)
    worked_out3 = next(h for h in row3["habits"] if h["habit_id"] == WORKED_OUT_ID)
    new_entry3 = next(h for h in row3["habits"] if h["habit_id"] == new_habit["id"])
    assert worked_out3["checked"] is True
    assert new_entry3["checked"] is True


# ── Confirm / frozen display / idempotency ───────────────────────────────────

def test_confirm_freezes_display_and_is_idempotent(client, db_conn):
    date = "2026-10-07"
    row = _get_review(client, date)
    assert row["status"] == "unreviewed"
    results = _full_set_results(row["habits"], checked_by_id={WORKED_OUT_ID: True})

    r = client.put(f"{BASE}/reviews/{date}", json={"status": "confirmed", "habit_results": results})
    assert r.status_code == 200
    confirmed = r.json()["rows"][0]
    assert confirmed["status"] == "confirmed"
    assert confirmed["confirmed_at"] is not None
    first_confirmed_at = confirmed["confirmed_at"]

    row2 = _get_review(client, date)
    assert row2["status"] == "confirmed"
    assert {h["habit_id"]: h["checked"] for h in row2["habits"]} == \
           {h["habit_id"]: h["checked"] for h in confirmed["habits"]}

    # Archive worked-out (end_date before this date) — the confirmed display
    # must stay frozen and unaffected.
    client.patch(f"{BASE}/habits/{WORKED_OUT_ID}", json={"end_date": "2026-10-01"})

    row3 = _get_review(client, date)
    assert row3["status"] == "confirmed"
    worked_out3 = next(h for h in row3["habits"] if h["habit_id"] == WORKED_OUT_ID)
    assert worked_out3["checked"] is True

    # Repeat the identical confirmed PUT — idempotent: no duplicate rows,
    # same content, confirmed_at reflects the most recent call.
    r2 = client.put(f"{BASE}/reviews/{date}", json={"status": "confirmed", "habit_results": results})
    assert r2.status_code == 200
    second_confirmed = r2.json()["rows"][0]
    assert {h["habit_id"]: h["checked"] for h in second_confirmed["habits"]} == \
           {h["habit_id"]: h["checked"] for h in confirmed["habits"]}
    assert second_confirmed["confirmed_at"] is not None

    with db_conn.cursor() as cur:
        cur.execute("select count(*) as n from habittracker.habit_results where review_date = %s", (date,))
        assert cur.fetchone()["n"] == len(STARTER_IDS)


# ── PUT expected-set rejection ────────────────────────────────────────────────

def test_put_rejects_mismatched_habit_sets(client, db_conn):
    date = "2026-10-08"
    row = _get_review(client, date)
    assert len(row["habits"]) == len(STARTER_IDS)

    # Omits one expected habit.
    short_results = _full_set_results(row["habits"][:-1])
    r = client.put(f"{BASE}/reviews/{date}", json={"status": "draft", "habit_results": short_results})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"

    # Adds an unexpected habit (the archived fixture, not in the active set).
    extra_results = _full_set_results(row["habits"]) + [{"habit_id": ARCHIVED_ID, "checked": True}]
    r2 = client.put(f"{BASE}/reviews/{date}", json={"status": "draft", "habit_results": extra_results})
    assert r2.status_code == 400
    assert r2.json()["error"]["code"] == "VALIDATION_ERROR"

    with db_conn.cursor() as cur:
        cur.execute("select count(*) as n from habittracker.daily_reviews where review_date = %s", (date,))
        assert cur.fetchone()["n"] == 0


# ── Re-confirm against the frozen set after the active window changes ───────

def test_reconfirm_accepts_frozen_set_after_active_window_changes(client):
    # On 2025-03-15, only the archived fixture habit is active (the starters'
    # active_from is 2026-01-01); confirm with exactly that set.
    date = "2025-03-15"
    row = _get_review(client, date)
    assert [h["habit_id"] for h in row["habits"]] == [ARCHIVED_ID]

    r = client.put(f"{BASE}/reviews/{date}", json={
        "status": "confirmed",
        "habit_results": [{"habit_id": ARCHIVED_ID, "checked": True}],
    })
    assert r.status_code == 200

    # Edit the archived habit's active window so it no longer covers this date.
    client.patch(f"{BASE}/habits/{ARCHIVED_ID}", json={"active_from": "2025-04-01"})

    # Re-confirming with the same previously-saved set still succeeds — the
    # frozen set, not the current active window, is validated against.
    r2 = client.put(f"{BASE}/reviews/{date}", json={
        "status": "confirmed",
        "habit_results": [{"habit_id": ARCHIVED_ID, "checked": True}],
    })
    assert r2.status_code == 200
    assert r2.json()["rows"][0]["status"] == "confirmed"


# ── Editing a confirmed day downgrades it to draft ───────────────────────────

def test_editing_confirmed_day_downgrades_to_draft(client):
    date = "2026-10-12"
    row = _get_review(client, date)
    results = _full_set_results(row["habits"], checked_by_id={WORKED_OUT_ID: True})
    confirmed = client.put(f"{BASE}/reviews/{date}", json={"status": "confirmed", "habit_results": results}).json()["rows"][0]
    confirmed_at_before = confirmed["confirmed_at"]
    assert confirmed_at_before is not None

    flipped = [
        {"habit_id": h["habit_id"], "checked": (not h["checked"]) if h["habit_id"] == WORKED_OUT_ID else h["checked"]}
        for h in confirmed["habits"]
    ]
    r = client.put(f"{BASE}/reviews/{date}", json={"status": "draft", "habit_results": flipped})
    assert r.status_code == 200
    draft = r.json()["rows"][0]
    assert draft["status"] == "draft"
    assert draft["confirmed_at"] == confirmed_at_before


# ── Malformed date ────────────────────────────────────────────────────────────

def test_malformed_date_is_rejected(client):
    r = client.get(f"{BASE}/reviews/not-a-date")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
