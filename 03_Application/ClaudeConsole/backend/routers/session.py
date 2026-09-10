"""
GET /session and GET /session/messages return ordinary Dataset objects — no
bespoke-shape exception (R-CON-BP-04). A single current-session status is a
legitimate 0-or-1-row Dataset; a chat transcript is a legitimate multi-row
Dataset, with the chat UI acting as a custom renderer over those rows
(bubbles) rather than a table. This differs from EssayCards' bespoke-shape
exemption (justified there because that payload is copied to an external LLM
and never rendered by the UI) — ClaudeConsole's messages ARE rendered by the
UI, so Dataset applies straightforwardly, no exemption needed.

POST /session returns a Dataset as its success response (a set-and-return
pattern) — explicitly permitted by R-CON-BP-04 for mutation endpoints.
POST /session/interrupt and POST /session/end return small typed records.

Chat send/receive itself lives in backend/ws.py as a WebSocket route, which
is outside this rule's scope entirely (it governs REST response shapes, not
socket frames) — see that module's docstring.
"""
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.database import get_db
from backend import claude_process
from platform_errorhandling import api_error
from platform_contracts import ColumnSchema, Dataset, DatasetMeta

router = APIRouter(prefix="/claudeconsole", tags=["claudeconsole"])

VALID_PERMISSION_MODES = {"plan", "acceptEdits", "bypassPermissions"}

SESSION_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="id",              label="ID",              type="string", sortable=False, filterable=False),
    ColumnSchema(key="permission_mode", label="Permission Mode", type="enum",   sortable=False, filterable=False),
    ColumnSchema(key="status",          label="Status",          type="enum",   sortable=False, filterable=False),
    ColumnSchema(key="created_at",      label="Created",         type="date",   sortable=False, filterable=False),
]

MESSAGE_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="id",          label="ID",          type="string", sortable=False, filterable=False),
    ColumnSchema(key="role",        label="Role",        type="enum",   sortable=False, filterable=False),
    ColumnSchema(key="content",     label="Content",     type="string", sortable=False, filterable=False),
    ColumnSchema(key="tool_detail", label="Tool Detail", type="string", sortable=False, filterable=False, detail_visible=True),
    ColumnSchema(key="created_at",  label="Created",     type="date",   sortable=True,  filterable=False),
]


class SessionCreate(BaseModel):
    permission_mode: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _dataset_response(dataset: Dataset) -> JSONResponse:
    return JSONResponse(content=dataset.model_dump(by_alias=True, mode="json"))


def _session_row_to_dict(row: Any) -> dict[str, Any]:
    d = dict(row)
    d["id"] = str(d["id"])
    if d.get("created_at"):
        d["created_at"] = d["created_at"].isoformat()
    d.pop("claude_session_id", None)
    d.pop("ended_at", None)
    return d


def _session_dataset(rows: list[dict[str, Any]]) -> Dataset:
    return Dataset(
        meta=DatasetMeta(
            object_type="claudeconsole_session",
            label="Session",
            total=len(rows),
            page=1,
            page_size=max(len(rows), 1),
            row_actions=[],
        ),
        **{"schema": SESSION_SCHEMA},
        rows=rows,
    )


def _message_row_to_dict(row: Any) -> dict[str, Any]:
    import json as _json
    d = dict(row)
    d["id"] = str(d["id"])
    raw_event = d.pop("raw_event", None)
    d["tool_detail"] = _json.dumps(raw_event) if raw_event is not None else None
    if d.get("created_at"):
        d["created_at"] = d["created_at"].isoformat()
    return d


def _messages_dataset(rows: list[dict[str, Any]]) -> Dataset:
    return Dataset(
        meta=DatasetMeta(
            object_type="claudeconsole_message",
            label="Messages",
            total=len(rows),
            page=1,
            page_size=max(len(rows), 1),
            row_actions=[],
        ),
        **{"schema": MESSAGE_SCHEMA},
        rows=rows,
    )


def get_active_session() -> dict[str, Any] | None:
    """Used by both the REST routes below and backend/ws.py."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, claude_session_id, permission_mode, status, created_at
                from claudeconsole.sessions
                where status = 'active'
                order by created_at desc
                limit 1
                """
            )
            row = cur.fetchone()
            return dict(row) if row else None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/session", response_model=None)
def get_session() -> JSONResponse:
    row = get_active_session()
    if not row:
        return _dataset_response(_session_dataset([]))
    return _dataset_response(_session_dataset([_session_row_to_dict(row)]))


@router.get("/session/messages", response_model=None)
def get_messages() -> JSONResponse:
    active = get_active_session()
    if not active:
        return _dataset_response(_messages_dataset([]))
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, role, content, raw_event, created_at
                from claudeconsole.messages
                where session_id = %s
                order by created_at asc
                """,
                (active["id"],),
            )
            rows = [_message_row_to_dict(r) for r in cur.fetchall()]
    return _dataset_response(_messages_dataset(rows))


@router.post("/session", response_model=None)
def start_session(body: SessionCreate) -> JSONResponse:
    if body.permission_mode not in VALID_PERMISSION_MODES:
        return api_error(
            "VALIDATION_ERROR",
            f"permission_mode must be one of: {', '.join(sorted(VALID_PERMISSION_MODES))}",
        )

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "update claudeconsole.sessions set status = 'ended', ended_at = now() where status = 'active'"
            )
            cur.execute(
                """
                insert into claudeconsole.sessions (permission_mode, status)
                values (%s, 'active')
                returning id, permission_mode, status, created_at
                """,
                (body.permission_mode,),
            )
            row = cur.fetchone()
        conn.commit()

    return _dataset_response(_session_dataset([_session_row_to_dict(row)]))


@router.post("/session/interrupt", response_model=None)
async def interrupt_session() -> JSONResponse:
    killed = await claude_process.interrupt()
    if not killed:
        return api_error("NO_ACTIVE_TURN", "No turn is currently running", status=409)
    return JSONResponse(content={"status": "interrupted"})


@router.post("/session/end", response_model=None)
def end_session() -> JSONResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update claudeconsole.sessions
                set status = 'ended', ended_at = now()
                where status = 'active'
                returning id
                """
            )
            ended = cur.fetchone()
        conn.commit()

    if not ended:
        return api_error("NO_ACTIVE_SESSION", "No active session to end", status=409)
    return JSONResponse(content={"status": "ended"})
