"""
Oral-recall endpoints (Sprint16_RecallFSRS): the Oral Recall review queue and
per-target review history. Importing results goes through POST
/examinations/import (unguided results carry a `recall` evidence object).

GET /recall/due   (R-CON-AL-01)
  Params: essay_id (optional uuid) restricts to one essay. No other params.
  Rows: one per DUE recall item — scope 'section' or 'essay' — i.e. established
  (a successful review exists) AND (next_due_at <= now() OR last rating 'again').
  Ordering: next_due_at asc (most overdue first), then essay sort_index, then
  section order (essay-scope row first). Time basis: server now(). Empty -> empty
  Dataset. meta.total is the due count; it NEVER includes flashcards.

GET /recall/reviews?section_id=|essay_id=   (exactly one required)
  Recall review history for one section or one essay-scope target, newest first.
"""

import json
import uuid
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.database import get_db
from backend.recall import recall_due_sql
from platform_contracts import ColumnSchema, Dataset, DatasetMeta
from platform_errorhandling import api_error

router = APIRouter(tags=["recall"])

_TXT = dict(type="string", sortable=False, filterable=False)
RECALL_DUE_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="id", label="Id", **_TXT),
    ColumnSchema(key="scope", label="Scope", type="string", sortable=False, filterable=True),
    ColumnSchema(key="essay_id", label="Essay", type="string", sortable=False, filterable=True),
    ColumnSchema(key="section_id", label="Section", **_TXT),
    ColumnSchema(key="essay_title", label="Essay title", **_TXT),
    ColumnSchema(key="category", label="Topic", **_TXT),
    ColumnSchema(key="section_heading", label="Section title", **_TXT),
    ColumnSchema(key="anchor_slug", label="Anchor", **_TXT),
    ColumnSchema(key="last_reviewed_at", label="Last reviewed", type="date", sortable=False, filterable=False),
    ColumnSchema(key="next_due_at", label="Due", type="date", sortable=True, filterable=False),
    ColumnSchema(key="last_rating", label="Last rating", **_TXT),
    ColumnSchema(key="review_count", label="Reviews", type="number", sortable=False, filterable=False),
    ColumnSchema(key="lapse_count", label="Lapses", type="number", sortable=False, filterable=False),
]

RECALL_REVIEW_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="id", label="Id", **_TXT),
    ColumnSchema(key="reviewed_at", label="Reviewed", type="date", sortable=True, filterable=False),
    ColumnSchema(key="rating", label="Rating", type="string", sortable=True, filterable=True),
    ColumnSchema(key="next_due_at", label="Next due", type="date", sortable=False, filterable=False),
    ColumnSchema(key="question", label="Question", type="string", sortable=False, filterable=False, detail_visible=True),
    ColumnSchema(key="answer_transcript", label="Answer", type="string", sortable=False, filterable=False, detail_visible=True),
    ColumnSchema(key="feedback", label="Feedback", type="string", sortable=False, filterable=False, detail_visible=True),
    ColumnSchema(key="evidence", label="Evidence", type="string", sortable=False, filterable=False, detail_visible=True),
]


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


def _dataset(object_type: str, label: str, schema: list[ColumnSchema], rows: list[dict[str, Any]]) -> JSONResponse:
    ds = Dataset(
        meta=DatasetMeta(object_type=object_type, label=label, total=len(rows), page=1,
                         page_size=max(len(rows), 1), row_actions=[]),
        **{"schema": schema},
        rows=rows,
    )
    return JSONResponse(content=ds.model_dump(by_alias=True, mode="json"))


def _iso(d: dict[str, Any], *keys: str) -> None:
    for k in keys:
        if d.get(k) is not None:
            d[k] = d[k].isoformat()


@router.get("/recall/due", response_model=None)
def list_due_recall(essay_id: str | None = None) -> JSONResponse:
    rows: list[dict[str, Any]] = []
    if essay_id is None or _is_uuid(essay_id):
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(recall_due_sql("and e.id = %s" if essay_id else ""), (essay_id,) if essay_id else ())
                for r in cur.fetchall():
                    d = dict(r)
                    for k in ("id", "essay_id", "section_id"):
                        d[k] = str(d[k]) if d[k] else None
                    _iso(d, "last_reviewed_at", "next_due_at")
                    rows.append(d)
    return _dataset("recall_due", "Oral Recall Due", RECALL_DUE_SCHEMA, rows)


@router.get("/recall/reviews", response_model=None)
def list_recall_reviews(section_id: str | None = None, essay_id: str | None = None) -> JSONResponse:
    if (section_id is None) == (essay_id is None):
        return api_error("VALIDATION_ERROR", "exactly one of section_id or essay_id is required")
    target = section_id or essay_id
    if not _is_uuid(target):
        return api_error("NOT_FOUND", f"{target} not found", status=404)
    where = "section_id = %s" if section_id else "essay_id = %s and section_id is null"
    rows: list[dict[str, Any]] = []
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select id, reviewed_at, rating, next_due_at, question, answer_transcript, feedback, evidence
                from essaycards.recall_reviews where {where} order by reviewed_at desc, id asc
                """,
                (target,),
            )
            for r in cur.fetchall():
                d = dict(r)
                d["id"] = str(d["id"])
                d["evidence"] = json.dumps(d["evidence"], indent=2)
                _iso(d, "reviewed_at", "next_due_at")
                rows.append(d)
    return _dataset("recall_review", "Recall History", RECALL_REVIEW_SCHEMA, rows)
