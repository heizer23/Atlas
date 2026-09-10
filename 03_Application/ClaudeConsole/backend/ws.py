"""
WS /api/claudeconsole/ws — the chat send/receive path.

Explicitly outside R-CON-BP-04's scope: that rule governs REST response
shapes, not WebSocket frames. See backend/routers/session.py's module
docstring for the paired Dataset resolution on the REST side.

Single-connection-at-a-time: this is a deliberate v1 simplification (one
session, one live view of it), not a resource limit. A second connection is
rejected outright rather than fanning events out to both or silently
displacing the first — that would create split-brain UIs where two tabs both
think they can send the next prompt. A refreshed tab reconnects cleanly once
the old socket's `finally` clears the slot below.

Per the sprint draft's stated v1 preference: a client that reconnects
mid-turn does NOT get buffered events replayed. It waits, then calls
GET /session/messages once the turn completes.
"""
import json
import logging

from fastapi import WebSocket, WebSocketDisconnect

from backend import claude_process
from backend.routers.session import get_active_session

log = logging.getLogger("claudeconsole.ws")

_current_ws: WebSocket | None = None


async def ws_endpoint(websocket: WebSocket) -> None:
    global _current_ws
    await websocket.accept()

    if _current_ws is not None:
        await websocket.send_json({
            "type": "error",
            "code": "ALREADY_CONNECTED",
            "message": "Another client is already connected to this session.",
        })
        await websocket.close(code=4409)
        return

    _current_ws = websocket
    try:
        while True:
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                break

            try:
                prompt = json.loads(raw)["prompt"]
                if not isinstance(prompt, str) or not prompt.strip():
                    raise ValueError
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                await websocket.send_json({
                    "type": "error", "code": "BAD_REQUEST",
                    "message": 'Expected {"prompt": "<non-empty text>"}',
                })
                continue

            active = get_active_session()
            if not active:
                await websocket.send_json({
                    "type": "error", "code": "NO_ACTIVE_SESSION",
                    "message": "Start a session first.",
                })
                continue

            if claude_process.is_turn_active():
                await websocket.send_json({
                    "type": "error", "code": "TURN_IN_PROGRESS",
                    "message": "A turn is already running.",
                })
                continue

            async def _forward(event: dict) -> None:
                await websocket.send_json(event)

            try:
                await claude_process.run_turn(
                    db_session_id=str(active["id"]),
                    prompt=prompt,
                    permission_mode=active["permission_mode"],
                    claude_session_id=active.get("claude_session_id"),
                    on_event=_forward,
                )
            except claude_process.TurnInProgress:
                await websocket.send_json({
                    "type": "error", "code": "TURN_IN_PROGRESS",
                    "message": "A turn is already running.",
                })
            except Exception:
                log.exception("Turn failed")
                await websocket.send_json({
                    "type": "error", "code": "TURN_FAILED",
                    "message": "The Claude Code turn failed unexpectedly.",
                })
    finally:
        _current_ws = None
