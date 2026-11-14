import httpx

SHELL = "http://atlas-shell"


def test_speech_proxy_reaches_backend():
    # Invalid mime: reaching the backend yields a JSON error envelope, not nginx 404/502 HTML.
    r = httpx.post(f"{SHELL}/api/speech/recordings", json={"mime_type": "text/plain"}, timeout=5)
    assert r.status_code in (415, 503)
    assert "application/json" in r.headers.get("content-type", "")
    assert r.json()["error"]["code"] in ("UNSUPPORTED_MIME", "SPEECH_NOT_CONFIGURED")
