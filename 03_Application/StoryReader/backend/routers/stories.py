"""
All story, version, and annotation endpoints — single router file, mirroring
StorageTracker's backend/routers/items.py single-file convention.

Route -> internal_flow step mapping (10_architecture.json):
  GET    /stories                                      -> step 3 list_stories
  GET    /stories/{story_id}                            -> step 4 get_story_detail
  GET    /stories/{story_id}/versions/{version}         -> step 5 get_version_content
  GET    /stories/{story_id}/versions/{version}/annotations        -> step 6 list_annotations
  POST   /annotations                                   -> step 7 create_or_update_annotation
  DELETE /annotations/{annotation_id}                   -> step 8 delete_annotation
  GET    /stories/{story_id}/versions/{version}/annotations/export -> step 9 export_annotations
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from backend.database import get_db
from backend.paragraphs import split_paragraphs
from platform_errorhandling import api_error
from platform_contracts import ColumnSchema, Dataset, DatasetMeta

router = APIRouter(prefix="/storyreader", tags=["storyreader"])

VALID_REACTIONS = {"positive", "negative", "neutral", "unclear"}
_MAX_CONTEXT_LEN = 500

# ── Request models ──────────────────────────────────────────────────────────

class AnnotationCreate(BaseModel):
    story_id:        str
    version:         int
    paragraph_index: int
    char_start:      int
    char_end:        int
    selected_text:   str
    context_before:  str
    context_after:   str
    reaction:        str


class PositionUpdate(BaseModel):
    paragraph_index: int

# ── Column schemas ───────────────────────────────────────────────────────────

STORY_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="slug",                 label="Slug",             type="string", sortable=True,  filterable=True),
    ColumnSchema(key="title",                label="Title",            type="string", sortable=True,  filterable=True),
    ColumnSchema(key="latest_version",       label="Latest Version",   type="number", sortable=True),
    ColumnSchema(key="marked_passage_count", label="Marked Passages",  type="number", sortable=True),
    ColumnSchema(key="created_at",           label="Created",         type="date",   sortable=True),
    ColumnSchema(key="updated_at",           label="Updated",         type="date",   sortable=True),
]

STORY_DETAIL_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="slug",           label="Slug",           type="string"),
    ColumnSchema(key="title",          label="Title",          type="string"),
    ColumnSchema(key="latest_version", label="Latest Version", type="number"),
    ColumnSchema(key="versions",       label="Versions",       type="string"),
    ColumnSchema(key="created_at",     label="Created",        type="date"),
    ColumnSchema(key="updated_at",     label="Updated",        type="date"),
]

VERSION_CONTENT_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="story_id",                  label="Story",             type="string"),
    ColumnSchema(key="version",                   label="Version",          type="number"),
    ColumnSchema(key="title",                     label="Title",            type="string"),
    ColumnSchema(key="paragraphs",                label="Paragraphs",       type="string"),
    ColumnSchema(key="last_read_paragraph_index", label="Last Read At",     type="number"),
    ColumnSchema(key="created_at",                label="Created",          type="date"),
]

ANNOTATION_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="story_id",        label="Story",          type="string"),
    ColumnSchema(key="version",         label="Version",        type="number"),
    ColumnSchema(key="paragraph_index", label="Paragraph",      type="number"),
    ColumnSchema(key="char_start",      label="Start",          type="number"),
    ColumnSchema(key="char_end",        label="End",            type="number"),
    ColumnSchema(key="selected_text",   label="Selected Text",  type="string"),
    ColumnSchema(key="context_before",  label="Context Before", type="string"),
    ColumnSchema(key="context_after",   label="Context After",  type="string"),
    ColumnSchema(key="reaction",        label="Reaction",       type="enum"),
    ColumnSchema(key="created_at",      label="Created",        type="date"),
    ColumnSchema(key="updated_at",      label="Updated",        type="date"),
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _dataset_response(dataset: Dataset, status: int = 200) -> JSONResponse:
    return JSONResponse(status_code=status, content=dataset.model_dump(by_alias=True, mode="json"))


def _iso(value: Any) -> Any:
    return value.isoformat() if value is not None else None


def _annotation_row_to_dict(row: Any) -> dict[str, Any]:
    d = dict(row)
    d["id"]       = str(d["id"])
    d["story_id"] = str(d["story_id"])
    d["created_at"] = _iso(d.get("created_at"))
    d["updated_at"] = _iso(d.get("updated_at"))
    return d


def _annotations_dataset(rows: list[dict], total: int) -> Dataset:
    return Dataset(
        meta=DatasetMeta(object_type="annotation", label="Annotations", total=total, page=1, page_size=max(total, 1), row_actions=[]),
        **{"schema": ANNOTATION_SCHEMA},
        rows=rows,
    )


class _ApiErrorSignal(Exception):
    """Carries a pre-built ApiError JSONResponse up from a shared validation
    helper to the calling route, which returns it unchanged. Used instead of
    HTTPException so every error body stays the ApiError shape (R-CON-BP-04),
    not FastAPI's default detail shape.
    """

    def __init__(self, response: JSONResponse):
        self.response = response


def _resolve_version(conn: Any, story_id: str, version_segment: str, allow_latest: bool) -> int:
    """Shared by get_version_content (allow_latest=True) and
    list_annotations/export_annotations (allow_latest=False).

    Raises _ApiErrorSignal(NOT_FOUND) if story_id does not exist, or if an
    explicit version number does not exist for that story. Raises
    _ApiErrorSignal(VALIDATION_ERROR) if version_segment is neither an
    accepted literal nor a positive integer string.
    """
    with conn.cursor() as cur:
        cur.execute("select latest_version from storyreader.stories where id = %s", (story_id,))
        story = cur.fetchone()
    if not story:
        raise _ApiErrorSignal(api_error("NOT_FOUND", f"Story {story_id} not found", status=404))

    if allow_latest and version_segment == "latest":
        return story["latest_version"]

    if not re.fullmatch(r"[1-9][0-9]*", version_segment):
        allowed = "'latest' or a positive integer" if allow_latest else "a positive integer"
        raise _ApiErrorSignal(api_error("VALIDATION_ERROR", f"version must be {allowed}", status=400))

    version = int(version_segment)
    with conn.cursor() as cur:
        cur.execute(
            "select 1 from storyreader.story_versions where story_id = %s and version = %s",
            (story_id, version),
        )
        if not cur.fetchone():
            raise _ApiErrorSignal(
                api_error("NOT_FOUND", f"Version {version} not found for story {story_id}", status=404)
            )
    return version

# ── GET /stories ──────────────────────────────────────────────────────────────

@router.get("/stories", response_model=None)
def list_stories() -> JSONResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select s.id, s.slug, s.title, s.latest_version, s.created_at, s.updated_at,
                       (select count(*) from storyreader.annotations a
                        where a.story_id = s.id and a.version = s.latest_version) as marked_passage_count
                from storyreader.stories s
                order by s.updated_at desc
                """
            )
            rows = []
            for r in cur.fetchall():
                d = dict(r)
                d["id"] = str(d["id"])
                d["created_at"] = _iso(d.get("created_at"))
                d["updated_at"] = _iso(d.get("updated_at"))
                rows.append(d)

    dataset = Dataset(
        meta=DatasetMeta(object_type="story", label="Stories", total=len(rows), page=1, page_size=max(len(rows), 1), row_actions=[]),
        **{"schema": STORY_SCHEMA},
        rows=rows,
    )
    return _dataset_response(dataset)

# ── GET /last-read ──────────────────────────────────────────────────────────
# Own literal path (not nested under /stories/{story_id}) so there's no route-
# ordering ambiguity with that catch-all. Bespoke JSON (R-CON-BP-04 exempt,
# same rationale as export_annotations): a tiny control signal the app-root
# route uses to decide whether to redirect into the most recently active
# story, not a rendered Dataset. Always 200 — "nothing opened yet" is a valid
# empty state, not an error.

@router.get("/last-read", response_model=None)
def get_last_read() -> JSONResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id from storyreader.stories
                where last_opened_at is not null
                order by last_opened_at desc
                limit 1
                """
            )
            row = cur.fetchone()
    return JSONResponse(status_code=200, content={"story_id": str(row["id"]) if row else None})

# ── GET /stories/{story_id} ────────────────────────────────────────────────────

@router.get("/stories/{story_id}", response_model=None)
def get_story(story_id: str) -> JSONResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select id, slug, title, latest_version, created_at, updated_at from storyreader.stories where id = %s",
                (story_id,),
            )
            story = cur.fetchone()
        if not story:
            return api_error("NOT_FOUND", f"Story {story_id} not found", status=404)

        with conn.cursor() as cur:
            cur.execute(
                "select version from storyreader.story_versions where story_id = %s order by version asc",
                (story_id,),
            )
            versions = [r["version"] for r in cur.fetchall()]

    row = dict(story)
    row["id"] = str(row["id"])
    row["created_at"] = _iso(row.get("created_at"))
    row["updated_at"] = _iso(row.get("updated_at"))
    row["versions"] = versions

    dataset = Dataset(
        meta=DatasetMeta(object_type="story", label="Story", total=1, page=1, page_size=1, row_actions=[]),
        **{"schema": STORY_DETAIL_SCHEMA},
        rows=[row],
    )
    return _dataset_response(dataset)

# ── GET /stories/{story_id}/versions/{version} ────────────────────────────────

@router.get("/stories/{story_id}/versions/{version}", response_model=None)
def get_version_content(story_id: str, version: str) -> JSONResponse:
    with get_db() as conn:
        try:
            resolved_version = _resolve_version(conn, story_id, version, allow_latest=True)
        except _ApiErrorSignal as e:
            return e.response

        with conn.cursor() as cur:
            cur.execute("select title from storyreader.stories where id = %s", (story_id,))
            story = cur.fetchone()

        with conn.cursor() as cur:
            cur.execute(
                """
                select id, body_markdown, last_read_paragraph_index, created_at
                from storyreader.story_versions where story_id = %s and version = %s
                """,
                (story_id, resolved_version),
            )
            version_row = cur.fetchone()
        if not version_row:
            return api_error("NOT_FOUND", f"Version {resolved_version} not found for story {story_id}", status=404)

    paragraphs = split_paragraphs(version_row["body_markdown"])
    paragraphs_payload = [{"paragraph_index": i, "text": p} for i, p in enumerate(paragraphs)]

    row = {
        "id":                         str(version_row["id"]),
        "story_id":                   story_id,
        "version":                    resolved_version,
        "title":                      story["title"],
        "paragraphs":                 paragraphs_payload,
        "last_read_paragraph_index":  version_row["last_read_paragraph_index"],
        "created_at":                 _iso(version_row["created_at"]),
    }

    dataset = Dataset(
        meta=DatasetMeta(object_type="story_version", label="Story Version", total=1, page=1, page_size=1, row_actions=[]),
        **{"schema": VERSION_CONTENT_SCHEMA},
        rows=[row],
    )
    return _dataset_response(dataset)

# ── GET /stories/{story_id}/versions/{version}/annotations ────────────────────

@router.get("/stories/{story_id}/versions/{version}/annotations", response_model=None)
def list_annotations(story_id: str, version: str) -> JSONResponse:
    with get_db() as conn:
        try:
            resolved_version = _resolve_version(conn, story_id, version, allow_latest=False)
        except _ApiErrorSignal as e:
            return e.response

        with conn.cursor() as cur:
            cur.execute(
                """
                select * from storyreader.annotations
                where story_id = %s and version = %s
                order by paragraph_index asc, char_start asc
                """,
                (story_id, resolved_version),
            )
            rows = [_annotation_row_to_dict(r) for r in cur.fetchall()]

    return _dataset_response(_annotations_dataset(rows, total=len(rows)))

# ── PUT /stories/{story_id}/versions/{version}/position ───────────────────────

@router.put("/stories/{story_id}/versions/{version}/position", response_model=None)
def save_position(story_id: str, version: str, body: PositionUpdate) -> Response:
    with get_db() as conn:
        try:
            resolved_version = _resolve_version(conn, story_id, version, allow_latest=False)
        except _ApiErrorSignal as e:
            return e.response

        with conn.cursor() as cur:
            cur.execute(
                "select body_markdown from storyreader.story_versions where story_id = %s and version = %s",
                (story_id, resolved_version),
            )
            version_row = cur.fetchone()

        paragraphs = split_paragraphs(version_row["body_markdown"])
        if body.paragraph_index < 0 or body.paragraph_index >= len(paragraphs):
            return api_error(
                "VALIDATION_ERROR",
                f"paragraph_index out of range for this version (0..{len(paragraphs) - 1})",
                status=400,
            )

        with conn.cursor() as cur:
            cur.execute(
                """
                update storyreader.story_versions
                set last_read_paragraph_index = %s
                where story_id = %s and version = %s
                """,
                (body.paragraph_index, story_id, resolved_version),
            )
            cur.execute(
                "update storyreader.stories set last_opened_at = now() where id = %s",
                (story_id,),
            )
        conn.commit()

    return Response(status_code=204)

# ── POST /annotations ──────────────────────────────────────────────────────────

@router.post("/annotations", response_model=None)
def create_or_update_annotation(body: AnnotationCreate) -> JSONResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select id from storyreader.stories where id = %s", (body.story_id,))
            if not cur.fetchone():
                return api_error("NOT_FOUND", f"Story {body.story_id} not found", status=404)

        with conn.cursor() as cur:
            cur.execute(
                "select body_markdown from storyreader.story_versions where story_id = %s and version = %s",
                (body.story_id, body.version),
            )
            version_row = cur.fetchone()
        if not version_row:
            return api_error("NOT_FOUND", f"Version {body.version} not found for story {body.story_id}", status=404)

        if body.reaction not in VALID_REACTIONS:
            return api_error(
                "VALIDATION_ERROR",
                f"reaction must be one of: {', '.join(sorted(VALID_REACTIONS))}",
                status=400,
            )
        if body.char_start < 0:
            return api_error("VALIDATION_ERROR", "char_start must be >= 0", status=400)
        if body.char_end <= body.char_start:
            return api_error("VALIDATION_ERROR", "char_end must be > char_start", status=400)

        paragraphs = split_paragraphs(version_row["body_markdown"])
        if body.paragraph_index < 0 or body.paragraph_index >= len(paragraphs):
            return api_error(
                "VALIDATION_ERROR",
                f"paragraph_index out of range for this version (0..{len(paragraphs) - 1})",
                status=400,
            )
        paragraph_text = paragraphs[body.paragraph_index]

        if body.char_end > len(paragraph_text):
            return api_error("VALIDATION_ERROR", "char_end exceeds the length of this paragraph's text", status=400)

        if body.selected_text != paragraph_text[body.char_start:body.char_end]:
            return api_error(
                "VALIDATION_ERROR",
                "selected_text does not match the paragraph substring at the given offsets",
                status=400,
            )

        context_before = (body.context_before or "")[:_MAX_CONTEXT_LEN]
        context_after  = (body.context_after or "")[:_MAX_CONTEXT_LEN]

        with conn.cursor() as cur:
            cur.execute(
                """
                insert into storyreader.annotations
                    (story_id, version, paragraph_index, char_start, char_end,
                     selected_text, context_before, context_after, reaction)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (story_id, version, paragraph_index, char_start, char_end)
                do update set
                    reaction       = excluded.reaction,
                    context_before = excluded.context_before,
                    context_after  = excluded.context_after,
                    selected_text  = excluded.selected_text,
                    updated_at     = now()
                returning *, (xmax = 0) as was_inserted
                """,
                (
                    body.story_id, body.version, body.paragraph_index, body.char_start, body.char_end,
                    body.selected_text, context_before, context_after, body.reaction,
                ),
            )
            row = dict(cur.fetchone())
        was_inserted = row.pop("was_inserted")
        conn.commit()

    result = _annotation_row_to_dict(row)
    return JSONResponse(status_code=201 if was_inserted else 200, content=result)

# ── DELETE /annotations/{annotation_id} ────────────────────────────────────────

@router.delete("/annotations/{annotation_id}", response_model=None)
def delete_annotation(annotation_id: str) -> Response:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from storyreader.annotations where id = %s returning id", (annotation_id,))
            deleted = cur.fetchone()
        if not deleted:
            return api_error("NOT_FOUND", f"Annotation {annotation_id} not found", status=404)
        conn.commit()

    return Response(status_code=204)

# ── GET /stories/{story_id}/versions/{version}/annotations/export ─────────────

@router.get("/stories/{story_id}/versions/{version}/annotations/export", response_model=None)
def export_annotations(story_id: str, version: str) -> JSONResponse:
    with get_db() as conn:
        try:
            resolved_version = _resolve_version(conn, story_id, version, allow_latest=False)
        except _ApiErrorSignal as e:
            return e.response

        with conn.cursor() as cur:
            cur.execute("select slug, title from storyreader.stories where id = %s", (story_id,))
            story = cur.fetchone()

        with conn.cursor() as cur:
            cur.execute(
                """
                select paragraph_index, selected_text, context_before, context_after,
                       reaction, created_at, updated_at
                from storyreader.annotations
                where story_id = %s and version = %s
                order by paragraph_index asc, char_start asc
                """,
                (story_id, resolved_version),
            )
            annotations = []
            for r in cur.fetchall():
                d = dict(r)
                d["created_at"] = _iso(d.get("created_at"))
                d["updated_at"] = _iso(d.get("updated_at"))
                annotations.append(d)

    payload = {
        "slug":             story["slug"],
        "title":            story["title"],
        "version":          resolved_version,
        "annotation_count": len(annotations),
        "annotations":      annotations,
    }
    return JSONResponse(status_code=200, content=payload)
