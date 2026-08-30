"""
GET /essays/{essay_id}/examination-package, POST /examinations/import, and
GET /sections/{section_id}/examinations.

GET /examination-package is a GET endpoint but returns a bespoke JSON blob,
not a Dataset. It is not rendered by a Dataset-consuming UI component — the
frontend copies it verbatim to the clipboard for a ChatGPT oral examination,
the same way STUB_PROMPT/PLACEHOLDER_JSON in src/ShellEntry.tsx are opaque
text, not table data. This is a deliberate R-CON-BP-04 interpretation: the
rule's stated test is "does the frontend consume the response to render a
data view" (no) vs "only to confirm success / display an error" (not quite
that either) — this endpoint is a third case, a self-contained interchange
artifact, and is treated as Dataset-exempt on the same rationale class as the
mutation-endpoint exemption. Documented here per R-OPS-BP-01 rather than
silently normalized.

POST /examinations/import is a mutation endpoint (Dataset-exempt per
R-CON-BP-04 proper). It reads the raw Starlette Request body — not a
Pydantic body model — so every invalid shape is caught by application code
and returned as ApiError VALIDATION_ERROR (400), same precedent as
POST /essays/ingest. Validation is all-or-nothing: the whole payload is
structurally validated, then every (essay_slug, section_anchor_slug) pair is
resolved to existing rows, before any INSERT is issued.

GET /sections/{section_id}/examinations IS real UI-visible tabular data (a
reverse-chronological history list) and returns Dataset per R-CON-BP-04.
"""

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.database import get_db
from backend.examinations import build_export_package, import_results, validate_import_body
from platform_contracts import ColumnSchema, Dataset, DatasetMeta
from platform_errorhandling import api_error

router = APIRouter(tags=["examinations"])

EXAMINATION_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="examined_at",       label="Examined",  type="date",   sortable=True,  filterable=False),
    ColumnSchema(key="score",             label="Score",     type="number", sortable=True,  filterable=False),
    ColumnSchema(key="question",          label="Question",  type="string", sortable=False, filterable=False, detail_visible=True),
    ColumnSchema(key="answer_transcript", label="Answer",    type="string", sortable=False, filterable=False, detail_visible=True),
    ColumnSchema(key="feedback",          label="Feedback",  type="string", sortable=False, filterable=False, detail_visible=True),
]


def _dataset_response(dataset: Dataset) -> JSONResponse:
    return JSONResponse(content=dataset.model_dump(by_alias=True, mode="json"))


@router.get("/essays/{essay_id}/examination-package", response_model=None)
def get_examination_package(essay_id: str) -> JSONResponse:
    """
    Self-contained JSON package for conducting an oral examination outside
    the app (see module docstring re: Dataset exemption). 404 ApiError if
    essay_id does not exist. An essay with zero sections still returns a
    package with sections: [].
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            package = build_export_package(cur, essay_id)

    if package is None:
        return api_error("NOT_FOUND", f"Essay {essay_id} not found", status=404)

    return JSONResponse(content=package)


@router.post("/examinations/import", response_model=None)
async def import_examinations(request: Request) -> JSONResponse:
    """
    Store one or more historical oral-examination results. Always inserts new
    rows — never updates or overwrites an existing result. Rejects the whole
    batch (no partial writes) if any result is structurally invalid or
    references an essay/section that does not exist.
    """
    try:
        body = await request.json()
    except Exception:
        return api_error("VALIDATION_ERROR", "Request body must be valid JSON")

    results, error = validate_import_body(body)
    if error is not None:
        return error

    with get_db() as conn:
        try:
            with conn.cursor() as cur:
                inserted, error = import_results(cur, results)
                if error is not None:
                    conn.rollback()
                    return error
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return JSONResponse(content={"imported": len(inserted), "results": inserted})


@router.get("/sections/{section_id}/examinations", response_model=None)
def list_section_examinations(section_id: str) -> JSONResponse:
    """
    Full examination history for one section, most recent first. No
    parameters, no pagination — history lists for a single section are
    expected to stay small. Empty result is valid (never examined yet).
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select 1 from essaycards.essay_sections where id = %s",
                (section_id,),
            )
            if not cur.fetchone():
                return api_error("NOT_FOUND", f"Section {section_id} not found", status=404)

            cur.execute(
                """
                select id, examined_at, score, question, answer_transcript, feedback, section_version_at
                from essaycards.section_examinations
                where section_id = %s
                order by examined_at desc
                """,
                (section_id,),
            )
            rows = []
            for r in cur.fetchall():
                d: dict[str, Any] = dict(r)
                d["id"] = str(d["id"])
                d["examined_at"] = d["examined_at"].isoformat()
                d["section_version_at"] = d["section_version_at"].isoformat()
                rows.append(d)

    dataset = Dataset(
        meta=DatasetMeta(
            object_type="section_examination",
            label="Examination History",
            total=len(rows),
            page=1,
            page_size=max(len(rows), 1),
            row_actions=[],
        ),
        **{"schema": EXAMINATION_SCHEMA},
        rows=rows,
    )
    return _dataset_response(dataset)
