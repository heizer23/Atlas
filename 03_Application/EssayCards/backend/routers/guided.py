"""
Guided section progression (Levels 1-6) — see backend/guided.py.

GET  /sections/{section_id}/guided-package   export package (bespoke JSON for the
     clipboard, a deliberate R-CON-BP-04 exemption, same class as
     /essays/{id}/examination-package). Params: level (optional int; default =
     next level to conduct; allowed 1..completed+1).
POST /guided/import                          mutation; raw Request body, manual
     validation -> ApiError VALIDATION_ERROR. Body:
     {"guided_session": {...AI reply...}, "learner_decision": "advance"|"stay"}.
GET  /sections/{section_id}/guided-sessions  history, newest first -> Dataset.
"""

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.database import get_db
from backend.guided import build_guided_package, import_guided_session, validate_guided_body
from platform_contracts import ColumnSchema, Dataset, DatasetMeta
from platform_errorhandling import api_error

router = APIRouter(tags=["guided"])

GUIDED_SESSION_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="session_at",       label="Session",        type="date",    sortable=True,  filterable=False),
    ColumnSchema(key="level",            label="Level",          type="number",  sortable=True,  filterable=True),
    ColumnSchema(key="recommendation",   label="AI recommended", type="string",  sortable=False, filterable=True),
    ColumnSchema(key="learner_decision", label="Learner chose",  type="string",  sortable=False, filterable=True),
    ColumnSchema(key="advanced_to",      label="Advanced to",    type="number",  sortable=False, filterable=False),
    ColumnSchema(key="rationale",        label="Rationale",      type="string",  sortable=False, filterable=False, detail_visible=True),
    ColumnSchema(key="demonstrated",     label="Demonstrated",   type="string",  sortable=False, filterable=False, detail_visible=True),
    ColumnSchema(key="gaps_text",        label="Open gaps",      type="string",  sortable=False, filterable=False, detail_visible=True),
]


@router.get("/sections/{section_id}/guided-package", response_model=None)
def get_guided_package(section_id: str, level: str | None = None) -> JSONResponse:
    parsed: int | None = None
    if level not in (None, ""):
        try:
            parsed = int(level)
        except ValueError:
            return api_error("VALIDATION_ERROR", "level must be an integer")
    with get_db() as conn:
        with conn.cursor() as cur:
            package, problem = build_guided_package(cur, section_id, parsed)
    if problem:
        return api_error("VALIDATION_ERROR", problem)
    if package is None:
        return api_error("NOT_FOUND", f"Section {section_id} not found", status=404)
    return JSONResponse(content=package)


@router.post("/guided/import", response_model=None)
async def import_guided(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return api_error("VALIDATION_ERROR", "Request body must be valid JSON")
    session, error = validate_guided_body(body)
    if error is not None:
        return error

    with get_db() as conn:
        try:
            with conn.cursor() as cur:
                result, error = import_guided_session(cur, session)
                if error is not None:
                    conn.rollback()
                    return error
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return JSONResponse(content=result)


@router.get("/sections/{section_id}/guided-sessions", response_model=None)
def list_guided_sessions(section_id: str) -> JSONResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select 1 from essaycards.essay_sections where id = %s", (section_id,))
            if not cur.fetchone():
                return api_error("NOT_FOUND", f"Section {section_id} not found", status=404)
            cur.execute(
                """
                select id, session_at, level, recommendation, learner_decision, advanced_to,
                       rationale, demonstrated, gaps
                from essaycards.section_guided_sessions
                where section_id = %s
                order by session_at desc, created_at desc
                """,
                (section_id,),
            )
            rows: list[dict[str, Any]] = []
            for r in cur.fetchall():
                d = dict(r)
                d["id"] = str(d["id"])
                d["session_at"] = d["session_at"].isoformat()
                d["gaps_text"] = "\n".join(
                    ("[serious] " if g["serious"] else "") + g["text"] for g in d.pop("gaps")
                )
                rows.append(d)

    dataset = Dataset(
        meta=DatasetMeta(
            object_type="section_guided_session",
            label="Guided Sessions",
            total=len(rows),
            page=1,
            page_size=max(len(rows), 1),
            row_actions=[],
        ),
        **{"schema": GUIDED_SESSION_SCHEMA},
        rows=rows,
    )
    return JSONResponse(content=dataset.model_dump(by_alias=True, mode="json"))
