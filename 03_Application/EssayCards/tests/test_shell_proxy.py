"""
Shell proxy smoke tests for EssayCards.

Verifies that the Atlas Shell nginx proxy correctly routes EssayCards API
paths to the backend, and that the shell serves the EssayCards SPA at its
basePath. These tests run inside the test container (atlas-net) and make
real HTTP requests to atlas-shell.

Catches: missing nginx location block, wrong container name in proxy_pass,
missing COPY in the shell Dockerfile, missing import in shell main.tsx.

These tests do NOT use the TestClient fixture — they require the full stack.
"""

import httpx

SHELL = "http://atlas-shell"


def test_essaycards_proxy_returns_json():
    """GET /api/essaycards/essays must be proxied to the backend, not served as HTML."""
    r = httpx.get(f"{SHELL}/api/essaycards/essays", timeout=5)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    ct = r.headers.get("content-type", "")
    assert "application/json" in ct, (
        f"Expected JSON content-type, got '{ct}' — "
        "nginx likely missing /api/essaycards location block or serving SPA fallback"
    )


def test_review_stats_summary_proxy_returns_json():
    """GET /api/essaycards/review-stats/summary (Sprint11_ReviewStats) must be
    proxied to the backend and reach the new review_stats router mounted in
    backend/main.py — same /api/essaycards prefix as every other EssayCards
    route, so no nginx/main.tsx/Dockerfile changes were needed this sprint,
    but a missing app.include_router(review_stats.router, ...) would still
    surface here as a 404."""
    r = httpx.get(f"{SHELL}/api/essaycards/review-stats/summary", timeout=5)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    ct = r.headers.get("content-type", "")
    assert "application/json" in ct, f"Expected JSON content-type, got '{ct}'"


def test_shell_serves_app_at_basepath():
    """GET /essaycards must return the shell HTML (app is registered in main.tsx)."""
    r = httpx.get(f"{SHELL}/essaycards", timeout=5)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    ct = r.headers.get("content-type", "")
    assert "text/html" in ct, f"Expected HTML, got '{ct}'"
    assert "<script" in r.text, (
        "Shell HTML has no script tag — app bundle may not have been built correctly"
    )
