"""
Subprocess lifecycle for a single headless `claude` CLI session.

One `claude -p` invocation = one full turn. Conversation continuity across
turns is carried by Claude Code's own `--resume <claude_session_id>` on the
*next* invocation, not by keeping the subprocess alive between turns.

Module-level singleton state (`_active`) is only valid because ClaudeConsole
controls exactly one session at a time (Sprint 1 scope). Do not generalize
this pattern if multi-session support is ever added.

Verified 2026-09-10 against installed CLI v2.1.197 (two turns, same session,
`--resume` continuity confirmed): `_is_init_event` matches on
`{"type":"system","subtype":"init",...}`, `_is_terminal_event` matches on
`{"type":"result",...}`, `_extract_text` correctly pulls the reply out of the
`assistant` event's `message.content`. `--cwd` is NOT a valid flag on this CLI
version (the subprocess's actual cwd is already set via the `cwd=ATLAS_ROOT`
kwarg to `create_subprocess_exec`, which is sufficient on its own).
`--output-format stream-json` requires `--verbose` when combined with
`--print`, or the CLI refuses to start. A fresh, never-interactively-opened
`~/.claude.json` also blocks every turn behind the workspace trust dialog —
see `ensure_workspace_trusted()` below.
"""
import asyncio
import json
import logging
import os
from typing import Any, Awaitable, Callable

from backend.database import get_db

log = logging.getLogger("claudeconsole.claude_process")

ATLAS_ROOT = "/home/linse/Prod/Atlas"
CLAUDE_CONFIG_PATH = os.path.expanduser("~/.claude.json")

OnEvent = Callable[[dict[str, Any]], Awaitable[None]]


def ensure_workspace_trusted() -> None:
    """Headless `claude -p` never shows the interactive trust dialog, so a
    fresh container's default (untrusted) ~/.claude.json blocks every turn.
    Seed just this repo path's trust flag into the container-local config —
    deliberately NOT the host's real ~/.claude.json (that carries metadata
    for every project ever opened; mounting it would be broader exposure
    than this app needs). Idempotent; safe to call on every startup."""
    try:
        with open(CLAUDE_CONFIG_PATH) as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        config = {}
    project = config.setdefault("projects", {}).setdefault(ATLAS_ROOT, {})
    if not project.get("hasTrustDialogAccepted"):
        project["hasTrustDialogAccepted"] = True
        with open(CLAUDE_CONFIG_PATH, "w") as f:
            json.dump(config, f)


class TurnInProgress(Exception):
    """Raised when run_turn() is called while a turn is already active."""


class _ActiveTurn:
    def __init__(self) -> None:
        self.process: asyncio.subprocess.Process | None = None
        self.task: asyncio.Task | None = None


_active = _ActiveTurn()
_lock = asyncio.Lock()


def is_turn_active() -> bool:
    return _active.process is not None


async def interrupt() -> bool:
    """Kill the in-flight turn, if any. Returns True if something was killed."""
    if _active.process is None:
        return False
    _active.process.kill()
    if _active.task is not None:
        _active.task.cancel()
    return True


def _persist_message(session_id: str, role: str, content: str | None, raw_event: dict[str, Any] | None) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into claudeconsole.messages (session_id, role, content, raw_event)
                values (%s, %s, %s, %s::jsonb)
                """,
                (session_id, role, content, json.dumps(raw_event) if raw_event is not None else None),
            )
        conn.commit()


def _set_claude_session_id(session_id: str, claude_session_id: str) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "update claudeconsole.sessions set claude_session_id = %s where id = %s",
                (claude_session_id, session_id),
            )
        conn.commit()


def _extract_text(event: dict[str, Any]) -> str | None:
    """Best-effort extraction of human-legible text from a stream-json event,
    for chat-bubble rendering. The full event is always persisted in
    raw_event regardless of what this returns."""
    if isinstance(event.get("text"), str):
        return event["text"]
    message = event.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
            if parts:
                return "".join(parts)
    return None


def _is_init_event(event: dict[str, Any]) -> str | None:
    """Return the claude-side session id if this is the init event, else None."""
    if event.get("type") == "system" and event.get("subtype") == "init":
        return event.get("session_id")
    if event.get("type") == "init":
        return event.get("session_id")
    return None


def _is_terminal_event(event: dict[str, Any]) -> bool:
    return event.get("type") == "result"


async def run_turn(
    db_session_id: str,
    prompt: str,
    permission_mode: str,
    claude_session_id: str | None,
    on_event: OnEvent,
) -> None:
    """Spawn one `claude -p` invocation for one turn, streaming parsed events to
    on_event and persisting them to `messages` as they arrive.

    Raises TurnInProgress if a turn is already running.
    """
    async with _lock:
        if _active.process is not None:
            raise TurnInProgress()

        argv = [
            "claude", "-p",
            "--output-format", "stream-json",
            "--input-format", "stream-json",
            "--verbose",
            "--permission-mode", permission_mode,
        ]
        if claude_session_id:
            argv += ["--resume", claude_session_id]

        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=ATLAS_ROOT,
        )
        _active.process = proc
        _active.task = asyncio.current_task()

    try:
        _persist_message(db_session_id, "user", prompt, None)

        input_event = {
            "type": "user",
            "message": {"role": "user", "content": [{"type": "text", "text": prompt}]},
        }
        assert proc.stdin is not None
        proc.stdin.write((json.dumps(input_event) + "\n").encode())
        await proc.stdin.drain()
        proc.stdin.close()

        assert proc.stdout is not None
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                log.warning("Non-JSON line from claude subprocess: %r", line)
                continue

            new_claude_session_id = _is_init_event(event)
            if new_claude_session_id and not claude_session_id:
                _set_claude_session_id(db_session_id, new_claude_session_id)
                claude_session_id = new_claude_session_id

            role = "user" if event.get("type") == "user" else "assistant"
            _persist_message(db_session_id, role, _extract_text(event), event)
            await on_event(event)

            if _is_terminal_event(event):
                break

        await proc.wait()
        if proc.returncode not in (0, None):
            stderr_output = b""
            if proc.stderr is not None:
                stderr_output = await proc.stderr.read()
            log.warning(
                "claude subprocess exited %s: %s",
                proc.returncode,
                stderr_output.decode(errors="replace"),
            )
    finally:
        async with _lock:
            _active.process = None
            _active.task = None
