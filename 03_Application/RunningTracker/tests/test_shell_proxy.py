"""
Shell proxy checks for RunningTracker (full stack: runs against http://atlas-shell from the test container).

Catches: missing nginx location block, wrong container name, missing deny block for the native prefix (E1),
missing main.tsx import. These tests do not use the TestClient.
"""

import httpx

SHELL = "http://atlas-shell"


def test_runs_proxy_returns_json():
    r = httpx.get(f"{SHELL}/api/runningtracker/runs", timeout=5)
    assert r.status_code == 200
    assert "application/json" in r.headers.get("content-type", "")
    assert "rows" in r.json()


def test_native_routes_are_not_reachable_through_the_public_proxy():
    paths = [
        "/api/runningtracker/native/prepared-runs",
        "/api/runningtracker/native/pair",
        "/api/runningtracker/native/runs/b1000000-0000-0000-0000-000000000009/begin",
        "/api/runningtracker//native/prepared-runs",       # doubled slash
        "/api/runningtracker/native",
        "/api/runningtracker/native/",
    ]
    for path in paths:
        for method in ("GET", "POST", "PUT"):
            r = httpx.request(method, f"{SHELL}{path}", json={} if method != "GET" else None, timeout=5)
            assert r.status_code == 404, (method, path, r.status_code)
            assert "error" not in r.text.lower() or "not found" in r.text.lower()  # nginx 404, not a backend ApiError


def test_shell_serves_app_at_basepath():
    r = httpx.get(f"{SHELL}/running", timeout=5)
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert "<script" in r.text
