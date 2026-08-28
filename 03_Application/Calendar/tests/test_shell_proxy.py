"""
Shell proxy smoke tests for Calendar.

These run inside the atlas-calendar-test container which is on atlas-net
and can reach http://atlas-shell. Tests verify that nginx correctly proxies
/api/cal to atlas-calendar:8000 and serves the Calendar SPA at /calendar.
"""
import httpx

SHELL = "http://atlas-shell"


def test_cal_proxy_returns_json():
    r = httpx.get(f"{SHELL}/api/cal/events", timeout=5)
    assert r.status_code == 200
    assert "application/json" in r.headers.get("content-type", "")


def test_shell_serves_app_at_basepath():
    r = httpx.get(f"{SHELL}/calendar", timeout=5)
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
