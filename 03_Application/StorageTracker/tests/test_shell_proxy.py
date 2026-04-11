"""
Shell proxy smoke tests for StorageTracker.

Verifies that the Atlas Shell nginx proxy correctly routes StorageTracker API
paths to the backend. These tests run inside the test container (atlas-net)
and make real HTTP requests to atlas-shell.

Catches: missing nginx location block, wrong container name in proxy_pass,
missing COPY in the shell Dockerfile, missing import in shell main.tsx.

These tests do NOT use the TestClient fixture — they require the full stack.
"""

import httpx
import pytest

SHELL = "http://atlas-shell"


def test_items_proxy_returns_json():
    """GET /api/items must be proxied to the backend, not served as HTML."""
    r = httpx.get(f"{SHELL}/api/items", timeout=5)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    ct = r.headers.get("content-type", "")
    assert "application/json" in ct, (
        f"Expected JSON content-type, got '{ct}' — "
        "nginx likely missing /api/items location block or serving SPA fallback"
    )


def test_shopping_tasks_proxy_returns_json():
    """GET /api/shopping-tasks must be proxied to the backend, not served as HTML."""
    r = httpx.get(f"{SHELL}/api/shopping-tasks", timeout=5)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    ct = r.headers.get("content-type", "")
    assert "application/json" in ct, (
        f"Expected JSON content-type, got '{ct}' — "
        "nginx likely missing /api/shopping-tasks location block or serving SPA fallback"
    )


def test_shell_serves_app_at_basepath():
    """GET /items must return the shell HTML (app is registered in main.tsx)."""
    r = httpx.get(f"{SHELL}/items", timeout=5)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    ct = r.headers.get("content-type", "")
    assert "text/html" in ct, f"Expected HTML, got '{ct}'"
    assert "<script" in r.text, (
        "Shell HTML has no script tag — app bundle may not have been built correctly"
    )
