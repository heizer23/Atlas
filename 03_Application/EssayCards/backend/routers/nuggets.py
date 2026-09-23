"""
GET /nuggets, GET /nuggets/{id}, POST /nuggets/upsert,
GET /nuggets/{id}/flashcards, GET /nuggets/{id}/sections,
GET /nuggets/authoring-package, GET /nuggets/{id}/generate-flashcards-package.

Nuggets (Sprint09_Nuggets — see CLAUDE.md "Nuggets") are standalone,
independently-learnable concepts, NOT owned by one essay or section. Create/
update is always upsert-by-nugget_key (backend/ingest.py's SLUG_LIKE_RE
convention) — see POST /upsert's docstring.

GET '' (list), GET '/{id}' (detail), GET '/{id}/flashcards', and
GET '/{id}/sections' are read endpoints and return Dataset per R-CON-BP-04.

GET '/authoring-package' and GET '/{id}/generate-flashcards-package' are
bespoke-JSON, Dataset-exempt read endpoints (R-CON-BP-04 exemption, same
rationale class as GET /essays/{essay_id}/examination-package and
GET /flashcards/{flashcard_id}/exploration-package): self-contained
interchange artifacts copied to the clipboard for an external LLM, not
rendered by a Dataset-consuming UI component.

POST /upsert is a mutation endpoint (R-CON-BP-04 exempt). It reads the raw
Starlette Request body — not a Pydantic body model — same VALIDATION_ERROR
precedent as POST /essays/ingest and POST /flashcards/upsert.

Registration order matters: '/authoring-package' is a single literal path
segment, exactly like the parameterised '/{id}' — FastAPI/Starlette matches
routes in registration order, so '/authoring-package' MUST be registered
BEFORE GET '/{id}', or a request to /nuggets/authoring-package would instead
match '/{id}' with id='authoring-package'. '/upsert' (POST, different method)
has no such collision risk but is conventionally also registered before
'/{id}' for readability — same precedent already documented in
backend/routers/flashcards.py for '/due'/'/stats'/'/upsert' before
'/{flashcard_id}/...'.
"""

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.database import get_db
from backend.ingest import SLUG_LIKE_RE, extract_nugget_keys
from platform_contracts import ColumnSchema, Dataset, DatasetMeta
from platform_errorhandling import api_error

router = APIRouter(prefix="/nuggets", tags=["nuggets"])

NUGGET_LIST_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="nugget_key", label="Key",     type="string", sortable=True,  filterable=True),
    ColumnSchema(key="title",      label="Title",    type="string", sortable=True,  filterable=True),
    ColumnSchema(key="created_at", label="Created",  type="date",   sortable=True,  filterable=False),
    ColumnSchema(key="updated_at", label="Updated",  type="date",   sortable=True,  filterable=False),
]

NUGGET_DETAIL_SCHEMA: list[ColumnSchema] = NUGGET_LIST_SCHEMA + [
    ColumnSchema(key="body_markdown", label="Body", type="string", sortable=False, filterable=False, detail_visible=True),
]

NUGGET_FLASHCARDS_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="card_key",   label="Card id",  type="string", sortable=False, filterable=False),
    ColumnSchema(key="question",   label="Question", type="string", sortable=False, filterable=False, detail_visible=True),
    ColumnSchema(key="answer",     label="Answer",   type="string", sortable=False, filterable=False, detail_visible=True),
    ColumnSchema(key="level",      label="Level",    type="number", sortable=True,  filterable=True),
    ColumnSchema(key="essay_id",   label="Essay",    type="string", sortable=False, filterable=True),
    ColumnSchema(key="section_id", label="Section",  type="string", sortable=False, filterable=True),
]

NUGGET_SECTIONS_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="heading",     label="Section",     type="string", sortable=False, filterable=False),
    ColumnSchema(key="anchor_slug", label="Anchor",      type="string", sortable=False, filterable=False),
    ColumnSchema(key="order_index", label="Order",       type="number", sortable=True,  filterable=False),
    ColumnSchema(key="essay_title", label="Essay",       type="string", sortable=True,  filterable=True),
    ColumnSchema(key="essay_slug",  label="Essay slug",  type="string", sortable=False, filterable=False),
]


def _row_to_dict(row: Any) -> dict[str, Any]:
    d = dict(row)
    d["id"] = str(d["id"])
    for k in ("created_at", "updated_at"):
        if d.get(k):
            d[k] = d[k].isoformat()
    return d


def _dataset_response(dataset: Dataset) -> JSONResponse:
    return JSONResponse(content=dataset.model_dump(by_alias=True, mode="json"))


def _resolve_essay_and_section(
    cur: Any, essay_id: str, section_id: str
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, JSONResponse | None]:
    """
    Given cur, essay_id, section_id: returns (essay_row, section_row, None) on
    success, or (None, None, ApiError NOT_FOUND) if essay_id does not exist or
    section_id does not belong to it. Shared by GET /authoring-package and
    GET /{id}/generate-flashcards-package.
    """
    cur.execute(
        "select id, slug, title, main_spine_markdown from essaycards.essays where id = %s",
        (essay_id,),
    )
    essay_row = cur.fetchone()
    if not essay_row:
        return None, None, api_error("NOT_FOUND", f"Essay {essay_id} not found", status=404)

    cur.execute(
        "select id, essay_id, anchor_slug, heading, body_markdown "
        "from essaycards.essay_sections where id = %s",
        (section_id,),
    )
    section_row = cur.fetchone()
    if not section_row or str(section_row["essay_id"]) != str(essay_id):
        return None, None, api_error(
            "NOT_FOUND", f"Section {section_id} not found in essay {essay_id}", status=404
        )

    return essay_row, section_row, None


# ── GET '' — list ─────────────────────────────────────────────────────────────

@router.get("", response_model=None)
def list_nuggets() -> JSONResponse:
    """
    No parameters. Ordering (R-CON-AL-01): title asc, nugget_key asc (stable
    tiebreak). Empty result is valid. Row shape: id, nugget_key, title,
    created_at, updated_at — deliberately no body_markdown (kept out of the
    list view; see GET /{id} for full detail).
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select id, nugget_key, title, created_at, updated_at "
                "from essaycards.nuggets order by title asc, nugget_key asc"
            )
            rows = [_row_to_dict(r) for r in cur.fetchall()]

    dataset = Dataset(
        meta=DatasetMeta(
            object_type="nugget",
            label="Nuggets",
            total=len(rows),
            page=1,
            page_size=max(len(rows), 1),
            row_actions=[],
        ),
        **{"schema": NUGGET_LIST_SCHEMA},
        rows=rows,
    )
    return _dataset_response(dataset)


# ── POST /upsert ──────────────────────────────────────────────────────────────
#
# Registered before GET '/{id}' — different HTTP method, no collision risk,
# but grouped here for readability (see module docstring).

@router.post("/upsert", response_model=None)
async def upsert_nugget(request: Request) -> JSONResponse:
    """
    Create or update exactly ONE nugget, upsert-by-nugget_key. The key is
    always the WHERE, never a SET column, so a title/body edit can never
    change the key — there is no key-rename path this sprint. Body:
    {nugget_key, title, body_markdown?}. Reads the raw Starlette Request
    body — not a Pydantic body model — same VALIDATION_ERROR precedent as
    POST /essays/ingest and POST /flashcards/upsert.

    Mutation endpoint per R-CON-BP-04: returns a typed record
    {id, nugget_key, title, created} on success (200), ApiError
    VALIDATION_ERROR (400) on any invalid shape. No row is written on error.
    """
    try:
        body = await request.json()
    except Exception:
        return api_error("VALIDATION_ERROR", "Request body must be valid JSON")

    if not isinstance(body, dict):
        return api_error("VALIDATION_ERROR", "Request body must be a JSON object")

    nugget_key = body.get("nugget_key")
    if not isinstance(nugget_key, str) or not nugget_key.strip():
        return api_error("VALIDATION_ERROR", "nugget_key is required and must be a non-empty string")
    nugget_key = nugget_key.strip()
    if not SLUG_LIKE_RE.match(nugget_key):
        return api_error("VALIDATION_ERROR", f"nugget_key '{nugget_key}' must match ^[a-zA-Z0-9_-]+$")

    title = body.get("title")
    if not isinstance(title, str) or not title.strip():
        return api_error("VALIDATION_ERROR", "title is required and must be a non-empty string")
    title = title.strip()

    body_markdown = body.get("body_markdown", "")
    if not isinstance(body_markdown, str):
        return api_error("VALIDATION_ERROR", "body_markdown, if present, must be a string")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into essaycards.nuggets (nugget_key, title, body_markdown)
                values (%s, %s, %s)
                on conflict (nugget_key) do update
                    set title         = excluded.title,
                        body_markdown = excluded.body_markdown,
                        updated_at    = now()
                returning id, created_at, (xmax = 0) as was_inserted
                """,
                (nugget_key, title, body_markdown),
            )
            row = cur.fetchone()
        conn.commit()

    return JSONResponse(content={
        "id": str(row["id"]),
        "nugget_key": nugget_key,
        "title": title,
        "created": row["was_inserted"],
    })


# ── GET /authoring-package — MUST be registered before GET /{id} ────────────

@router.get("/authoring-package", response_model=None)
def nugget_authoring_package(essay_id: str, section_id: str, nugget_id: str | None = None) -> JSONResponse:
    """
    Self-contained JSON context for drafting/revising ONE nugget via an
    external LLM: current essay title + main spine, current section + its
    spine, the target nugget (existing body if editing, null if drafting a
    new one — nugget_id omitted), and its prerequisite/connected nuggets
    (resolved via extract_nugget_keys() over the target nugget's own
    body_markdown). Applies via POST /nuggets/upsert. Read-only.

    essay_id and section_id are required query params; section_id must
    belong to essay_id. nugget_id is optional. 404 ApiError if essay_id,
    section_id (under essay_id), or a supplied nugget_id does not resolve.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            essay_row, section_row, error = _resolve_essay_and_section(cur, essay_id, section_id)
            if error is not None:
                return error

            nugget: dict[str, Any] | None = None
            connected_nuggets: list[dict[str, str]] = []
            if nugget_id is not None:
                cur.execute(
                    "select id, nugget_key, title, body_markdown from essaycards.nuggets where id = %s",
                    (nugget_id,),
                )
                nugget_row = cur.fetchone()
                if not nugget_row:
                    return api_error("NOT_FOUND", f"Nugget {nugget_id} not found", status=404)
                nugget = {
                    "id": str(nugget_row["id"]),
                    "nugget_key": nugget_row["nugget_key"],
                    "title": nugget_row["title"],
                    "body_markdown": nugget_row["body_markdown"],
                }
                keys = extract_nugget_keys(nugget_row["body_markdown"])
                if keys:
                    cur.execute(
                        "select nugget_key, title from essaycards.nuggets "
                        "where nugget_key = any(%s) order by title asc",
                        (list(keys),),
                    )
                    connected_nuggets = [
                        {"nugget_key": r["nugget_key"], "title": r["title"]} for r in cur.fetchall()
                    ]

    package = {
        "export_version": 1,
        "essay": {
            "slug": essay_row["slug"],
            "title": essay_row["title"],
            "main_spine_markdown": essay_row["main_spine_markdown"],
        },
        "section": {
            "id": str(section_row["id"]),
            "anchor_slug": section_row["anchor_slug"],
            "heading": section_row["heading"],
            "body_markdown": section_row["body_markdown"],
        },
        "nugget": nugget,
        "connected_nuggets": connected_nuggets,
    }
    return JSONResponse(content=package)


# ── GET /{id} — detail ────────────────────────────────────────────────────────

@router.get("/{id}", response_model=None)
def get_nugget(id: str) -> JSONResponse:
    """Single nugget detail including body_markdown. 404 ApiError if id does not exist."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select id, nugget_key, title, body_markdown, created_at, updated_at "
                "from essaycards.nuggets where id = %s",
                (id,),
            )
            row = cur.fetchone()
            if not row:
                return api_error("NOT_FOUND", f"Nugget {id} not found", status=404)

    dataset = Dataset(
        meta=DatasetMeta(
            object_type="nugget",
            label="Nugget",
            total=1,
            page=1,
            page_size=1,
            row_actions=[],
        ),
        **{"schema": NUGGET_DETAIL_SCHEMA},
        rows=[_row_to_dict(row)],
    )
    return _dataset_response(dataset)


# ── GET /{id}/flashcards ──────────────────────────────────────────────────────

@router.get("/{id}/flashcards", response_model=None)
def list_nugget_flashcards(id: str) -> JSONResponse:
    """
    Flat, read-only list of flashcards currently pointing at this nugget.
    Ordering (R-CON-AL-01): created_at asc, id asc. No parameters. 404
    ApiError if the nugget id does not exist. Empty result is valid.

    Deliberately NOT due-queue-shaped: no scheduling fields (no next_due_at,
    is_new, is_recent, scheduled_interval_seconds) — reviewing a
    nugget-linked card for real spaced repetition still goes through the
    existing essay/section-scoped focus session the card already belongs to.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select 1 from essaycards.nuggets where id = %s", (id,))
            if not cur.fetchone():
                return api_error("NOT_FOUND", f"Nugget {id} not found", status=404)

            cur.execute(
                """
                select id, card_key, question, answer, level, essay_id, section_id
                from essaycards.flashcards
                where nugget_id = %s
                order by created_at asc, id asc
                """,
                (id,),
            )
            rows = []
            for r in cur.fetchall():
                d = dict(r)
                d["id"] = str(d["id"])
                d["essay_id"] = str(d["essay_id"])
                d["section_id"] = str(d["section_id"])
                rows.append(d)

    dataset = Dataset(
        meta=DatasetMeta(
            object_type="flashcard",
            label="Nugget Flashcards",
            total=len(rows),
            page=1,
            page_size=max(len(rows), 1),
            row_actions=[],
        ),
        **{"schema": NUGGET_FLASHCARDS_SCHEMA},
        rows=rows,
    )
    return _dataset_response(dataset)


# ── GET /{id}/sections ─────────────────────────────────────────────────────────

@router.get("/{id}/sections", response_model=None)
def list_nugget_sections(id: str) -> JSONResponse:
    """
    Sections (with essay context) currently referencing this nugget, for the
    nugget view's "referenced by" list. Ordering (R-CON-AL-01): essay title
    asc, section order_index asc. No parameters. 404 ApiError if the nugget
    id does not exist. Empty result is valid (referenced nowhere).
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select 1 from essaycards.nuggets where id = %s", (id,))
            if not cur.fetchone():
                return api_error("NOT_FOUND", f"Nugget {id} not found", status=404)

            cur.execute(
                """
                select s.id as section_id, s.anchor_slug, s.heading, s.order_index,
                       s.essay_id, e.title as essay_title, e.slug as essay_slug
                from essaycards.section_nuggets sn
                join essaycards.essay_sections s on s.id = sn.section_id
                join essaycards.essays e on e.id = s.essay_id
                where sn.nugget_id = %s
                order by e.title asc, s.order_index asc
                """,
                (id,),
            )
            rows = []
            for r in cur.fetchall():
                d = dict(r)
                d["id"] = str(d["section_id"])
                d["section_id"] = str(d["section_id"])
                d["essay_id"] = str(d["essay_id"])
                rows.append(d)

    dataset = Dataset(
        meta=DatasetMeta(
            object_type="section",
            label="Referenced By",
            total=len(rows),
            page=1,
            page_size=max(len(rows), 1),
            row_actions=[],
        ),
        **{"schema": NUGGET_SECTIONS_SCHEMA},
        rows=rows,
    )
    return _dataset_response(dataset)


# ── GET /{id}/generate-flashcards-package ────────────────────────────────────

@router.get("/{id}/generate-flashcards-package", response_model=None)
def generate_flashcards_package(id: str, essay_id: str, section_id: str) -> JSONResponse:
    """
    Self-contained JSON context (the nugget's own content plus its existing
    flashcards) for generating new flashcards from ONE nugget via an external
    LLM. Reimports by looping POST /flashcards/upsert once per returned card
    (no new bulk/atomic endpoint — see 10_architecture.json risks). Read-only.

    essay_id/section_id anchor the cards to be created; section_id must
    belong to essay_id. 404 ApiError if the nugget id, essay_id, or
    section_id (under essay_id) does not resolve.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select id, nugget_key, title, body_markdown from essaycards.nuggets where id = %s",
                (id,),
            )
            nugget_row = cur.fetchone()
            if not nugget_row:
                return api_error("NOT_FOUND", f"Nugget {id} not found", status=404)

            essay_row, section_row, error = _resolve_essay_and_section(cur, essay_id, section_id)
            if error is not None:
                return error

            cur.execute(
                """
                select id, card_key, question, answer, level
                from essaycards.flashcards
                where nugget_id = %s
                order by created_at asc, id asc
                """,
                (id,),
            )
            existing_flashcards = []
            for r in cur.fetchall():
                d = dict(r)
                d["id"] = str(d["id"])
                existing_flashcards.append(d)

    package = {
        "export_version": 1,
        "nugget": {
            "nugget_key": nugget_row["nugget_key"],
            "title": nugget_row["title"],
            "body_markdown": nugget_row["body_markdown"],
        },
        "existing_flashcards": existing_flashcards,
        "context": {
            "essay_slug": essay_row["slug"],
            "section_id": str(section_row["id"]),
        },
    }
    return JSONResponse(content=package)
