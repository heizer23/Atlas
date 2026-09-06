"""
GET /flashcards/{flashcard_id}/exploration-package and
POST /flashcards/exploration/import.

GET /exploration-package is a GET that returns a bespoke JSON blob, not a
Dataset. Same deliberate R-CON-BP-04 interpretation as
GET /essays/{id}/examination-package (see backend/routers/examinations.py
module docstring): the frontend copies it verbatim to the clipboard for an
external ChatGPT conversation — it is not rendered by a Dataset-consuming UI
component. Documented here per R-OPS-BP-01 rather than silently normalised.
404 ApiError if the id is malformed or the flashcard does not exist.

POST /flashcards/exploration/import is a mutation endpoint (Dataset-exempt per
R-CON-BP-04 proper). It reads the raw Starlette Request body — not a Pydantic
model — so every invalid shape is caught by application code and returned as a
descriptive ApiError (see backend/exploration.py::_import_error). The whole
import is one transaction: a failure in any action rolls back every action,
including the discussion.

?dry_run=true (or 1 / yes) validates and resolves the payload and returns the
plan WITHOUT writing anything — the frontend shows this as a preview and only
POSTs again without the flag once the user confirms.

Route registration: included after flashcards.router in backend/main.py. Its
paths (`/flashcards/{id}/exploration-package`, `/flashcards/exploration/import`)
do not collide with that router's `/flashcards/due`, `/flashcards/stats` or
`/flashcards/{id}/review`.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.database import get_db
from backend.exploration import (
    build_exploration_package,
    execute_plan,
    plan_to_public,
    resolve_and_plan,
    validate_import_body,
)
from platform_errorhandling import api_error

router = APIRouter(tags=["exploration"])

_DRY_RUN_TRUE = {"1", "true", "yes"}


@router.get("/flashcards/{flashcard_id}/exploration-package", response_model=None)
def get_exploration_package(flashcard_id: str) -> JSONResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            package = build_exploration_package(cur, flashcard_id)

    if package is None:
        return api_error("NOT_FOUND", f"Flashcard {flashcard_id} not found", status=404)

    return JSONResponse(content=package)


@router.post("/flashcards/exploration/import", response_model=None)
async def import_exploration(request: Request) -> JSONResponse:
    dry_run = request.query_params.get("dry_run", "").strip().lower() in _DRY_RUN_TRUE

    try:
        body = await request.json()
    except Exception:
        return api_error(
            "VALIDATION_ERROR",
            "EssayCards could not import this exploration result. The request "
            "body is not valid JSON. Nothing was saved. Fix the JSON and send "
            "the complete EssayCards return package again.",
        )

    actions, error = validate_import_body(body)
    if error is not None:
        return error

    with get_db() as conn:
        try:
            with conn.cursor() as cur:
                plan, error = resolve_and_plan(cur, actions)
                if error is not None:
                    conn.rollback()
                    return error

                if dry_run:
                    conn.rollback()
                    return JSONResponse(content={
                        "dry_run": True,
                        "applied": False,
                        "preview": plan_to_public(plan),
                    })

                result = execute_plan(cur, plan)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return JSONResponse(content=result)
