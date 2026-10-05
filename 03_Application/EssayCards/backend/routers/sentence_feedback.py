"""
Sentence feedback (Sprint13_ReviewStatsSentenceFeedback): per-sentence
"difficult" / "thumbs up" marks in the essay reader.

  GET   /essays/{essay_id}/sentences          -> Dataset (server-computed sentences)
  GET   /essays/{essay_id}/sentence-feedback  -> Dataset (sparse: marked sentences only)
  PATCH /sections/{section_id}/sentence-feedback -> typed record (mutation, Dataset-exempt)

Sentence boundaries come only from backend.sentences.split_sentences. A row in
essaycards.sentence_feedback exists iff at least one flag is true.
"""

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.database import get_db
from backend.sentences import split_sentences
from platform_contracts import ColumnSchema, Dataset, DatasetMeta
from platform_errorhandling import api_error

router = APIRouter(tags=["sentence_feedback"])

SENTENCE_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="section_id", label="Section", type="string", sortable=False, filterable=False),
    ColumnSchema(key="sentence_index", label="Sentence index", type="number", sortable=False, filterable=False),
    ColumnSchema(key="text", label="Text", type="string", sortable=False, filterable=False),
]

SENTENCE_FEEDBACK_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="section_id", label="Section", type="string", sortable=False, filterable=False),
    ColumnSchema(key="sentence_index", label="Sentence index", type="number", sortable=False, filterable=False),
    ColumnSchema(key="sentence_text", label="Sentence", type="string", sortable=False, filterable=False),
    ColumnSchema(key="is_difficult", label="Difficult", type="boolean", sortable=False, filterable=False),
    ColumnSchema(key="is_thumbs_up", label="Thumbs up", type="boolean", sortable=False, filterable=False),
    ColumnSchema(key="created_at", label="Created", type="date", sortable=False, filterable=False),
    ColumnSchema(key="updated_at", label="Updated", type="date", sortable=False, filterable=False),
]

_FLAGS = ("difficult", "thumbs_up")


class SentenceFeedbackUpdate(BaseModel):
    sentence_index: int
    sentence_text: str
    flag: str
    value: bool


def _dataset_response(dataset: Dataset) -> JSONResponse:
    return JSONResponse(content=dataset.model_dump(by_alias=True, mode="json"))


def _dataset(object_type: str, label: str, schema: list[ColumnSchema], rows: list[dict[str, Any]]) -> Dataset:
    return Dataset(
        meta=DatasetMeta(
            object_type=object_type, label=label, total=len(rows),
            page=1, page_size=max(len(rows), 1), row_actions=[],
        ),
        **{"schema": schema},
        rows=rows,
    )


def _essay_exists(cur: Any, essay_id: str) -> bool:
    cur.execute("select 1 from essaycards.essays where id::text = %s", (essay_id,))
    return cur.fetchone() is not None


@router.get("/essays/{essay_id}/sentences", response_model=None)
def list_essay_sentences(essay_id: str) -> JSONResponse:
    """Flat sentence rows across every section, ordered (section order_index,
    sentence_index). A section with no sentences contributes no rows."""
    with get_db() as conn:
        with conn.cursor() as cur:
            if not _essay_exists(cur, essay_id):
                return api_error("NOT_FOUND", f"Essay {essay_id} not found", status=404)
            cur.execute(
                "select id::text as id, body_markdown from essaycards.essay_sections "
                "where essay_id::text = %s order by order_index asc",
                (essay_id,),
            )
            sections = cur.fetchall()

    rows = [
        {"section_id": s["id"], "sentence_index": i, "text": text}
        for s in sections
        for i, text in enumerate(split_sentences(s["body_markdown"]))
    ]
    return _dataset_response(_dataset("essay_sentence", "Essay Sentences", SENTENCE_SCHEMA, rows))


@router.get("/essays/{essay_id}/sentence-feedback", response_model=None)
def list_essay_sentence_feedback(essay_id: str) -> JSONResponse:
    """Sparse: only sentences with at least one flag set. Not re-validated
    against current section content (see 10_architecture.json invariants)."""
    with get_db() as conn:
        with conn.cursor() as cur:
            if not _essay_exists(cur, essay_id):
                return api_error("NOT_FOUND", f"Essay {essay_id} not found", status=404)
            cur.execute(
                """
                select sf.section_id::text as section_id, sf.sentence_index, sf.sentence_text,
                       sf.is_difficult, sf.is_thumbs_up, sf.created_at, sf.updated_at
                from essaycards.sentence_feedback sf
                join essaycards.essay_sections s on s.id = sf.section_id
                where s.essay_id::text = %s
                order by s.order_index asc, sf.sentence_index asc
                """,
                (essay_id,),
            )
            rows = [dict(r) for r in cur.fetchall()]
    return _dataset_response(
        _dataset("sentence_feedback", "Sentence Feedback", SENTENCE_FEEDBACK_SCHEMA, rows)
    )


@router.patch("/sections/{section_id}/sentence-feedback", response_model=None)
def update_sentence_feedback(section_id: str, body: SentenceFeedbackUpdate) -> JSONResponse:
    """Set one flag on one sentence to an explicit value. Deletes the row when
    both flags end up false. Always returns the resulting record, status 200."""
    if body.flag not in _FLAGS:
        return api_error("VALIDATION_ERROR", "flag must be one of 'difficult', 'thumbs_up'")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select id::text as id, body_markdown from essaycards.essay_sections where id::text = %s",
                (section_id,),
            )
            section = cur.fetchone()
            if section is None:
                return api_error("NOT_FOUND", f"Section {section_id} not found", status=404)

            sentences = split_sentences(section["body_markdown"])
            if body.sentence_index < 0 or body.sentence_index >= len(sentences):
                return api_error(
                    "VALIDATION_ERROR",
                    f"sentence_index {body.sentence_index} is out of range for this section "
                    "(it may have been edited since you loaded this page — reload and try again)",
                )
            if sentences[body.sentence_index] != body.sentence_text:
                return api_error(
                    "VALIDATION_ERROR",
                    "sentence_text does not match the section's current text at that index "
                    "(edited since you loaded this page — reload and try again)",
                )

            cur.execute(
                "select is_difficult, is_thumbs_up from essaycards.sentence_feedback "
                "where section_id::text = %s and sentence_index = %s",
                (section_id, body.sentence_index),
            )
            existing = cur.fetchone()
            is_difficult = bool(existing["is_difficult"]) if existing else False
            is_thumbs_up = bool(existing["is_thumbs_up"]) if existing else False
            if body.flag == "difficult":
                is_difficult = body.value
            else:
                is_thumbs_up = body.value

            if is_difficult or is_thumbs_up:
                cur.execute(
                    """
                    insert into essaycards.sentence_feedback
                        (section_id, sentence_index, sentence_text, is_difficult, is_thumbs_up)
                    values (%s, %s, %s, %s, %s)
                    on conflict (section_id, sentence_index) do update set
                        sentence_text = excluded.sentence_text,
                        is_difficult = excluded.is_difficult,
                        is_thumbs_up = excluded.is_thumbs_up,
                        updated_at = now()
                    """,
                    (section_id, body.sentence_index, body.sentence_text, is_difficult, is_thumbs_up),
                )
            else:
                cur.execute(
                    "delete from essaycards.sentence_feedback where section_id::text = %s and sentence_index = %s",
                    (section_id, body.sentence_index),
                )
            conn.commit()

    return JSONResponse(content={
        "section_id": section_id,
        "sentence_index": body.sentence_index,
        "is_difficult": is_difficult,
        "is_thumbs_up": is_thumbs_up,
    })
