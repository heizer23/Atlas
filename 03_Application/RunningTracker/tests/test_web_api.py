"""Web list/detail/splits/series/PATCH/DELETE/prepared/devices/pairing-code scenarios (Dataset | ApiError)."""

import pytest

from tests.conftest import (
    PREPARED_EXPIRED, PREPARED_FRESH, RUN_CADENCE, RUN_CADENCE_EMPTY, RUN_CADENCE_UPLOAD, RUN_COACH_1, RUN_COACH_2, RUN_COACH_3, RUN_COACH_4, RUN_COMPLETE, RUN_GAP, RUN_RECOVERY, RUN_RECOVERY_NOHR, RUN_RECOVERY_UPLOAD,
    RUN_REVOKED_COMPLETE, RUN_REVOKED_UPLOADING,
)

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
    assert ids == [RUN_COACH_1, RUN_COACH_2, RUN_COACH_3, RUN_COACH_4, RUN_CADENCE_EMPTY, RUN_CADENCE_UPLOAD, RUN_CADENCE, RUN_RECOVERY_UPLOAD, RUN_RECOVERY_NOHR, RUN_RECOVERY, RUN_GAP, RUN_COMPLETE, RUN_REVOKED_UPLOADING, RUN_REVOKED_COMPLETE]
    assert body["meta"]["total"] == 14
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
    assert [row["id"] for row in page2["rows"]] == [RUN_COACH_2]
    assert page2["meta"]["total"] == 14 and page2["meta"]["page"] == 2 and page2["meta"]["page_size"] == 1

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
    assert client.get(f"{W}/runs/{RUN_COMPLETE}/series", params={"metric": "speed"}).status_code == 422

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


# ── Sprint02: recovery ───────────────────────────────────────────────────────

def test_recovery_dataset_for_a_run_with_recovery(client):
    r = client.get(f"{W}/runs/{RUN_RECOVERY}/recovery")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"meta", "schema", "rows"}
    assert body["meta"]["object_type"] == "run_recovery" and body["meta"]["total"] == 1
    assert {c["key"] for c in body["schema"]} >= {"run_finished_at", "recovery_s", "hr_end", "hr_60", "hr_120", "hrr60", "hrr120"}
    row = body["rows"][0]
    assert row["id"] == RUN_RECOVERY and row["recovery_s"] == 300
    assert row["run_finished_at"].startswith("2026-01-12T08:10:00")
    assert (row["hr_end"], row["hr_60"], row["hr_120"], row["hrr60"], row["hrr120"]) == (150, 138, 126, 12, 24)


def test_recovery_dataset_is_empty_for_legacy_and_uploading_runs_and_404_for_unknown(client):
    for run_id in (RUN_COMPLETE, RUN_RECOVERY_UPLOAD):
        r = client.get(f"{W}/runs/{run_id}/recovery")
        assert r.status_code == 200 and r.json()["rows"] == [] and r.json()["meta"]["total"] == 0
    missing = client.get(f"{W}/runs/b1000000-0000-0000-0000-000000000009/recovery")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "NOT_FOUND"
    assert client.get(f"{W}/runs/not-a-uuid/recovery").status_code == 404


def test_recovery_trend_lists_only_runs_with_recovery(client):
    r = client.get(f"{W}/runs/recovery-trend")
    assert r.status_code == 200
    body = r.json()
    assert body["meta"]["object_type"] == "run_recovery_trend"
    assert [row["id"] for row in body["rows"]] == [RUN_RECOVERY]
    row = body["rows"][0]
    assert (row["hr_end"], row["hrr60"], row["hrr120"]) == (150, 12, 24)
    assert len(row["when"]) == 16 and row["when"].startswith("2026-01-12")


def test_efficiency_trend_is_speed_over_avg_hr_for_runs_with_hr(client):
    body = client.get(f"{W}/runs/efficiency-trend").json()
    assert body["meta"]["object_type"] == "run_efficiency_trend"
    row = next(r for r in body["rows"] if r["id"] == RUN_COMPLETE)
    assert row["avg_hr"] == 160 and row["pace_s_per_km"] > 0
    assert abs(row["efficiency"] - (60000 / row["pace_s_per_km"]) / 160) < 1e-2
    assert RUN_RECOVERY_NOHR not in [r["id"] for r in body["rows"]]


def test_run_without_heart_rate_has_a_null_recovery_row_and_an_empty_series(client):
    row = _rows(client.get(f"{W}/runs/{RUN_RECOVERY_NOHR}/recovery"))[0]
    assert row["recovery_s"] == 180
    assert all(row[k] is None for k in ("hr_end", "hr_60", "hr_120", "hrr60", "hrr120"))
    series = client.get(f"{W}/runs/{RUN_RECOVERY_NOHR}/series", params={"metric": "recovery_hr"})
    assert series.status_code == 200 and series.json()["rows"] == [] and series.json()["meta"]["total"] == 0


def test_recovery_series_covers_the_recovery_phase_without_zero_filling(client):
    series = client.get(f"{W}/runs/{RUN_RECOVERY}/series", params={"metric": "recovery_hr"})
    assert series.status_code == 200 and series.json()["meta"]["label"] == "Recovery heart rate"
    rows = series.json()["rows"]
    ts = [p["t_s"] for p in rows]
    assert ts[0] == 0 and ts[-1] == 300 and ts == sorted(ts)
    assert all(t % 5 == 0 for t in ts)
    assert not {135, 140, 145} & set(ts)  # the 20 s heart-rate gap: absent, not zero, not interpolated
    assert all(p["value"] > 0 for p in rows)
    assert rows == sorted(rows, key=lambda p: p["t_label"])


def test_series_metric_validation(client):
    for metric in ("recovery_hr", "heart_rate", "pace"):
        assert client.get(f"{W}/runs/{RUN_RECOVERY}/series", params={"metric": metric}).status_code == 200
    for params in ({"metric": "speed"}, {}):
        r = client.get(f"{W}/runs/{RUN_RECOVERY}/series", params=params)
        assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_history_averages_exclude_recovery(client):
    rows = {r["id"]: r for r in _rows(client.get(f"{W}/runs"))}
    rec = rows[RUN_RECOVERY]
    assert abs(rec["avg_hr"] - 150.0833333) < 1e-6 and rec["max_hr"] == 200  # stored running-phase values, not all-session
    assert rec["distance_m"] == 2396 and rec["moving_s"] == 600
    assert rows[RUN_COMPLETE]["avg_hr"] == 160 and rows[RUN_COMPLETE]["distance_m"] == 2000  # unchanged from Sprint01
    detail = _rows(client.get(f"{W}/runs/{RUN_RECOVERY}"))[0]
    assert detail["avg_hr"] == rec["avg_hr"] and detail["max_hr"] == 200


def test_recomputing_a_recovery_run_gives_the_golden_hrr_values(client, db_conn):
    from backend.database import get_db, init_pool
    import backend.database as db_module
    from backend.metrics import recompute_and_store
    if db_module._pool is None:
        init_pool()
    with get_db() as conn:
        recompute_and_store(conn, RUN_RECOVERY)
        conn.commit()
    with db_conn.cursor() as cur:
        cur.execute("select avg_hr, max_hr, hr_series, recovery from runningtracker.run_metrics where run_id = %s", (RUN_RECOVERY,))
        m = cur.fetchone()
    rec = m["recovery"]
    assert (rec["hr_end"], rec["hr_60"], rec["hr_120"]) == (150, 138, 126)
    assert abs(rec["hrr60"] - 12) < 0.01 and abs(rec["hrr120"] - 24) < 0.01
    curve_t = [p[0] for p in rec["curve"]]
    assert curve_t[0] == 0 and curve_t[-1] == 300 and not {135, 140, 145} & set(curve_t)
    assert max(p[0] for p in m["hr_series"]) <= 600  # running-phase HR series stops at the run end
    assert m["max_hr"] == 200  # A1 'bpm >= 1' rule is unchanged: the spike still counts for running max


def test_deleting_a_recovery_run_removes_its_recovery_data(client, db_conn):
    assert client.delete(f"{W}/runs/{RUN_RECOVERY}").status_code == 200
    with db_conn.cursor() as cur:
        for table in ("run_samples", "run_metrics"):
            cur.execute(f"select count(*) as n from runningtracker.{table} where run_id = %s", (RUN_RECOVERY,))
            assert cur.fetchone()["n"] == 0, table
    assert client.get(f"{W}/runs/{RUN_RECOVERY}/recovery").status_code == 404


# ---- Sprint03 cadence ----

def test_average_cadence_in_run_row(client):
    rows = {r["id"]: r for r in _rows(client.get(f"{W}/runs"))}
    assert rows[RUN_CADENCE]["avg_cadence_spm"] == 170.0
    assert rows[RUN_CADENCE_EMPTY]["avg_cadence_spm"] is None and rows[RUN_COMPLETE]["avg_cadence_spm"] is None
    assert _rows(client.get(f"{W}/runs/{RUN_CADENCE}"))[0]["avg_cadence_spm"] == 170.0
    assert rows[RUN_COMPLETE]["avg_hr"] == 160 and rows[RUN_COMPLETE]["distance_m"] == 2000   # no other column changed


def test_cadence_series_dataset(client):
    r = client.get(f"{W}/runs/{RUN_CADENCE}/series", params={"metric": "cadence"})
    body = r.json()
    assert r.status_code == 200 and body["meta"]["object_type"] == "run_series" and body["meta"]["label"] == "Cadence"
    assert body["meta"]["total"] == 59 and [row["t_s"] for row in body["rows"]] == [5.0 * k for k in range(1, 60)]
    assert all(row["value"] == 170.0 for row in body["rows"]) and "conf" not in body["rows"][0]


def test_cadence_series_empty_and_error_cases(client):
    for rid in (RUN_CADENCE_EMPTY, RUN_COMPLETE, RUN_CADENCE_UPLOAD):
        r = client.get(f"{W}/runs/{rid}/series", params={"metric": "cadence"})
        assert r.status_code == 200 and r.json()["meta"]["total"] == 0 and r.json()["rows"] == []
    r = client.get(f"{W}/runs/00000000-0000-0000-0000-00000000dead/series", params={"metric": "cadence"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"
    assert client.get(f"{W}/runs/{RUN_CADENCE}/series", params={"metric": "speed"}).status_code == 422
    for metric in ("pace", "heart_rate", "recovery_hr"):
        assert client.get(f"{W}/runs/{RUN_RECOVERY}/series", params={"metric": metric}).status_code == 200


def test_deleting_a_cadence_run_removes_its_cadence_data(client, db_conn):
    assert client.delete(f"{W}/runs/{RUN_CADENCE}").status_code == 200
    with db_conn.cursor() as cur:
        for table in ("run_samples", "run_metrics", "run_route_progress"):
            cur.execute(f"select count(*) as n from runningtracker.{table} where run_id = %s", (RUN_CADENCE,))
            assert cur.fetchone()["n"] == 0, table
    assert client.get(f"{W}/runs/{RUN_CADENCE}/series", params={"metric": "cadence"}).status_code == 404


def test_schema_with_step_stream_is_idempotent_and_still_rejects_unknown_streams(db_conn):
    import os
    ddl = open(os.path.join(os.path.dirname(__file__), "../schema.sql")).read()
    with db_conn.cursor() as cur:
        cur.execute(ddl)
        cur.execute(ddl)
        cur.execute("select conname from pg_constraint where conname in ('ck_run_samples_stream', 'run_samples_stream_check')")
        assert [r["conname"] for r in cur.fetchall()] == ["ck_run_samples_stream"]
        cur.execute("select count(*) as n from runningtracker.run_samples where run_id = %s", (RUN_CADENCE,))
        assert cur.fetchone()["n"] == 1450
        import psycopg2
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute("insert into runningtracker.run_samples (run_id, stream, seq, sample_ts, payload) "
                        "values (%s, 'gyro', 99999, now(), '{}')", (RUN_CADENCE,))
