"""
REST tests for backend/routers/session.py.

Deliberately never exercises backend/claude_process.run_turn (the real
`claude` subprocess spawn) — that path is only reachable via the WS route in
backend/ws.py, which is verified manually per the Sprint 1 plan, not here.
POST /session/interrupt is safe to call for real in these tests since, with
no turn ever started, it always takes the "nothing to interrupt" branch.
"""


def test_get_session_empty_when_none_active(client):
    """Fixture has one ENDED session — it must not appear here."""
    r = client.get("/api/claudeconsole/session")
    assert r.status_code == 200
    data = r.json()
    assert data["rows"] == []
    assert data["meta"]["total"] == 0


def test_get_messages_empty_when_no_active_session(client):
    """Fixture has messages tied to the ended session — they must not leak out
    while there is no active session."""
    r = client.get("/api/claudeconsole/session/messages")
    assert r.status_code == 200
    assert r.json()["rows"] == []


def test_start_session_creates_active_row(client):
    r = client.post("/api/claudeconsole/session", json={"permission_mode": "acceptEdits"})
    assert r.status_code == 200
    data = r.json()
    assert data["meta"]["total"] == 1
    row = data["rows"][0]
    assert row["status"] == "active"
    assert row["permission_mode"] == "acceptEdits"
    assert "id" in row


def test_start_session_rejects_invalid_permission_mode(client):
    r = client.post("/api/claudeconsole/session", json={"permission_mode": "sudo"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_start_session_ends_prior_active(client, db_conn):
    first = client.post("/api/claudeconsole/session", json={"permission_mode": "plan"}).json()["rows"][0]
    second = client.post("/api/claudeconsole/session", json={"permission_mode": "acceptEdits"}).json()["rows"][0]

    with db_conn.cursor() as cur:
        cur.execute("select status from claudeconsole.sessions where id = %s", (first["id"],))
        assert cur.fetchone()["status"] == "ended"
        cur.execute("select status from claudeconsole.sessions where id = %s", (second["id"],))
        assert cur.fetchone()["status"] == "active"

    r = client.get("/api/claudeconsole/session")
    assert r.json()["meta"]["total"] == 1
    assert r.json()["rows"][0]["id"] == second["id"]


def test_get_messages_returns_only_active_sessions_rows(client, db_conn):
    started = client.post("/api/claudeconsole/session", json={"permission_mode": "acceptEdits"}).json()["rows"][0]

    with db_conn.cursor() as cur:
        cur.execute(
            "insert into claudeconsole.messages (session_id, role, content) values (%s, 'user', 'ping')",
            (started["id"],),
        )

    r = client.get("/api/claudeconsole/session/messages")
    assert r.status_code == 200
    data = r.json()
    assert data["meta"]["total"] == 1
    assert data["rows"][0]["content"] == "ping"
    assert data["rows"][0]["role"] == "user"


def test_interrupt_with_no_active_turn_returns_409(client):
    client.post("/api/claudeconsole/session", json={"permission_mode": "acceptEdits"})
    r = client.post("/api/claudeconsole/session/interrupt")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "NO_ACTIVE_TURN"


def test_end_session(client):
    client.post("/api/claudeconsole/session", json={"permission_mode": "acceptEdits"})
    r = client.post("/api/claudeconsole/session/end")
    assert r.status_code == 200
    assert r.json()["status"] == "ended"

    r = client.get("/api/claudeconsole/session")
    assert r.json()["rows"] == []


def test_end_session_with_none_active_returns_409(client):
    r = client.post("/api/claudeconsole/session/end")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "NO_ACTIVE_SESSION"
