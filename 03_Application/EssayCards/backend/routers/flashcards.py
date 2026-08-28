"""
GET /flashcards/due and POST /flashcards/{flashcard_id}/review.

GET /due is a read endpoint and returns Dataset per R-CON-BP-04.

POST .../review is a mutation endpoint (R-CON-BP-04 exempt from the Dataset
requirement). It reads the raw Starlette Request body — not a Pydantic body
model — so a missing grade key, a non-string grade value, an out-of-set grade
value, or an unparsable JSON body are ALL caught by application code and
returned as ApiError with error.code=VALIDATION_ERROR (400). FastAPI's default
RequestValidationError 422 shape must never be produced by this endpoint.

'/due' is registered before the parameterised '/{flashcard_id}/review' route
to avoid FastAPI path-matching ambiguity with any future single-segment route.
"""

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.database import get_db
from backend.scheduling import VALID_GRADES, compute_next_due_at
from platform_contracts import ColumnSchema, Dataset, DatasetMeta
from platform_errorhandling import api_error

router = APIRouter(prefix="/flashcards", tags=["flashcards"])

DUE_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="question",    label="Question", type="string", sortable=False, filterable=False),
    ColumnSchema(key="answer",      label="Answer",   type="string", sortable=False, filterable=False, detail_visible=True),
    ColumnSchema(key="essay_id",    label="Essay",    type="string", sortable=False, filterable=True),
    ColumnSchema(key="section_id",  label="Section",  type="string", sortable=False, filterable=True),
    ColumnSchema(key="anchor_slug", label="Anchor",   type="string", sortable=False, filterable=False),
    ColumnSchema(key="next_due_at", label="Due",      type="date",   sortable=True,  filterable=False),
]


def _due_row_to_dict(row: Any) -> dict[str, Any]:
    d = dict(row)
    d["id"] = str(d["id"])
    d["flashcard_id"] = str(d["flashcard_id"])
    d["essay_id"] = str(d["essay_id"])
    d["section_id"] = str(d["section_id"])
    if d.get("next_due_at"):
        d["next_due_at"] = d["next_due_at"].isoformat()
    return d


def _dataset_response(dataset: Dataset) -> JSONResponse:
    return JSONResponse(content=dataset.model_dump(by_alias=True, mode="json"))


def _due_dataset(rows: list[dict[str, Any]]) -> Dataset:
    return Dataset(
        meta=DatasetMeta(
            object_type="flashcard",
            label="Due Flashcards",
            total=len(rows),
            page=1,
            page_size=max(len(rows), 1),
            row_actions=["review"],
        ),
        **{"schema": DUE_SCHEMA},
        rows=rows,
    )


@router.get("/due", response_model=None)
def list_due_flashcards(essay_id: str | None = None, section_id: str | None = None) -> JSONResponse:
    """
    Allowed combinations: {} system-wide; {essay_id} due cards in that essay;
    {essay_id, section_id} due cards in that section only. {section_id} alone
    is rejected with VALIDATION_ERROR.

    'Due' = next_due_at <= now(), evaluated by Postgres at query time.
    Ordered by next_due_at asc (most overdue first). Empty result is valid.
    """
    if section_id and not essay_id:
        return api_error("VALIDATION_ERROR", "section_id requires essay_id to also be provided")

    conditions: list[str] = ["frs.next_due_at <= now()"]
    params: list[Any] = []
    if essay_id:
        conditions.append("f.essay_id = %s")
        params.append(essay_id)
    if section_id:
        conditions.append("f.section_id = %s")
        params.append(section_id)
    where = "where " + " and ".join(conditions)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select f.id as flashcard_id, f.question, f.answer, f.essay_id, f.section_id,
                       s.anchor_slug, frs.next_due_at
                from essaycards.flashcards f
                join essaycards.flashcard_review_state frs on frs.flashcard_id = f.id
                join essaycards.essay_sections s on s.id = f.section_id
                {where}
                order by frs.next_due_at asc
                """,
                params,
            )
            rows = []
            for r in cur.fetchall():
                d = dict(r)
                d["id"] = d["flashcard_id"]
                rows.append(_due_row_to_dict(d))

    return _dataset_response(_due_dataset(rows))


async def _parse_review_grade(request: Request) -> tuple[str | None, JSONResponse | None]:
    """
    Validate the `grade` field manually from the raw request body.

    Returns (grade, None) on success, or (None, error_response) for any
    invalid shape: unparsable JSON, non-object body, missing grade key,
    non-string grade, or a grade outside VALID_GRADES.
    """
    try:
        body = await request.json()
    except Exception:
        return None, api_error("VALIDATION_ERROR", "Request body must be valid JSON")

    if not isinstance(body, dict):
        return None, api_error("VALIDATION_ERROR", "Request body must be a JSON object")

    grade = body.get("grade")
    if not isinstance(grade, str) or grade not in VALID_GRADES:
        return None, api_error(
            "VALIDATION_ERROR",
            f"grade must be one of: {', '.join(sorted(VALID_GRADES))}",
        )

    return grade, None


@router.post("/{flashcard_id}/review", response_model=None)
async def review_flashcard(flashcard_id: str, request: Request) -> JSONResponse:
    """
    Grade a flashcard and persist its updated scheduling state.

    R-CON-AL-06 time authority: a single `select now()` read at the start of
    the transaction is reused as both last_reviewed_at and the base for
    computing next_due_at.
    """
    grade, error = await _parse_review_grade(request)
    if error is not None:
        return error

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select now() as now")
            now = cur.fetchone()["now"]

            cur.execute(
                "select last_reviewed_at from essaycards.flashcard_review_state where flashcard_id = %s",
                (flashcard_id,),
            )
            state_row = cur.fetchone()
            if not state_row:
                return api_error("NOT_FOUND", f"Flashcard {flashcard_id} not found", status=404)

            next_due_at = compute_next_due_at(grade, state_row["last_reviewed_at"], now)

            cur.execute(
                """
                update essaycards.flashcard_review_state
                set last_reviewed_at = %s, next_due_at = %s, updated_at = %s
                where flashcard_id = %s
                """,
                (now, next_due_at, now, flashcard_id),
            )
        conn.commit()

    return JSONResponse(content={
        "flashcard_id": flashcard_id,
        "last_reviewed_at": now.isoformat(),
        "next_due_at": next_due_at.isoformat(),
    })
