"""
Shell proxy smoke tests for StoryReader.

Verifies that the Atlas Shell nginx proxy correctly routes StoryReader API
paths to the backend, and that the app is registered and served at its
basePath. These tests run inside the test container (atlas-net) and make
real HTTP requests to atlas-shell.

Catches: missing nginx location block, wrong container name in proxy_pass,
missing COPY in the shell Dockerfile, missing import in shell main.tsx.

These tests do NOT use the TestClient fixture — they require the full stack.
"""

import httpx

SHELL = "http://atlas-shell"


def test_storyreader_proxy_returns_json():
    """GET /api/storyreader/stories must be proxied to the backend, not served as HTML."""
    r = httpx.get(f"{SHELL}/api/storyreader/stories", timeout=5)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    ct = r.headers.get("content-type", "")
    assert "application/json" in ct, (
        f"Expected JSON content-type, got '{ct}' — "
        "nginx likely missing /api/storyreader location block or serving SPA fallback"
    )


def test_shell_serves_app_at_basepath():
    """GET /storyreader must return the shell HTML (app is registered in main.tsx)."""
    r = httpx.get(f"{SHELL}/storyreader", timeout=5)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    ct = r.headers.get("content-type", "")
    assert "text/html" in ct, f"Expected HTML, got '{ct}'"
    assert "<script" in r.text, (
        "Shell HTML has no script tag — app bundle may not have been built correctly"
    )
