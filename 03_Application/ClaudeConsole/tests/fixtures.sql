-- ClaudeConsole Sprint 1 — test fixtures
--
-- IDs use pattern f3000001-... (sessions) / f4000001-... (messages)
-- All chars are valid hex — readable in test output.

-- ── One already-ended session, with history ─────────────────────────────────
-- Used to verify GET /claudeconsole/session and /session/messages only ever
-- surface the ACTIVE session — this one must never appear in either response.

INSERT INTO claudeconsole.sessions
  (id, claude_session_id, permission_mode, status, created_at, ended_at)
VALUES
  ('f3000001-0000-0000-0000-000000000000', 'claude-sess-abc', 'acceptEdits', 'ended', now() - interval '1 day', now() - interval '1 day' + interval '10 minutes');

INSERT INTO claudeconsole.messages
  (id, session_id, role, content, raw_event, created_at)
VALUES
  ('f4000001-0000-0000-0000-000000000000', 'f3000001-0000-0000-0000-000000000000', 'user',      'hello',        null, now() - interval '1 day'),
  ('f4000002-0000-0000-0000-000000000000', 'f3000001-0000-0000-0000-000000000000', 'assistant', 'hi there',     null, now() - interval '1 day' + interval '1 minute');
