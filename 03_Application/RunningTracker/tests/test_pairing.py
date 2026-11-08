"""Pairing, lockout, revoke and token-scoping scenarios (10_test_spec.md)."""

import os

from tests.conftest import RUN_COMPLETE, TOKEN_1, auth

PAIR = "/api/runningtracker/native/pair"
CODES = "/api/runningtracker/pairing-codes"
NATIVE_PREPARED = "/api/runningtracker/native/prepared-runs"


def _pair(client, code, name="Pixel"):
    return client.post(PAIR, json={"code": code, "device_name": name})


def test_pairing_creates_a_device_token_once(client, db_conn):
    r = client.post(CODES)
    assert r.status_code == 201
    body = r.json()
    assert body["meta"]["total"] == 1 and body["meta"]["object_type"] == "pairing_code"
    row = body["rows"][0]
    code = row["code"]
    assert len(code) == 8
    assert row["native_base_url"] == (os.environ.get("RUNNINGTRACKER_NATIVE_BASE_URL") or None)
    from datetime import datetime, timezone
    expires = datetime.fromisoformat(row["expires_at"])
    assert 200 < (expires - datetime.now(timezone.utc)).total_seconds() <= 300

    paired = _pair(client, code)
    assert paired.status_code == 200
    token = paired.json()["device_token"]
    assert paired.json()["device_id"] and len(token) >= 40

    assert _pair(client, code).status_code == 403  # single use

    # only hashes are stored: neither the token nor the code appear in any column
    with db_conn.cursor() as cur:
        cur.execute("select * from runningtracker.devices")
        assert token not in str(cur.fetchall())
        cur.execute("select * from runningtracker.pairing_codes")
        assert code not in str(cur.fetchall())

    # the new token works on a native endpoint
    assert client.get(NATIVE_PREPARED, headers=auth(token)).status_code == 200


def test_pairing_code_cannot_be_reused(client):
    used = _pair(client, "FIXUSED2")
    unknown = _pair(client, "ZZZZZZZZ")
    assert used.status_code == 403
    assert used.json()["error"]["code"] == "PAIRING_FAILED"
    assert used.json()["error"]["message"] == unknown.json()["error"]["message"]


def test_expired_pairing_code_is_refused(client):
    expired = _pair(client, "FIXEXPD2")
    unknown = _pair(client, "ZZZZZZZZ")
    assert expired.status_code == 403
    assert expired.json()["error"]["code"] == "PAIRING_FAILED"
    assert set(expired.json()["error"]) == set(unknown.json()["error"])
    assert expired.json()["error"]["message"] == unknown.json()["error"]["message"]


def test_pairing_lockout_after_five_wrong_attempts(client, db_conn):
    for i in range(5):
        assert _pair(client, f"WRONG{i}XX").status_code == 403
    locked = _pair(client, "FIXACTV2")
    assert locked.status_code == 429
    assert locked.json()["error"]["code"] == "PAIRING_RATE_LIMITED"

    # the window passes: the code that was active at lockout time stays locked
    with db_conn.cursor() as cur:
        cur.execute("update runningtracker.pairing_failures set failed_at = now() - interval '10 minutes'")
    after = _pair(client, "FIXACTV2")
    assert after.status_code == 403

    # a freshly created code redeems normally
    code = client.post(CODES).json()["rows"][0]["code"]
    assert _pair(client, code).status_code == 200


def test_revoked_token_is_rejected(client):
    code = client.post(CODES).json()["rows"][0]["code"]
    paired = _pair(client, code).json()
    headers = auth(paired["device_token"])
    assert client.get(NATIVE_PREPARED, headers=headers).status_code == 200

    first = client.post(f"/api/runningtracker/devices/{paired['device_id']}/revoke")
    assert first.status_code == 200
    revoked_at = first.json()["rows"][0]["revoked_at"]
    assert revoked_at is not None

    denied = client.get(NATIVE_PREPARED, headers=headers)
    assert denied.status_code == 401
    assert denied.json()["error"]["code"] == "DEVICE_UNAUTHORIZED"

    second = client.post(f"/api/runningtracker/devices/{paired['device_id']}/revoke")
    assert second.status_code == 200
    assert second.json()["rows"][0]["revoked_at"] == revoked_at

    devices = client.get("/api/runningtracker/devices").json()["rows"]
    assert next(d for d in devices if d["id"] == paired["device_id"])["is_revoked"] is True


def test_native_endpoints_require_a_device_token(client):
    base = "/api/runningtracker/native"
    calls = [
        ("get", f"{base}/prepared-runs", None),
        ("get", f"{base}/prepared-runs/e1000000-0000-0000-0000-0000000000f1", None),
        ("post", f"{base}/runs/c1000000-0000-0000-0000-000000000001/begin", {"started_at": "2026-01-01T00:00:00Z"}),
        ("put", f"{base}/runs/c1000000-0000-0000-0000-000000000001/samples", {"samples": []}),
        ("post", f"{base}/runs/c1000000-0000-0000-0000-000000000001/finish", {}),
    ]
    for headers in ({}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer"}, {"Authorization": "Bearer unknown-token"}):
        for method, path, body in calls:
            r = client.request(method, path, json=body, headers=headers)
            assert r.status_code == 401, (method, path, headers)
            assert r.json()["error"]["code"] == "DEVICE_UNAUTHORIZED"


def test_device_token_has_no_extra_power_on_web_endpoints(client):
    without = client.get("/api/runningtracker/runs")
    with_token = client.get("/api/runningtracker/runs", headers=auth(TOKEN_1))
    assert without.status_code == with_token.status_code == 200
    assert without.json() == with_token.json()


def test_native_route_rejected_when_it_arrives_through_the_public_path(client):
    r = client.get(NATIVE_PREPARED, headers={**auth(TOKEN_1), "CF-Connecting-IP": "203.0.113.9"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "NATIVE_ROUTE_FORBIDDEN"
    r = client.post(PAIR, json={"code": "FIXACTV2", "device_name": "x"}, headers={"CF-Connecting-IP": "203.0.113.9"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "NATIVE_ROUTE_FORBIDDEN"


def test_oversized_body_is_refused_with_413(client):
    big = {"samples": [{"stream": "location", "seq": 1, "payload": {"timestamp": "2026-01-01T00:00:00Z", "pad": "x" * 2_100_000}}]}
    r = client.put(f"/api/runningtracker/native/runs/{RUN_COMPLETE}/samples", json=big, headers=auth(TOKEN_1))
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_pairing_pair_endpoint_validates_the_body(client):
    assert client.post(PAIR, json={"code": "FIXACTV2"}).status_code == 422
    assert client.post(PAIR, json={"code": "FIXACTV2", "device_name": ""}).status_code == 422
    assert client.post(PAIR, json={"code": "FIXACTV2", "device_name": "x", "extra": 1}).status_code == 422
