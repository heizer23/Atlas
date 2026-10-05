"""
GET /flashcards/due, GET /flashcards/stats, POST /flashcards/upsert,
GET /flashcards/{flashcard_id}/export, and POST /flashcards/{flashcard_id}/review.

GET /due and GET /stats are read endpoints and return Dataset per
R-CON-BP-04.

POST .../review is a mutation endpoint (R-CON-BP-04 exempt from the Dataset
requirement). It reads the raw Starlette Request body — not a Pydantic body
model — so a missing grade key, a non-string grade value, an out-of-set grade
value, or an unparsable JSON body are ALL caught by application code and
returned as ApiError with error.code=VALIDATION_ERROR (400). FastAPI's default
RequestValidationError 422 shape must never be produced by this endpoint.

POST /upsert (Sprint08_QuestionLevelsAndStructure) is the single-question
create/update operation: {essay_slug, section_id, card: {id?, level, q, a}}.
Same raw-Request/no-Pydantic-model precedent as .../review. It never touches
essaycards.essays or essaycards.essay_sections — see its own docstring for
why that makes it safe to reimport a single-question AI export unedited.

GET /{flashcard_id}/export is a bespoke-JSON, Dataset-exempt read endpoint
(R-CON-BP-04 exemption, same rationale as GET
/essays/{essay_id}/examination-package) — the single-question counterpart to
POST /upsert, for copying to the clipboard for an external LLM.

'/due', '/stats' and '/upsert' are registered before the parameterised
'/{flashcard_id}/...' routes to avoid FastAPI path-matching ambiguity with
any future single-segment route.
"""

import re
import secrets
import uuid
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from psycopg2.extras import Json

from backend.database import get_db
from backend.progress import UNLOCKED_SECTION_SQL
from backend.revalidation import (
    clear_revalidation_flag,
    is_revalidation_correct,
    record_revalidation_event,
)
from backend.scheduling import VALID_GRADES, FSRSScheduler
from platform_contracts import ColumnSchema, Dataset, DatasetMeta
from platform_errorhandling import api_error

router = APIRouter(prefix="/flashcards", tags=["flashcards"])

_CARD_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")

# Sentinel distinguishing "card.nugget_id key absent from the payload" from
# "card.nugget_id present as JSON null" (R-CON-AL-04). dict.get(key, _UNSET)
# returns this object only when the key itself was never sent.
_UNSET = object()


def _is_uuid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False

DUE_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="question",    label="Question", type="string",  sortable=False, filterable=False),
    ColumnSchema(key="answer",      label="Answer",   type="string",  sortable=False, filterable=False, detail_visible=True),
    ColumnSchema(key="essay_id",    label="Essay",    type="string",  sortable=False, filterable=True),
    ColumnSchema(key="section_id",  label="Section",  type="string",  sortable=False, filterable=True),
    ColumnSchema(key="anchor_slug", label="Anchor",   type="string",  sortable=False, filterable=False),
    ColumnSchema(key="next_due_at", label="Due",      type="date",    sortable=True,  filterable=False),
    # is_new == "this card has never been reviewed" (last_reviewed_at IS NULL,
    # i.e. interval 0). Additive, non-breaking (R-CON-BP-04). Consumed by the
    # review screen's CURRENT stats block to count new cards in the session.
    ColumnSchema(key="is_new",      label="New",      type="boolean", sortable=False, filterable=False),
    # is_recent == the RECENT-vs-BACKLOG category flag: exactly the ordering
    # predicate last_reviewed_at >= now() - interval '24 hours'. True => this
    # card was placed ahead of the backlog because it was reviewed within the
    # rolling 24h window (sorted by next_due_at), not because of its interval.
    # false for a never-reviewed card. Additive, non-breaking; the review
    # screen bolds the question frame when true.
    ColumnSchema(key="is_recent",   label="Recent",   type="boolean", sortable=False, filterable=False),
    # scheduled_interval_seconds == extract(epoch from
    # flashcard_review_state.review_interval) — the interval this card is
    # currently scheduled across, i.e. the value the BACKLOG ordering sorts on.
    # 0 for a never-reviewed ("new") card (review_interval defaults to '0').
    # Additive, non-breaking; shown in the review screen's diagnostics frame
    # ("this card's last interval").
    ColumnSchema(key="scheduled_interval_seconds", label="Interval (s)", type="number", sortable=False, filterable=False),
    # [NEW Sprint09_Nuggets] The card's current nugget assignment (nullable).
    # Feeds the review screen's source-navigation branch: set -> "Flashcard ->
    # Nugget" overlay; null -> unchanged legacy "Jump to passage" navigation.
    ColumnSchema(key="nugget_id", label="Nugget", type="string", sortable=False, filterable=True),
]

STATS_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="bucket", label="Bucket",  type="string", sortable=False, filterable=False),
    ColumnSchema(key="label",  label="Horizon", type="string", sortable=False, filterable=False),
    ColumnSchema(key="count",  label="Cards",   type="number", sortable=False, filterable=False),
]

# (bucket key, display label) in fixed near -> far order. This list IS the
# response row order and the set of buckets is closed. `bucket` is the stable
# machine key; `label` is a short human string for a compact horizontal strip.
STATS_BUCKETS: list[tuple[str, str]] = [
    ("due_now",        "Due now"),
    ("within_10_min",  "≤ 10 min"),
    ("within_1_day",   "≤ 1 day"),
    ("within_7_days",  "≤ 7 days"),
    ("within_30_days", "≤ 30 days"),
    ("within_90_days", "≤ 3 mo"),
    ("beyond_90_days", "> 3 mo"),
]


def _due_row_to_dict(row: Any) -> dict[str, Any]:
    d = dict(row)
    d["id"] = str(d["id"])
    d["flashcard_id"] = str(d["flashcard_id"])
    d["essay_id"] = str(d["essay_id"])
    d["section_id"] = str(d["section_id"])
    d["nugget_id"] = str(d["nugget_id"]) if d.get("nugget_id") else None
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
def list_due_flashcards(
    topic: str | None = None,
    essay_id: str | None = None,
    section_id: str | None = None,
) -> JSONResponse:
    """
    Session type is inferred from whether a scope parameter is present — there
    is no mode parameter:

      - no scope           -> REVIEW (maintenance). Eligibility adds
                              review_interval >= interval '24 hours', so only
                              `established` cards that are also due appear.
      - topic=<category>    -> FOCUS on that topic (all essays whose
                              essays.category equals it).
      - essay_id=<id>       -> FOCUS on that essay.
      - essay_id + section_id -> FOCUS on that section.

    A FOCUS session applies no interval filter: every open card in scope
    appears, whether it is new, learning, or established.

    Allowed scoped forms are exactly: {topic}, {essay_id}, {essay_id,
    section_id}. {section_id} alone, or {topic} together with essay_id or
    section_id, are rejected with VALIDATION_ERROR.

    Sprint14: locked cards (section guided oral not passed) and cards with
    needs_revalidation are never eligible here. ORDER BY is unchanged.

    Eligibility: next_due_at <= now(), evaluated by Postgres at query time
    (R-CON-AL-06 — single server-clock authority; the client never sends a
    time). Empty result is valid.

    Ordering (R-CON-AL-01) — eligible cards fall into two categories and
    category RECENT is returned entirely before category BACKLOG:

      RECENT  — last_reviewed_at >= now() - interval '24 hours'.
                A rolling 24-hour window off the same now(); NOT a calendar
                day, so the local midnight boundary is irrelevant. A card with
                last_reviewed_at IS NULL is never RECENT.
                Sorted by next_due_at DESC: the card that came due most
                recently (closest to now) is shown first. A card the user
                struggled with — pushed a few minutes into the future — thus
                re-enters near the front of the queue as soon as that short
                delay elapses. This category serves relearning within one
                broader learning period.

      BACKLOG — every other eligible card. Sorted by the interval the card is
                currently scheduled across, flashcard_review_state.review_interval
                (== next_due_at - last_reviewed_at), DESC: longest interval
                first, shortest last. How overdue the card is does NOT affect
                this order — a mature card only 1 minute overdue still precedes
                an immature card days overdue. A never-reviewed card has
                review_interval 0 and therefore sorts behind every
                previously-reviewed backlog card. interval = 0 is how the data
                model represents a new card (backend/ingest.py seeds
                last_reviewed_at = null, review_interval = '0'); no separate
                new-card queue or "block until backlog empty" gate exists or is
                needed.

    Final tie-breakers, for deterministic paging: next_due_at ASC, then
    flashcard id ASC.

    Each row also carries three additive fields (R-CON-BP-04; none affects
    eligibility or ordering):
      - is_new (bool) = (last_reviewed_at IS NULL) — never-reviewed / interval-0.
      - is_recent (bool) = (last_reviewed_at >= now() - interval '24 hours') —
        the RECENT-vs-BACKLOG category flag (false when is_new).
      - scheduled_interval_seconds (int) = epoch seconds of
        flashcard_review_state.review_interval, the interval the card is
        currently scheduled across (the BACKLOG sort key). 0 when is_new.
    """
    if section_id and not essay_id:
        return api_error("VALIDATION_ERROR", "section_id requires essay_id to also be provided")
    if topic and (essay_id or section_id):
        return api_error(
            "VALIDATION_ERROR", "topic cannot be combined with essay_id or section_id"
        )

    scoped = bool(topic or essay_id)  # section_id implies essay_id

    # Sprint14: eligibility also requires the card's section to be unlocked
    # (guided section oral passed) and the card not awaiting revalidation
    # (flagged cards are served only by GET /flashcards/revalidation).
    conditions: list[str] = [
        "frs.next_due_at <= now()",
        UNLOCKED_SECTION_SQL,
        "frs.needs_revalidation = false",
    ]
    params: list[Any] = []
    extra_join = ""
    if not scoped:
        # REVIEW / maintenance: only established cards that are also due.
        conditions.append("frs.review_interval >= interval '24 hours'")
    if topic:
        extra_join = "join essaycards.essays e on e.id = f.essay_id"
        conditions.append("e.category = %s")
        params.append(topic)
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
                       f.nugget_id, s.anchor_slug, frs.next_due_at,
                       (frs.last_reviewed_at is null) as is_new,
                       coalesce(frs.last_reviewed_at >= now() - interval '24 hours', false)
                           as is_recent,
                       extract(epoch from frs.review_interval)::bigint
                           as scheduled_interval_seconds
                from essaycards.flashcards f
                join essaycards.flashcard_review_state frs on frs.flashcard_id = f.id
                join essaycards.essay_sections s on s.id = f.section_id
                {extra_join}
                {where}
                order by
                    case when frs.last_reviewed_at >= now() - interval '24 hours'
                         then 0 else 1 end,
                    case when frs.last_reviewed_at >= now() - interval '24 hours'
                         then frs.next_due_at end desc nulls last,
                    frs.review_interval desc,
                    frs.next_due_at asc,
                    f.id asc
                """,
                params,
            )
            rows = []
            for r in cur.fetchall():
                d = dict(r)
                d["id"] = d["flashcard_id"]
                rows.append(_due_row_to_dict(d))

    return _dataset_response(_due_dataset(rows))


@router.get("/stats", response_model=None)
def flashcard_queue_stats(
    topic: str | None = None,
    essay_id: str | None = None,
    section_id: str | None = None,
) -> JSONResponse:
    """
    Review-queue forecast: every flashcard that has a review-state row,
    partitioned into seven non-overlapping horizon bands by next_due_at relative
    to now(). Read endpoint -> returns Dataset (R-CON-BP-04).

    Parameters (identical scoping rules to GET /flashcards/due, minus the
    review/focus interval filter — this endpoint always counts every scheduled
    card in scope regardless of interval):
      - topic       optional; restrict to essays whose essays.category matches.
      - essay_id    optional; restrict to one essay.
      - section_id  optional; requires essay_id; restrict to one section.
      - section_id without essay_id                  -> VALIDATION_ERROR (400).
      - topic together with essay_id or section_id   -> VALIDATION_ERROR (400).
      - no params                                    -> system-wide.
    No other parameter is accepted. There is no ordering parameter: rows are
    always returned in the fixed near -> far band order of STATS_BUCKETS.

    Time basis: Postgres now(), evaluated once per statement, so all band
    boundaries are computed against the identical instant (R-CON-AL-06 — same
    server-time authority as GET /flashcards/due). Bands are open on the lower
    edge and closed on the upper edge:
        due_now        : next_due_at <= now()
        within_10_min  : now()           < next_due_at <= now() + 10 minutes
        within_1_day   : now() + 10 min  < next_due_at <= now() + 1 day
        within_7_days  : now() + 1 day   < next_due_at <= now() + 7 days
        within_30_days : now() + 7 days  < next_due_at <= now() + 30 days
        within_90_days : now() + 30 days < next_due_at <= now() + 90 days
        beyond_90_days : next_due_at > now() + 90 days
    Every review-state row in scope falls into exactly one band; the seven
    counts sum to the total number of scheduled flashcards in scope. The
    30-/90-day split feeds the review screen's UPCOMING forecast columns
    (≤3 mo / >3 mo).

    Empty-result behavior: always exactly seven rows. An empty scope (or an
    unknown essay_id) yields seven rows with count 0 — the bands are
    zero-filled, never omitted. meta.total is the row count (always 7), not the
    card total.
    """
    if section_id and not essay_id:
        return api_error("VALIDATION_ERROR", "section_id requires essay_id to also be provided")
    if topic and (essay_id or section_id):
        return api_error(
            "VALIDATION_ERROR", "topic cannot be combined with essay_id or section_id"
        )

    # Sprint14: locked cards are excluded. needs_revalidation cards stay
    # counted in their FSRS due-date bands (their due dates are untouched), so
    # due_now can exceed the focus queue by the number of flagged due cards.
    conditions: list[str] = [UNLOCKED_SECTION_SQL]
    params: list[Any] = []
    extra_join = ""
    if topic:
        extra_join = "join essaycards.essays e on e.id = f.essay_id"
        conditions.append("e.category = %s")
        params.append(topic)
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
                select
                  count(*) filter (
                    where frs.next_due_at <= now())                                  as due_now,
                  count(*) filter (
                    where frs.next_due_at >  now()
                      and frs.next_due_at <= now() + interval '10 minutes')          as within_10_min,
                  count(*) filter (
                    where frs.next_due_at >  now() + interval '10 minutes'
                      and frs.next_due_at <= now() + interval '1 day')               as within_1_day,
                  count(*) filter (
                    where frs.next_due_at >  now() + interval '1 day'
                      and frs.next_due_at <= now() + interval '7 days')              as within_7_days,
                  count(*) filter (
                    where frs.next_due_at >  now() + interval '7 days'
                      and frs.next_due_at <= now() + interval '30 days')             as within_30_days,
                  count(*) filter (
                    where frs.next_due_at >  now() + interval '30 days'
                      and frs.next_due_at <= now() + interval '90 days')             as within_90_days,
                  count(*) filter (
                    where frs.next_due_at >  now() + interval '90 days')             as beyond_90_days
                from essaycards.flashcard_review_state frs
                join essaycards.flashcards f on f.id = frs.flashcard_id
                {extra_join}
                {where}
                """,
                params,
            )
            counts = cur.fetchone()

    rows = [
        {"bucket": key, "label": label, "count": int(counts[key])}
        for key, label in STATS_BUCKETS
    ]
    dataset = Dataset(
        meta=DatasetMeta(
            object_type="flashcard_queue_stat",
            label="Review Queue Forecast",
            total=len(rows),
            page=1,
            page_size=len(rows),
            row_actions=[],
        ),
        **{"schema": STATS_SCHEMA},
        rows=rows,
    )
    return _dataset_response(dataset)


@router.get("/revalidation", response_model=None)
def list_revalidation_cards(essay_id: str | None = None) -> JSONResponse:
    """
    The Revalidation queue (Sprint14): every card flagged needs_revalidation,
    available immediately regardless of next_due_at. Same row shape as
    GET /flashcards/due (DUE_SCHEMA); is_new is always false.

    Parameters (R-CON-AL-01): optional essay_id; allowed combinations {} and
    {essay_id}. No time predicate (flagged == eligible). Ordering,
    deterministic: essay display order (category asc nulls last, sort_index
    asc, created_at asc), section order_index asc, flashcards.level asc,
    flashcards.created_at asc, flashcards.id asc — the FSRS due date is
    deliberately ignored. Empty result (or unknown essay_id) -> empty Dataset;
    that is the "revalidation complete" signal.
    """
    rows: list[dict[str, Any]] = []
    if essay_id is None or _is_uuid(essay_id):
        conditions = ["frs.needs_revalidation"]
        params: list[Any] = []
        if essay_id:
            conditions.append("f.essay_id = %s")
            params.append(essay_id)
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    select f.id as flashcard_id, f.question, f.answer, f.essay_id, f.section_id,
                           f.nugget_id, s.anchor_slug, frs.next_due_at,
                           false as is_new,
                           coalesce(frs.last_reviewed_at >= now() - interval '24 hours', false)
                               as is_recent,
                           extract(epoch from frs.review_interval)::bigint
                               as scheduled_interval_seconds
                    from essaycards.flashcards f
                    join essaycards.flashcard_review_state frs on frs.flashcard_id = f.id
                    join essaycards.essay_sections s on s.id = f.section_id
                    join essaycards.essays e on e.id = f.essay_id
                    where {" and ".join(conditions)}
                    order by e.category asc nulls last, e.sort_index asc, e.created_at asc,
                             s.order_index asc, f.level asc, f.created_at asc, f.id asc
                    """,
                    params,
                )
                for r in cur.fetchall():
                    d = dict(r)
                    d["id"] = d["flashcard_id"]
                    rows.append(_due_row_to_dict(d))

    return _dataset_response(_due_dataset(rows))


# ── Single-question maintenance (Sprint08_QuestionLevelsAndStructure) ───────
#
# POST /upsert + GET /{flashcard_id}/export are the narrow, question-only
# counterpart to the essay-shaped ingest/export pair in
# backend/routers/essays.py. Both operate purely on essaycards.flashcards
# (+ flashcard_review_state for a create) and never touch essaycards.essays
# or essaycards.essay_sections.

def _validate_upsert_body(body: Any) -> tuple[dict[str, Any] | None, JSONResponse | None]:
    """
    Full structural validation of a POST /upsert payload. Returns
    (parsed, None) on success, or (None, ApiError VALIDATION_ERROR) on the
    first violation. Never touches the database — mirrors
    essays.py::_validate_ingest_body's validate-everything-first precedent.

    `card.level` is REQUIRED (no silent default) — an omitted level must
    never quietly reset an existing level-1/level-3 card back to some
    default; the caller (the overview's edit form, always pre-filled with
    the card's current level, or an AI reply that copied it from the export)
    must always state it explicitly.
    """
    if not isinstance(body, dict):
        return None, api_error("VALIDATION_ERROR", "Request body must be a JSON object")

    essay_slug = body.get("essay_slug")
    if not isinstance(essay_slug, str) or not essay_slug.strip():
        return None, api_error("VALIDATION_ERROR", "essay_slug is required and must be a non-empty string")
    essay_slug = essay_slug.strip()

    section_id = body.get("section_id")
    if not isinstance(section_id, str) or not section_id.strip():
        return None, api_error("VALIDATION_ERROR", "section_id is required and must be a non-empty string")
    section_id = section_id.strip()

    card_raw = body.get("card")
    if not isinstance(card_raw, dict):
        return None, api_error("VALIDATION_ERROR", "card is required and must be an object")

    card_id = card_raw.get("id")
    if card_id is not None:
        if not isinstance(card_id, str) or not card_id.strip():
            return None, api_error("VALIDATION_ERROR", "card.id, if present, must be a non-empty string")
        card_id = card_id.strip()
        if not _CARD_ID_RE.match(card_id):
            return None, api_error(
                "VALIDATION_ERROR", f"card.id '{card_id}' must match ^[a-zA-Z0-9_-]+$"
            )

    level = card_raw.get("level")
    if isinstance(level, bool) or not isinstance(level, int) or level < 1:
        return None, api_error("VALIDATION_ERROR", "card.level is required and must be an integer >= 1")

    q = card_raw.get("q")
    if not isinstance(q, str) or not q.strip():
        return None, api_error("VALIDATION_ERROR", "card.q is required and must be a non-empty string")

    a = card_raw.get("a")
    if not isinstance(a, str) or not a.strip():
        return None, api_error("VALIDATION_ERROR", "card.a is required and must be a non-empty string")

    # nugget_id tri-state (R-CON-AL-04, Sprint09_Nuggets): key OMITTED from
    # card ->  leave any existing assignment untouched; key present as JSON
    # null -> clear the assignment; key present with a value -> must be a
    # well-formed uuid string (existence is checked against the DB in
    # _upsert_question, inside the transaction).
    nugget_id_raw = card_raw.get("nugget_id", _UNSET)
    touch_nugget_id = nugget_id_raw is not _UNSET
    nugget_id: str | None = None
    if touch_nugget_id and nugget_id_raw is not None:
        if not _is_uuid(nugget_id_raw):
            return None, api_error(
                "VALIDATION_ERROR", "card.nugget_id, if present and non-null, must be a well-formed uuid string"
            )
        nugget_id = nugget_id_raw

    return {
        "essay_slug": essay_slug,
        "section_id": section_id,
        "card_id": card_id,  # None => auto-generate (new card, no author-chosen id)
        "level": level,
        "question": q,
        "answer": a,
        "touch_nugget_id": touch_nugget_id,
        "nugget_id": nugget_id,
    }, None


def _new_card_key(cur: Any, essay_id: str) -> str:
    """Auto-generated card_key for a new question created without an
    explicit id (the question-overview's "Add question" form). Deliberately
    NOT a cross-module import of backend/exploration.py's own "_"-private
    helper of the same shape — each module owns its own key-generation
    concern. flashcards has unique(essay_id, card_key); retry on the
    (vanishingly unlikely) collision."""
    for _ in range(10):
        key = f"q-{secrets.token_hex(4)}"
        cur.execute(
            "select 1 from essaycards.flashcards where essay_id = %s and card_key = %s",
            (essay_id, key),
        )
        if not cur.fetchone():
            return key
    raise RuntimeError("could not allocate a unique card_key")  # pragma: no cover


def _upsert_question(
    cur: Any, essay_slug: str, section_id: str, card_id: str | None,
    level: int, question: str, answer: str,
    touch_nugget_id: bool = False, nugget_id: str | None = None,
) -> tuple[dict[str, Any] | None, JSONResponse | None]:
    """
    Create or update exactly one flashcard. Returns (result, None) or
    (None, ApiError). Never touches essaycards.essays or
    essaycards.essay_sections (only reads them, to resolve/validate ids).

    card_id present and matching an existing card_key for this essay ->
    UPDATE in place (question/answer/level change; id, card_key, essay,
    section all stable). card_id present but unmatched -> CREATE with that
    id. card_id None -> CREATE with an auto-generated id.

    Rejects a card_id that already exists under a DIFFERENT section
    (mirrors essays.py::_check_card_section_collisions) — section_id is not
    in the UPDATE's SET clause, so this endpoint cannot move a card between
    sections even by accident.

    nugget_id tri-state (R-CON-AL-04, Sprint09_Nuggets): touch_nugget_id
    False -> the SET clause's `case` leaves the existing nugget_id
    untouched (also vacuously true on create — nothing to touch, so the
    INSERT column is simply null in that case). touch_nugget_id True and
    nugget_id None -> clears the assignment. touch_nugget_id True and
    nugget_id a value -> resolved against essaycards.nuggets first
    (VALIDATION_ERROR if it does not exist) and set. Implemented as a single
    INSERT ... ON CONFLICT DO UPDATE whose nugget_id SET expression is one
    `case` — never two divergent code paths.
    """
    if touch_nugget_id and nugget_id is not None:
        cur.execute("select 1 from essaycards.nuggets where id = %s", (nugget_id,))
        if not cur.fetchone():
            return None, api_error(
                "VALIDATION_ERROR", f"card.nugget_id '{nugget_id}' does not resolve to an existing nugget"
            )
    cur.execute("select id from essaycards.essays where slug = %s", (essay_slug,))
    essay_row = cur.fetchone()
    if not essay_row:
        return None, api_error("NOT_FOUND", f"Essay with slug '{essay_slug}' not found", status=404)
    essay_id = essay_row["id"]

    cur.execute("select essay_id from essaycards.essay_sections where id = %s", (section_id,))
    section_row = cur.fetchone()
    if not section_row:
        return None, api_error("NOT_FOUND", f"Section {section_id} not found", status=404)
    if str(section_row["essay_id"]) != str(essay_id):
        return None, api_error(
            "VALIDATION_ERROR", f"Section {section_id} does not belong to essay '{essay_slug}'"
        )

    if card_id is not None:
        cur.execute(
            "select section_id from essaycards.flashcards where essay_id = %s and card_key = %s",
            (essay_id, card_id),
        )
        existing = cur.fetchone()
        if existing and str(existing["section_id"]) != str(section_id):
            return None, api_error(
                "VALIDATION_ERROR",
                f"card '{card_id}' already exists under a different section and cannot be "
                "moved via this endpoint",
            )
    else:
        card_id = _new_card_key(cur, str(essay_id))

    insert_nugget_id = nugget_id if touch_nugget_id else None
    cur.execute(
        """
        insert into essaycards.flashcards (essay_id, section_id, card_key, question, answer, level, nugget_id)
        values (%s, %s, %s, %s, %s, %s, %s)
        on conflict (essay_id, card_key) do update
            set question   = excluded.question,
                answer     = excluded.answer,
                level      = excluded.level,
                nugget_id  = case when %s then excluded.nugget_id
                                  else essaycards.flashcards.nugget_id end,
                updated_at = now()
        returning id, created_at, nugget_id, (xmax = 0) as was_inserted
        """,
        (essay_id, section_id, card_id, question, answer, level, insert_nugget_id, touch_nugget_id),
    )
    row = cur.fetchone()

    if row["was_inserted"]:
        cur.execute(
            """
            insert into essaycards.flashcard_review_state (flashcard_id, last_reviewed_at, next_due_at)
            values (%s, null, %s)
            """,
            (row["id"], row["created_at"]),
        )

    return {
        "flashcard_id": str(row["id"]),
        "card_id": card_id,
        "essay_id": str(essay_id),
        "section_id": section_id,
        "level": level,
        "nugget_id": str(row["nugget_id"]) if row.get("nugget_id") else None,
        "created": row["was_inserted"],
    }, None


@router.post("/upsert", response_model=None)
async def upsert_flashcard(request: Request) -> JSONResponse:
    """
    Create or update exactly ONE flashcard — the question-level counterpart
    to POST /essays/ingest, sharing none of its code or validation. Body:
    {essay_slug, section_id, card: {id?, level, q, a}}. Reads the raw
    Starlette Request body — not a Pydantic body model — same VALIDATION_ERROR
    precedent as POST /essays/ingest and POST .../review.

    This is a mutation endpoint (R-CON-BP-04 exempt): returns a typed record
    on success (200), ApiError on any failure. It never touches
    essaycards.essays or essaycards.essay_sections — the payload has no
    field for section prose/heading/order at all, so even pasting back an
    unedited single-question export (which DOES carry that context, as
    read-only grounding for an external LLM — see GET .../export below)
    cannot change essay content; there is nothing here for such a field to
    write to.
    """
    try:
        body = await request.json()
    except Exception:
        return api_error("VALIDATION_ERROR", "Request body must be valid JSON")

    parsed, error = _validate_upsert_body(body)
    if error is not None:
        return error

    with get_db() as conn:
        with conn.cursor() as cur:
            result, error = _upsert_question(
                cur, parsed["essay_slug"], parsed["section_id"], parsed["card_id"],
                parsed["level"], parsed["question"], parsed["answer"],
                parsed["touch_nugget_id"], parsed["nugget_id"],
            )
            if error is not None:
                return error
        conn.commit()

    return JSONResponse(content=result)


@router.get("/{flashcard_id}/export", response_model=None)
def export_question(flashcard_id: str) -> JSONResponse:
    """
    Self-contained JSON export of ONE flashcard for an external AI
    conversation. essay_slug/essay_title/section_* fields are READ-ONLY
    CONTEXT (grounding for the discussion) — POST /upsert has no field to
    write them back to, so this package can be pasted back unedited (or with
    only card.* changed) with no risk of touching essay prose. See
    POST /upsert's docstring.

    Bespoke JSON, not a Dataset — R-CON-BP-04 exemption, same rationale as
    GET /essays/{essay_id}/examination-package.

    404 ApiError if flashcard_id does not exist.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select f.card_key, f.question, f.answer, f.level, f.nugget_id,
                       f.section_id, s.anchor_slug as section_anchor_slug,
                       s.heading as section_heading, s.body_markdown as section_body_markdown,
                       e.slug as essay_slug, e.title as essay_title
                from essaycards.flashcards f
                join essaycards.essay_sections s on s.id = f.section_id
                join essaycards.essays e on e.id = f.essay_id
                where f.id = %s
                """,
                (flashcard_id,),
            )
            row = cur.fetchone()
            if not row:
                return api_error("NOT_FOUND", f"Flashcard {flashcard_id} not found", status=404)

    package = {
        "export_version": 1,
        "essay_slug": row["essay_slug"],
        "essay_title": row["essay_title"],
        "section_id": str(row["section_id"]),
        "section_anchor_slug": row["section_anchor_slug"],
        "section_heading": row["section_heading"],
        "section_body_markdown": row["section_body_markdown"],
        "card": {
            "id": row["card_key"],
            "level": row["level"],
            "q": row["question"],
            "a": row["answer"],
            "nugget_id": str(row["nugget_id"]) if row["nugget_id"] else None,
        },
    }
    return JSONResponse(content=package)


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


def _load_fsrs_existing_state(cur: Any, flashcard_id: str) -> dict[str, Any] | None:
    """Read this card's persisted FSRS memory state, if any. Returns None for
    a card being reviewed for the first time (never reviewed before, or
    reviewed pre-Sprint12 and not yet reached by the legacy backfill) —
    FSRSScheduler.review starts such a card from a fresh fsrs.Card()."""
    cur.execute(
        "select raw_state from essaycards.fsrs_card_state where flashcard_id = %s",
        (flashcard_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return {"raw_state": row["raw_state"]}


def _upsert_fsrs_card_state(cur: Any, flashcard_id: str, extra_state: dict[str, Any]) -> None:
    """Persist FSRS's own memory state. raw_state (fsrs.Card.to_dict()) is the
    sole source of truth for reconstructing the Card on the next review; the
    discrete columns exist only for dashboard queryability/audit and are
    always written from the SAME extra_state dict that produced raw_state —
    never derived independently."""
    cur.execute(
        """
        insert into essaycards.fsrs_card_state
            (flashcard_id, stability, difficulty, fsrs_state, step, last_review_at, raw_state, updated_at)
        values (%s, %s, %s, %s, %s, %s, %s, now())
        on conflict (flashcard_id) do update
            set stability      = excluded.stability,
                difficulty     = excluded.difficulty,
                fsrs_state     = excluded.fsrs_state,
                step           = excluded.step,
                last_review_at = excluded.last_review_at,
                raw_state      = excluded.raw_state,
                updated_at     = now()
        """,
        (
            flashcard_id,
            extra_state["stability"],
            extra_state["difficulty"],
            extra_state["fsrs_state"],
            extra_state["step"],
            extra_state["last_review_at"],
            Json(extra_state["raw_state"]),
        ),
    )


def _insert_review_event(
    cur: Any,
    flashcard_id: str,
    grade: str,
    now: Any,
    was_due: bool,
    prior_review_interval: Any,
    resulting_review_interval: Any,
) -> None:
    """Append-only: one row per review. Called unconditionally for every
    review — backs GET /review-stats/summary|activity, since
    flashcard_review_state only ever holds the latest snapshot."""
    cur.execute(
        """
        insert into essaycards.review_events
            (flashcard_id, grade, reviewed_at, was_due,
             prior_review_interval, resulting_review_interval)
        values (%s, %s, %s, %s, %s, %s)
        """,
        (flashcard_id, grade, now, was_due, prior_review_interval, resulting_review_interval),
    )


@router.post("/{flashcard_id}/review", response_model=None)
async def review_flashcard(flashcard_id: str, request: Request) -> JSONResponse:
    """
    Grade a flashcard and persist its updated scheduling state.

    R-CON-AL-06 time authority: a single `select now()` read at the start of
    the transaction is reused as both last_reviewed_at and the base for
    computing next_due_at.

    Sprint12_FSRSAndUXOverhaul: FSRS is the sole scheduler — always dispatches
    to FSRSScheduler, unconditionally. The request/response shape is unchanged
    from pre-sprint. This is still the single writer of
    flashcard_review_state.review_interval — the write-time cache of
    (next_due_at - last_reviewed_at) — set here in the same UPDATE as
    next_due_at, from FSRSScheduler's SchedulerResult. Inside the SAME
    transaction/commit as that UPDATE, this also upserts fsrs_card_state and
    always inserts one review_events row — a review can never persist its new
    due date while failing to persist its FSRS state or its review-event
    record.

    Sprint14: rejects a card in a locked section (VALIDATION_ERROR, no write)
    and branches on the card's server-side needs_revalidation flag — see
    backend/revalidation.py. Response gains revalidation_outcome
    (null | 'preserved' | 'failed').
    """
    grade, error = await _parse_review_grade(request)
    if error is not None:
        return error

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select now() as now")
            now = cur.fetchone()["now"]

            cur.execute(
                f"""
                select frs.last_reviewed_at, frs.next_due_at, frs.review_interval,
                       frs.needs_revalidation, f.essay_id,
                       {UNLOCKED_SECTION_SQL} as is_unlocked
                from essaycards.flashcard_review_state frs
                join essaycards.flashcards f on f.id = frs.flashcard_id
                where frs.flashcard_id = %s
                """,
                (flashcard_id,),
            )
            state_row = cur.fetchone()
            if not state_row:
                return api_error("NOT_FOUND", f"Flashcard {flashcard_id} not found", status=404)

            # Locked-card write guard (stale clients): a card whose section has
            # not passed its guided oral cannot be reviewed. No write happens.
            if not state_row["is_unlocked"]:
                return api_error(
                    "VALIDATION_ERROR",
                    "This card is locked: pass the guided oral exam for its section to unlock it",
                )

            # Revalidation is server-derived from the flag; the client sends no mode.
            is_revalidation = bool(state_row["needs_revalidation"])

            if is_revalidation and is_revalidation_correct(grade):
                # CORRECT: clear the flag and audit it — NOTHING else changes
                # (no FSRS call, no review_events row, no timestamp/interval write).
                clear_revalidation_flag(cur, flashcard_id)
                record_revalidation_event(cur, flashcard_id, str(state_row["essay_id"]), grade, "preserved")
                conn.commit()
                last_reviewed = state_row["last_reviewed_at"]
                return JSONResponse(content={
                    "flashcard_id": flashcard_id,
                    "last_reviewed_at": last_reviewed.isoformat() if last_reviewed else None,
                    "next_due_at": state_row["next_due_at"].isoformat(),
                    "revalidation_outcome": "preserved",
                })

            existing_state = _load_fsrs_existing_state(cur, flashcard_id)

            result = FSRSScheduler().review(grade, state_row["last_reviewed_at"], now, existing_state)

            was_due = state_row["next_due_at"] <= now
            prior_review_interval = state_row["review_interval"]

            cur.execute(
                """
                update essaycards.flashcard_review_state
                set last_reviewed_at = %s, next_due_at = %s, review_interval = %s, updated_at = %s
                where flashcard_id = %s
                """,
                (now, result.next_due_at, result.review_interval, now, flashcard_id),
            )

            _upsert_fsrs_card_state(cur, flashcard_id, result.extra_state)

            _insert_review_event(
                cur, flashcard_id, grade, now, was_due,
                prior_review_interval, result.review_interval,
            )

            # INCORRECT revalidation: a genuine FSRS failure (path above), plus
            # flag clear and audit row in the same transaction.
            if is_revalidation:
                clear_revalidation_flag(cur, flashcard_id)
                record_revalidation_event(cur, flashcard_id, str(state_row["essay_id"]), grade, "failed")
        conn.commit()

    return JSONResponse(content={
        "flashcard_id": flashcard_id,
        "last_reviewed_at": now.isoformat(),
        "next_due_at": result.next_due_at.isoformat(),
        "revalidation_outcome": "failed" if is_revalidation else None,
    })
