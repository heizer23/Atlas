"""Web list/detail/splits/series/PATCH/DELETE/prepared/devices/pairing-code scenarios (Dataset | ApiError)."""

from tests.conftest import PREPARED_EXPIRED, PREPARED_FRESH, RUN_COMPLETE, RUN_GAP, RUN_REVOKED_COMPLETE, RUN_REVOKED_UPLOADING

W = "/api/runningtracker"


def _rows(r):
    assert r.status_code == 200, r.text
    return r.json()["rows"]


def test_history_list_is_a_dataset_with_defined_ordering_and_defaults(client):
    r = client.get(f"{W}/runs")
    body = r.json()
    assert r.status_code == 200
    assert set(body) == {"meta", "schema", "rows"}
    assert body["meta"]["object_type"] == "run" and body["meta"]["row_actions"] == ["delete"]
    ids = [row["id"] for row in body["rows"]]
    # default: uploading + complete, newest started_at first, prepared excluded
    assert ids == [RUN_GAP, RUN_COMPLETE, RUN_REVOKED_UPLOADING, RUN_REVOKED_COMPLETE]
    assert body["meta"]["total"] == 4
    by_id = {row["id"]: row for row in body["rows"]}
    assert by_id[RUN_GAP]["sync_state"] == "pending" and by_id[RUN_COMPLETE]["sync_state"] == "synced"
    complete = by_id[RUN_COMPLETE]
    assert abs(complete["avg_pace_s_per_km"] - 270.0) < 1e-9  # 540 s / 2 km
    assert complete["avg_hr"] == 160 and complete["location_count"] == 20 and complete["hr_count"] == 20
    assert complete["device_name"] == "fix-device-1"

    prepared = _rows(client.get(f"{W}/runs", params={"status": "prepared"}))
    assert {row["id"] for row in prepared} == {PREPARED_FRESH, PREPARED_EXPIRED}
    assert all(row["sync_state"] == "prepared" for row in prepared)

    page2 = client.get(f"{W}/runs", params={"page_size": 1, "page": 2}).json()
    assert [row["id"] for row in page2["rows"]] == [RUN_COMPLETE]
    assert page2["meta"]["total"] == 4 and page2["meta"]["page"] == 2 and page2["meta"]["page_size"] == 1

    for bad in ({"page_size": 101}, {"status": "bogus"}, {"page": 0}):
        e = client.get(f"{W}/runs", params=bad)
        assert e.status_code == 422 and e.json()["error"]["code"] == "VALIDATION_ERROR"


def test_empty_history_is_an_empty_dataset(client, db_conn):
    with db_conn.cursor() as cur:
        cur.execute("truncate runningtracker.runs cascade")
    body = client.get(f"{W}/runs").json()
    assert body["rows"] == [] and body["meta"]["total"] == 0 and body["schema"]


def test_run_detail_splits_and_series(client):
    detail = client.get(f"{W}/runs/{RUN_COMPLETE}")
    assert detail.status_code == 200
    rows = detail.json()["rows"]
    assert len(rows) == 1 and rows[0]["id"] == RUN_COMPLETE and rows[0]["comment"] == "tempo"
    assert abs(rows[0]["avg_pace_s_per_km"] - 270.0) < 1e-9

    splits = _rows(client.get(f"{W}/runs/{RUN_COMPLETE}/splits"))
    assert [s["km"] for s in splits] == [1, 2]  # ordered by km although stored the other way round
    assert splits[0]["pace_s_per_km"] == 260 and splits[0]["partial"] is False

    for metric in ("pace", "heart_rate"):
        series = _rows(client.get(f"{W}/runs/{RUN_COMPLETE}/series", params={"metric": metric}))
        assert [p["t_s"] for p in series] == [5, 10, 15]
        assert all(isinstance(p["t_s"], (int, float)) and isinstance(p["value"], (int, float)) for p in series)
        assert series == sorted(series, key=lambda p: p["t_label"])  # label sorts like time (LineChart sorts x as text)
    assert client.get(f"{W}/runs/{RUN_COMPLETE}/series").status_code == 422
    assert client.get(f"{W}/runs/{RUN_COMPLETE}/series", params={"metric": "cadence"}).status_code == 422

    # a run that is still uploading has no metrics yet: empty datasets, not errors
    assert _rows(client.get(f"{W}/runs/{RUN_GAP}/splits")) == []
    assert _rows(client.get(f"{W}/runs/{RUN_GAP}/series", params={"metric": "pace"})) == []

    for path in ("", "/splits", "/series?metric=pace"):
        missing = client.get(f"{W}/runs/b1000000-0000-0000-0000-000000000009{path}")
        assert missing.status_code == 404 and missing.json()["error"]["code"] == "NOT_FOUND"
    assert client.get(f"{W}/runs/not-a-uuid").status_code == 404


def test_comment_patch_distinguishes_omit_value_and_null(client):
    url = f"{W}/runs/{RUN_COMPLETE}"

    def comment(r):
        assert r.status_code == 200, r.text
        return r.json()["rows"][0]["comment"]

    assert comment(client.patch(url, json={})) == "tempo"
    assert comment(client.patch(url, json={"comment": "easy"})) == "easy"
    assert comment(client.patch(url, json={"comment": "  trimmed  "})) == "trimmed"
    assert comment(client.patch(url, json={"comment": None})) is None
    client.patch(url, json={"comment": "again"})
    assert comment(client.patch(url, json={"comment": "   "})) is None
    assert client.patch(url, json={"other": 1}).status_code == 422
    assert client.patch(f"{W}/runs/b1000000-0000-0000-0000-000000000009", json={"comment": "x"}).status_code == 404


def test_delete_run_removes_all_derived_data(client, db_conn):
    r = client.delete(f"{W}/runs/{RUN_COMPLETE}")
    assert r.status_code == 200 and r.json()["rows"] == [] and r.json()["meta"]["total"] == 0
    with db_conn.cursor() as cur:
        for table in ("run_samples", "run_pauses", "run_metrics"):
            cur.execute(f"select count(*) as n from runningtracker.{table} where run_id = %s", (RUN_COMPLETE,))
            assert cur.fetchone()["n"] == 0, table
    assert client.delete(f"{W}/runs/{RUN_COMPLETE}").status_code == 404


def test_devices_list_and_pairing_do_not_expose_secrets(client):
    devices = client.get(f"{W}/devices").json()
    names = {row["name"]: row for row in devices["rows"]}
    assert set(names) == {"fix-device-1", "fix-device-2", "fix-device-3"}
    assert names["fix-device-2"]["is_revoked"] is True and names["fix-device-1"]["is_revoked"] is False
    assert devices["meta"]["row_actions"] == ["revoke"]
    prepared = client.get(f"{W}/prepared-runs")
    for text in (str(devices), str(prepared.json())):
        assert "token" not in text.lower() and "hash" not in text.lower()
    assert [r["id"] for r in prepared.json()["rows"]] == [PREPARED_FRESH, PREPARED_EXPIRED]  # newest first
    assert client.post(f"{W}/devices/b1000000-0000-0000-0000-000000000009/revoke").status_code == 404


def test_logs_contain_no_tokens_codes_or_samples(client, caplog):
    import logging
    caplog.set_level(logging.DEBUG)
    code = client.post(f"{W}/pairing-codes").json()["rows"][0]["code"]
    paired = client.post(f"{W}/native/pair", json={"code": code, "device_name": "Pixel"}).json()
    client.put(f"{W}/native/runs/b1000000-0000-0000-0000-0000000000aa/samples",
               json={"samples": [{"stream": "location", "seq": 1, "payload": {"timestamp": "2026-01-01T00:00:00Z", "latitude": 52.123456}}]},
               headers={"Authorization": f"Bearer {paired['device_token']}"})
    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert paired["device_token"] not in logged and code not in logged and "52.123456" not in logged


def test_schema_is_idempotent(client, db_conn):
    import backend.database as db_module
    before = {}
    with db_conn.cursor() as cur:
        for table in ("runs", "devices", "run_samples", "pairing_codes"):
            cur.execute(f"select count(*) as n from runningtracker.{table}")
            before[table] = cur.fetchone()["n"]
    db_module.init_schema()
    db_module.init_schema()
    with db_conn.cursor() as cur:
        for table, n in before.items():
            cur.execute(f"select count(*) as n from runningtracker.{table}")
            assert cur.fetchone()["n"] == n
