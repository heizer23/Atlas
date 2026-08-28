"""
GET /essays, GET /essays/{essay_id}, and POST /essays/ingest.

GET /essays and GET /essays/{essay_id} are read endpoints and return Dataset
per R-CON-BP-04.

POST /ingest is a mutation endpoint (R-CON-BP-04 exempt from the Dataset
requirement). It reads the raw Starlette Request body — not a Pydantic body
model — so every invalid shape (unparsable JSON, non-object body, missing or
malformed field, in-payload duplicate anchor_slug/id, a card id colliding
with an existing card in a different section) is caught by application code
and returned as ApiError with error.code=VALIDATION_ERROR (400). FastAPI's
default RequestValidationError 422 shape must never be produced by this
endpoint — same precedent as POST /flashcards/{id}/review (see
backend/routers/flashcards.py::_parse_review_grade).

Validation is all-or-nothing: the whole payload is structurally and
semantically validated (§_validate_ingest_body) before any database access.
The one DB-dependent check — a card id colliding with an existing card in a
different section of the same essay (§_check_card_section_collisions) — also
runs, and must pass, before backend.ingest.upsert_document is ever called.
This is an intentional asymmetry versus the markdown CLI path, which silently
allows a re-ingested card to move to a different section — see
Sprint02_JsonIngestion/10_architecture.json §risks.
"""

import re
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.database import get_db
from backend.ingest import upsert_document
from platform_contracts import ColumnSchema, Dataset, DatasetMeta
from platform_errorhandling import api_error

router = APIRouter(prefix="/essays", tags=["essays"])

_SLUG_LIKE_RE = re.compile(r"^[a-zA-Z0-9_-]+$")

ESSAY_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="title", label="Title", type="string", sortable=True,  filterable=True),
    ColumnSchema(key="slug",  label="Slug",  type="string", sortable=False, filterable=False),
]


def _row_to_dict(row: Any) -> dict[str, Any]:
    d = dict(row)
    d["id"] = str(d["id"])
    if d.get("created_at"):
        d["created_at"] = d["created_at"].isoformat()
    if d.get("updated_at"):
        d["updated_at"] = d["updated_at"].isoformat()
    return d


def _section_row_to_dict(row: Any) -> dict[str, Any]:
    d = dict(row)
    d["id"] = str(d["id"])
    if d.get("created_at"):
        d["created_at"] = d["created_at"].isoformat()
    if d.get("updated_at"):
        d["updated_at"] = d["updated_at"].isoformat()
    return d


def _dataset_response(dataset: Dataset) -> JSONResponse:
    return JSONResponse(content=dataset.model_dump(by_alias=True, mode="json"))


@router.get("", response_model=None)
def list_essays() -> JSONResponse:
    """No parameters. Ordered by created_at asc. Empty result is valid."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select id, title, slug, created_at, updated_at "
                "from essaycards.essays order by created_at asc"
            )
            rows = [_row_to_dict(r) for r in cur.fetchall()]

    dataset = Dataset(
        meta=DatasetMeta(
            object_type="essay",
            label="Essays",
            total=len(rows),
            page=1,
            page_size=max(len(rows), 1),
            row_actions=[],
        ),
        **{"schema": ESSAY_SCHEMA},
        rows=rows,
    )
    return _dataset_response(dataset)


@router.get("/{essay_id}", response_model=None)
def get_essay(essay_id: str) -> JSONResponse:
    """Single essay with its ordered sections embedded on the returned row.

    404 ApiError if essay_id does not exist. An essay with zero sections is
    valid and returns sections: [].
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select id, title, slug, created_at, updated_at "
                "from essaycards.essays where id = %s",
                (essay_id,),
            )
            essay_row = cur.fetchone()
            if not essay_row:
                return api_error("NOT_FOUND", f"Essay {essay_id} not found", status=404)
            row = _row_to_dict(essay_row)

            cur.execute(
                """
                select id, heading, anchor_slug, order_index, body_markdown, created_at, updated_at
                from essaycards.essay_sections
                where essay_id = %s
                order by order_index asc
                """,
                (essay_id,),
            )
            row["sections"] = [_section_row_to_dict(r) for r in cur.fetchall()]

    dataset = Dataset(
        meta=DatasetMeta(
            object_type="essay",
            label="Essay",
            total=1,
            page=1,
            page_size=1,
            row_actions=[],
        ),
        **{"schema": ESSAY_SCHEMA},
        rows=[row],
    )
    return _dataset_response(dataset)


# ── POST /ingest ──────────────────────────────────────────────────────────────
#
# NOTE ON STRING NORMALIZATION (design review §Recommended Improvements 1):
# title, slug, heading, and anchor_slug/card id are stripped of surrounding
# whitespace before validation/storage — matching the markdown CLI path,
# where front-matter title/slug are `.strip()`ped and anchor_slug/card_key
# have no way to carry surrounding whitespace (extracted from a regex
# character class / explicitly `.strip()`ped). body_markdown, q, and a are
# stored verbatim (not stripped) — matching the markdown path, which never
# strips question/answer text and only strips body_markdown as a side effect
# of fenced-block extraction, not as a general text-normalization rule.


def _validate_ingest_body(body: Any) -> tuple[dict[str, Any] | None, JSONResponse | None]:
    """
    Full structural + semantic validation of a JSON ingest payload
    (10_architecture.json internal_flow step 8). Returns (doc, None) on
    success, or (None, JSONResponse) with an ApiError VALIDATION_ERROR on the
    first violation found. Never touches the database.
    """
    if not isinstance(body, dict):
        return None, api_error("VALIDATION_ERROR", "Request body must be a JSON object")

    title = body.get("title")
    if not isinstance(title, str) or not title.strip():
        return None, api_error("VALIDATION_ERROR", "title is required and must be a non-empty string")
    title = title.strip()

    slug = body.get("slug")
    if not isinstance(slug, str) or not slug.strip():
        return None, api_error("VALIDATION_ERROR", "slug is required and must be a non-empty string")
    slug = slug.strip()
    if not _SLUG_LIKE_RE.match(slug):
        return None, api_error("VALIDATION_ERROR", f"slug '{slug}' must match ^[a-zA-Z0-9_-]+$")

    sections_raw = body.get("sections")
    if not isinstance(sections_raw, list) or not sections_raw:
        return None, api_error("VALIDATION_ERROR", "sections is required and must be a non-empty list")

    sections: list[dict[str, Any]] = []
    for s_idx, section_raw in enumerate(sections_raw):
        if not isinstance(section_raw, dict):
            return None, api_error("VALIDATION_ERROR", f"sections[{s_idx}] must be an object")

        heading = section_raw.get("heading")
        if not isinstance(heading, str) or not heading.strip():
            return None, api_error(
                "VALIDATION_ERROR", f"sections[{s_idx}].heading is required and must be a non-empty string"
            )
        heading = heading.strip()

        anchor_slug = section_raw.get("anchor_slug")
        if not isinstance(anchor_slug, str) or not anchor_slug.strip():
            return None, api_error(
                "VALIDATION_ERROR", f"sections[{s_idx}].anchor_slug is required and must be a non-empty string"
            )
        anchor_slug = anchor_slug.strip()
        if not _SLUG_LIKE_RE.match(anchor_slug):
            return None, api_error(
                "VALIDATION_ERROR", f"sections[{s_idx}].anchor_slug '{anchor_slug}' must match ^[a-zA-Z0-9_-]+$"
            )

        body_markdown = section_raw.get("body_markdown")
        if not isinstance(body_markdown, str):
            return None, api_error(
                "VALIDATION_ERROR", f"sections[{s_idx}].body_markdown is required and must be a string"
            )

        cards_raw = section_raw.get("cards")
        if not isinstance(cards_raw, list):
            return None, api_error("VALIDATION_ERROR", f"sections[{s_idx}].cards must be a list")

        cards: list[dict[str, str]] = []
        for c_idx, card_raw in enumerate(cards_raw):
            if not isinstance(card_raw, dict):
                return None, api_error("VALIDATION_ERROR", f"sections[{s_idx}].cards[{c_idx}] must be an object")

            card_id = card_raw.get("id")
            if not isinstance(card_id, str) or not card_id.strip():
                return None, api_error(
                    "VALIDATION_ERROR", f"sections[{s_idx}].cards[{c_idx}].id is required and must be a non-empty string"
                )
            card_id = card_id.strip()
            if not _SLUG_LIKE_RE.match(card_id):
                return None, api_error(
                    "VALIDATION_ERROR", f"sections[{s_idx}].cards[{c_idx}].id '{card_id}' must match ^[a-zA-Z0-9_-]+$"
                )

            q = card_raw.get("q")
            if not isinstance(q, str) or not q.strip():
                return None, api_error(
                    "VALIDATION_ERROR", f"sections[{s_idx}].cards[{c_idx}].q is required and must be a non-empty string"
                )

            a = card_raw.get("a")
            if not isinstance(a, str) or not a.strip():
                return None, api_error(
                    "VALIDATION_ERROR", f"sections[{s_idx}].cards[{c_idx}].a is required and must be a non-empty string"
                )

            cards.append({"card_key": card_id, "question": q, "answer": a})

        sections.append({
            "heading": heading,
            "anchor_slug": anchor_slug,
            "order_index": s_idx,
            "body_markdown": body_markdown,
            "cards": cards,
        })

    seen_anchors: set[str] = set()
    for section in sections:
        if section["anchor_slug"] in seen_anchors:
            return None, api_error(
                "VALIDATION_ERROR", f"duplicate anchor_slug '{section['anchor_slug']}' in payload"
            )
        seen_anchors.add(section["anchor_slug"])

    seen_card_keys: set[str] = set()
    for section in sections:
        for card in section["cards"]:
            if card["card_key"] in seen_card_keys:
                return None, api_error(
                    "VALIDATION_ERROR", f"duplicate card id '{card['card_key']}' in payload"
                )
            seen_card_keys.add(card["card_key"])

    doc = {"title": title, "slug": slug, "sections": sections}
    return doc, None


def _check_card_section_collisions(cur: Any, existing_essay_id: str, doc: dict[str, Any]) -> JSONResponse | None:
    """
    Given the connection cursor, an existing essay's id, and the incoming doc,
    rejects the request if any incoming card id already exists in the DB for
    this essay under a different section than the one it appears under in the
    payload. Returns None if no collision is found. Must be called, and must
    return None, before backend.ingest.upsert_document is invoked.
    """
    incoming_anchor_by_key: dict[str, str] = {
        card["card_key"]: section["anchor_slug"]
        for section in doc["sections"]
        for card in section["cards"]
    }
    if not incoming_anchor_by_key:
        return None

    cur.execute(
        """
        select f.card_key, s.anchor_slug
        from essaycards.flashcards f
        join essaycards.essay_sections s on s.id = f.section_id
        where f.essay_id = %s and f.card_key = any(%s)
        """,
        (existing_essay_id, list(incoming_anchor_by_key.keys())),
    )
    for row in cur.fetchall():
        existing_anchor = row["anchor_slug"]
        incoming_anchor = incoming_anchor_by_key[row["card_key"]]
        if existing_anchor != incoming_anchor:
            return api_error(
                "VALIDATION_ERROR",
                f"card id '{row['card_key']}' already exists under section '{existing_anchor}' "
                f"and cannot be moved to section '{incoming_anchor}' via JSON ingest",
            )
    return None


@router.post("/ingest", response_model=None)
async def ingest_essay(request: Request) -> JSONResponse:
    """
    Create a new essay (if slug is new) or upsert sections/flashcards onto an
    existing essay (if slug already exists) from a JSON payload. Shares the
    same upsert core (backend.ingest.upsert_document) as the markdown CLI path.

    Mutation endpoint per R-CON-BP-04: returns a typed record on success (200),
    ApiError on any validation failure (400).
    """
    try:
        body = await request.json()
    except Exception:
        return api_error("VALIDATION_ERROR", "Request body must be valid JSON")

    doc, error = _validate_ingest_body(body)
    if error is not None:
        return error

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select id from essaycards.essays where slug = %s", (doc["slug"],))
            existing = cur.fetchone()
            if existing:
                collision_error = _check_card_section_collisions(cur, existing["id"], doc)
                if collision_error is not None:
                    return collision_error

        summary = upsert_document(conn, doc)

    return JSONResponse(content={
        "essay_id": summary.essay_id,
        "slug": doc["slug"],
        "sections_created": summary.sections_created,
        "sections_updated": summary.sections_updated,
        "cards_created": summary.flashcards_created,
        "cards_updated": summary.flashcards_updated,
    })
