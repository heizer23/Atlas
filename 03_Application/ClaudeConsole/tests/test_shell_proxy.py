"""
Shell proxy smoke tests for ClaudeConsole.

Verifies that the Atlas Shell nginx proxy correctly routes ClaudeConsole API
paths to the backend. These tests run inside the test container (atlas-net)
and make real HTTP requests to atlas-shell.

Catches: missing nginx location block, wrong container name in proxy_pass,
missing import in shell main.tsx.

These tests do NOT use the TestClient fixture — they require the full stack.

NOTE: the WS path (/api/claudeconsole/ws) cannot be exercised with plain
httpx (no upgrade support) and is NOT covered by this suite. Its nginx
upgrade-header proxying and the Vite dev-proxy `ws: true` entry are verified
manually per the Sprint 1 plan's Verification section (steps 4-5) — a broken
upgrade-header setup fails as a silent "connection closes immediately" and
is easy to misattribute to the backend, which is exactly why it needs a
direct manual check rather than being assumed covered here.
"""

import httpx

SHELL = "http://atlas-shell"


def test_session_proxy_returns_json():
    """GET /api/claudeconsole/session must be proxied to the backend, not served as HTML."""
    r = httpx.get(f"{SHELL}/api/claudeconsole/session", timeout=5)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    ct = r.headers.get("content-type", "")
    assert "application/json" in ct, (
        f"Expected JSON content-type, got '{ct}' — "
        "nginx likely missing /api/claudeconsole location block or serving SPA fallback"
    )


def test_shell_serves_app_at_basepath():
    """GET /console must return the shell HTML (app is registered in main.tsx)."""
    r = httpx.get(f"{SHELL}/console", timeout=5)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    ct = r.headers.get("content-type", "")
    assert "text/html" in ct, f"Expected HTML, got '{ct}'"
    assert "<script" in r.text, (
        "Shell HTML has no script tag — app bundle may not have been built correctly"
    )
