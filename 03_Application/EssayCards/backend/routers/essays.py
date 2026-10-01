"""
GET /essays, GET /essays/{essay_id}, GET /essays/{essay_id}/questions,
GET /essays/{essay_id}/export, GET /essays/{essay_id}/sections/{section_id}/export,
and POST /essays/ingest.

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

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.database import get_db
from backend.ingest import (
    DEFAULT_ESSAY_STATUS,
    SLUG_LIKE_RE,
    VALID_ESSAY_STATUSES,
    IngestionError,
    extract_nugget_keys,
    upsert_document,
)
from platform_contracts import ColumnSchema, Dataset, DatasetMeta
from platform_errorhandling import api_error

router = APIRouter(prefix="/essays", tags=["essays"])

# Detail endpoint (GET /essays/{id}) — the base essay columns. main_spine_markdown
# and main_spine_nuggets are embedded on the row like `sections`, not added as
# ColumnSchema entries (same precedent).
ESSAY_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="title",      label="Title",    type="string", sortable=True,  filterable=True),
    ColumnSchema(key="slug",       label="Slug",     type="string", sortable=False, filterable=False),
    ColumnSchema(key="category",   label="Category", type="string", sortable=True,  filterable=True),
    ColumnSchema(key="sort_index", label="Order",    type="number", sortable=True,  filterable=False),
    ColumnSchema(key="status",     label="Status",   type="string", sortable=True,  filterable=True),
]

# List endpoint (GET /essays) — the roadmap view: base columns plus derived
# per-essay knowledge indicators (see list_essays docstring).
# Sprint12_FSRSAndUXOverhaul: oral_score/oral_date removed (replaced by the
# derived 0-4 learning_level and its four milestones — see
# _learning_progress_subquery_sql).
ESSAY_OVERVIEW_SCHEMA: list[ColumnSchema] = ESSAY_SCHEMA + [
    ColumnSchema(key="progress_established",          label="Established",           type="number",  sortable=True,  filterable=False),
    ColumnSchema(key="progress_total",                 label="Total cards",           type="number",  sortable=True,  filterable=False),
    ColumnSchema(key="open_count",                     label="Open",                  type="number",  sortable=True,  filterable=False),
    ColumnSchema(key="cards_seen_count",                label="Cards seen",            type="number",  sortable=True,  filterable=False),
    ColumnSchema(key="cards_future_safe_count",         label="Cards future-safe",     type="number",  sortable=True,  filterable=False),
    ColumnSchema(key="milestone_all_cards_seen",        label="All cards seen",        type="boolean", sortable=False, filterable=False),
    ColumnSchema(key="milestone_all_cards_future_safe", label="All cards future-safe", type="boolean", sortable=False, filterable=False),
    ColumnSchema(key="milestone_guided_passed",         label="Guided exam passed",    type="boolean", sortable=False, filterable=False),
    ColumnSchema(key="milestone_unguided_passed",       label="Unguided exam passed",  type="boolean", sortable=False, filterable=False),
    ColumnSchema(key="guided_passed_at",                label="Guided passed on",      type="date",    sortable=True,  filterable=False),
    ColumnSchema(key="unguided_passed_at",              label="Unguided passed on",    type="date",    sortable=True,  filterable=False),
    ColumnSchema(key="learning_level",                  label="Learning level",        type="number",  sortable=True,  filterable=False),
]

# GET /essays/{essay_id}/questions — the question-overview screen. A flat row
# list, same pattern as ESSAY_OVERVIEW_SCHEMA: the frontend groups rows by
# section then by level client-side (mirroring EssayListView's existing
# category grouping) rather than the backend inventing a nested Dataset shape
# (Datasets are flat by contract — R-CON-BP-04).
QUESTION_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="card_key",            label="Card id",      type="string", sortable=False, filterable=False),
    ColumnSchema(key="question",            label="Question",     type="string", sortable=False, filterable=False, detail_visible=True),
    ColumnSchema(key="answer",              label="Answer",       type="string", sortable=False, filterable=False, detail_visible=True),
    ColumnSchema(key="level",               label="Level",        type="number", sortable=True,  filterable=True),
    ColumnSchema(key="section_id",          label="Section",      type="string", sortable=False, filterable=True),
    ColumnSchema(key="section_anchor_slug", label="Anchor",       type="string", sortable=False, filterable=False),
    ColumnSchema(key="section_heading",     label="Section title", type="string", sortable=False, filterable=False),
    ColumnSchema(key="section_order_index", label="Section order", type="number", sortable=True,  filterable=False),
    # [NEW Sprint09_Nuggets] The card's current nugget assignment (nullable) —
    # feeds QuestionOverviewView's edit-form nugget <select> (11_design_review.md
    # Hard Rule Violation 2 / Minimal Change Set item 3). section_nuggets
    # ({nugget_key, title} pairs for the row's own section) stays embedded on
    # the row like the existing section_* fields, not a ColumnSchema entry.
    ColumnSchema(key="nugget_id",           label="Nugget",        type="string", sortable=False, filterable=True),
]


def _row_to_dict(row: Any) -> dict[str, Any]:
    d = dict(row)
    d["id"] = str(d["id"])
    for k in ("created_at", "updated_at", "guided_passed_at", "unguided_passed_at"):
        if d.get(k):
            d[k] = d[k].isoformat()
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


def _nuggets_by_section(cur: Any, section_ids: list[str]) -> dict[str, list[dict[str, str]]]:
    """
    Given a list of section ids, returns dict[section_id, list[{nugget_key,
    title}]] — every nugget currently referenced by each section, ordered by
    nugget title asc. Reused by get_essay, export_essay, export_section, and
    list_essay_questions so the section_nuggets join SQL exists in exactly
    one place (Sprint09_Nuggets/10_architecture.json internal_flow step 8).
    """
    if not section_ids:
        return {}

    cur.execute(
        """
        select sn.section_id, n.nugget_key, n.title
        from essaycards.section_nuggets sn
        join essaycards.nuggets n on n.id = sn.nugget_id
        where sn.section_id = any(%s::uuid[])
        order by n.title asc
        """,
        (section_ids,),
    )
    result: dict[str, list[dict[str, str]]] = {}
    for row in cur.fetchall():
        result.setdefault(str(row["section_id"]), []).append(
            {"nugget_key": row["nugget_key"], "title": row["title"]}
        )
    return result


def _main_spine_nuggets(cur: Any, main_spine_markdown: str) -> list[dict[str, str]]:
    """
    Resolves every [[nugget:key]] reference in `main_spine_markdown` against
    essaycards.nuggets (same join shape as _nuggets_by_section, ORDER BY
    title asc) — independent of whether those keys are also referenced by any
    section. Reused by get_essay, export_essay, and export_section to attach
    a top-level main_spine_nuggets field alongside main_spine_markdown.
    Closes the gap where a nugget referenced only in main_spine_markdown had
    no title-resolution path (11_design_review.md Hard Rule Violation 1 /
    Minimal Change Set item 2). Unresolved keys (should not occur through the
    app — ingestion enforces resolution — but possible via direct SQL) are
    silently omitted here; rendering-time fallback for that case lives in the
    frontend's remarkNuggetRefs (nugget-missing:<key>).
    """
    keys = extract_nugget_keys(main_spine_markdown)
    if not keys:
        return []

    cur.execute(
        "select nugget_key, title from essaycards.nuggets where nugget_key = any(%s) order by title asc",
        (list(keys),),
    )
    return [{"nugget_key": row["nugget_key"], "title": row["title"]} for row in cur.fetchall()]


# ── Learning progress (Sprint12_FSRSAndUXOverhaul) ──────────────────────────
#
# Shared LATERAL-join SQL fragment computing the nine derived learning-
# progress fields for ONE essay — reused by both _OVERVIEW_QUERY (per-row,
# list_essays) and get_essay's single-essay query, so the milestone logic
# exists in exactly one place (R-CON-BP-09). Assumes the enclosing query's
# essays row is aliased `e`. All against Postgres now() at query time
# (R-CON-AL-06) — never cached/stored.
#
# "Active card" = every flashcard currently belonging to the essay (no
# archival/retirement concept exists). Milestone 1/2 are explicitly false
# (never vacuously true) for a zero-card essay — card_counts.total = 0 fails
# the `> 0` guard on both. Milestone 3/4 ("passed") require (a) at least one
# section, (b) EVERY section to have at least one examination of that
# exam_type, and (c) EVERY such section's LATEST examination of that type to
# score >= 3 (PASS_SCORE_THRESHOLD) — a per-section minimum gate, not an
# average. *_passed_at is the OLDEST examined_at among those latest-per-
# section rows, present only when the corresponding milestone is true.
def _learning_progress_subquery_sql() -> str:
    return """
    left join lateral (
      with sec as (
        select s.id from essaycards.essay_sections s where s.essay_id = e.id
      ),
      cards as (
        select frs.last_reviewed_at, frs.next_due_at
        from essaycards.flashcards f
        join essaycards.flashcard_review_state frs on frs.flashcard_id = f.id
        where f.essay_id = e.id
      ),
      card_counts as (
        select
          count(*) as total,
          count(*) filter (where last_reviewed_at is not null) as seen,
          count(*) filter (
            where last_reviewed_at is not null
              and next_due_at > now() + interval '24 hours'
          ) as future_safe
        from cards
      ),
      section_counts as (select count(*) as n from sec),
      guided_latest as (
        select distinct on (se.section_id) se.section_id, se.score, se.examined_at
        from essaycards.section_examinations se
        where se.section_id in (select id from sec) and se.exam_type = 'guided'
        order by se.section_id, se.examined_at desc
      ),
      unguided_latest as (
        select distinct on (se.section_id) se.section_id, se.score, se.examined_at
        from essaycards.section_examinations se
        where se.section_id in (select id from sec) and se.exam_type = 'unguided'
        order by se.section_id, se.examined_at desc
      )
      select
        cc.seen                                     as cards_seen_count,
        cc.future_safe                               as cards_future_safe_count,
        (cc.total > 0 and cc.seen = cc.total)        as milestone_all_cards_seen,
        (cc.total > 0 and cc.future_safe = cc.total) as milestone_all_cards_future_safe,
        (
          sc.n > 0 and sc.n = (select count(*) from guided_latest)
          and not exists (select 1 from guided_latest where score < 3)
        ) as milestone_guided_passed,
        case
          when sc.n > 0 and sc.n = (select count(*) from guided_latest)
               and not exists (select 1 from guided_latest where score < 3)
          then (select min(examined_at) from guided_latest)
        end as guided_passed_at,
        (
          sc.n > 0 and sc.n = (select count(*) from unguided_latest)
          and not exists (select 1 from unguided_latest where score < 3)
        ) as milestone_unguided_passed,
        case
          when sc.n > 0 and sc.n = (select count(*) from unguided_latest)
               and not exists (select 1 from unguided_latest where score < 3)
          then (select min(examined_at) from unguided_latest)
        end as unguided_passed_at
      from card_counts cc, section_counts sc
    ) lp on true
    """


_OVERVIEW_QUERY = f"""
select
  e.id, e.title, e.slug, e.category, e.sort_index, e.status,
  e.created_at, e.updated_at,
  (select count(*) from essaycards.flashcards f where f.essay_id = e.id)
      as progress_total,
  (select count(*)
     from essaycards.flashcards f
     join essaycards.flashcard_review_state frs on frs.flashcard_id = f.id
     where f.essay_id = e.id and frs.review_interval >= interval '24 hours')
      as progress_established,
  (select count(*)
     from essaycards.flashcards f
     join essaycards.flashcard_review_state frs on frs.flashcard_id = f.id
     where f.essay_id = e.id and frs.next_due_at <= now())
      as open_count,
  lp.cards_seen_count, lp.cards_future_safe_count,
  lp.milestone_all_cards_seen, lp.milestone_all_cards_future_safe,
  lp.milestone_guided_passed, lp.milestone_unguided_passed,
  lp.guided_passed_at, lp.unguided_passed_at,
  (
    lp.milestone_all_cards_seen::int + lp.milestone_all_cards_future_safe::int
    + lp.milestone_guided_passed::int + lp.milestone_unguided_passed::int
  ) as learning_level
from essaycards.essays e
{_learning_progress_subquery_sql()}
order by e.category asc nulls last, e.sort_index asc, e.created_at asc
"""


@router.get("", response_model=None)
def list_essays() -> JSONResponse:
    """No parameters. The roadmap view.

    Ordering (R-CON-AL-01): (category asc nulls last, sort_index asc, created_at
    asc) so the overview page renders the essays grouped by topic and in
    author-assigned sequence without re-sorting. Empty result is valid.

    Each row carries, beyond id/title/slug/category/sort_index/status, three
    pre-existing knowledge indicators plus the nine Sprint12 learning-progress
    fields (all computed against Postgres now() at query time — R-CON-AL-06):
      - progress_total (int)       — every flashcard in the essay.
      - progress_established (int) — those whose review_interval >= 24h.
      - open_count (int)           — those whose next_due_at <= now() (the
                                     existing `open` definition; NOT gated on
                                     established — a focus session would surface
                                     exactly this many).
      - cards_seen_count / cards_future_safe_count (int) — see
        _learning_progress_subquery_sql.
      - milestone_all_cards_seen / milestone_all_cards_future_safe /
        milestone_guided_passed / milestone_unguided_passed (bool) — the four
        independently-gated learning milestones.
      - guided_passed_at / unguided_passed_at (ISO str | null) — present only
        when the corresponding milestone is true.
      - learning_level (int, 0-4) — count of the four milestones that are true.
    Topic-level progress / open count are not returned — the client sums the
    per-essay counts of a topic's rows.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(_OVERVIEW_QUERY)
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
        **{"schema": ESSAY_OVERVIEW_SCHEMA},
        rows=rows,
    )
    return _dataset_response(dataset)


@router.get("/{essay_id}", response_model=None)
def get_essay(essay_id: str) -> JSONResponse:
    """Single essay with its ordered sections embedded on the returned row.

    Sprint12_FSRSAndUXOverhaul: now also carries the same nine derived
    learning-progress fields as GET /essays (see _learning_progress_subquery_sql
    — computed by the identical shared SQL fragment, R-CON-BP-09).

    404 ApiError if essay_id does not exist. An essay with zero sections is
    valid and returns sections: [].
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select
                  e.id, e.title, e.slug, e.category, e.sort_index, e.status,
                  e.main_spine_markdown, e.created_at, e.updated_at,
                  lp.cards_seen_count, lp.cards_future_safe_count,
                  lp.milestone_all_cards_seen, lp.milestone_all_cards_future_safe,
                  lp.milestone_guided_passed, lp.milestone_unguided_passed,
                  lp.guided_passed_at, lp.unguided_passed_at,
                  (
                    lp.milestone_all_cards_seen::int + lp.milestone_all_cards_future_safe::int
                    + lp.milestone_guided_passed::int + lp.milestone_unguided_passed::int
                  ) as learning_level
                from essaycards.essays e
                {_learning_progress_subquery_sql()}
                where e.id = %s
                """,
                (essay_id,),
            )
            essay_row = cur.fetchone()
            if not essay_row:
                return api_error("NOT_FOUND", f"Essay {essay_id} not found", status=404)
            row = _row_to_dict(essay_row)
            row["main_spine_nuggets"] = _main_spine_nuggets(cur, essay_row["main_spine_markdown"])

            cur.execute(
                """
                select id, heading, anchor_slug, order_index, body_markdown, created_at, updated_at
                from essaycards.essay_sections
                where essay_id = %s
                order by order_index asc
                """,
                (essay_id,),
            )
            section_rows = cur.fetchall()
            nuggets_by_section = _nuggets_by_section(cur, [str(r["id"]) for r in section_rows])
            sections = []
            for r in section_rows:
                d = _section_row_to_dict(r)
                d["nuggets"] = nuggets_by_section.get(d["id"], [])
                sections.append(d)
            row["sections"] = sections

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


@router.get("/{essay_id}/questions", response_model=None)
def list_essay_questions(essay_id: str) -> JSONResponse:
    """
    Every flashcard in this essay, flat, each row carrying its section's
    identity/order — the question-overview screen groups section -> level
    client-side from this, the same way EssayListView groups essays by
    category from a flat GET /essays row list (R-CON-BP-06 pattern fidelity;
    Datasets are flat by contract, R-CON-BP-04).

    Ordering (R-CON-AL-01): (section order_index asc, level asc, created_at
    asc) — sections in essay order; within a section, questions grouped by
    level ascending; created_at asc as the stable tiebreaker within a level
    (there is no question sort_index in this sprint — see
    Sprint08_QuestionLevelsAndStructure/00_draft.md). No parameters. Time
    basis: not applicable (no time-dependent filtering). 404 if essay_id does
    not exist. An essay with no cards returns rows: [].
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select 1 from essaycards.essays where id = %s", (essay_id,))
            if not cur.fetchone():
                return api_error("NOT_FOUND", f"Essay {essay_id} not found", status=404)

            cur.execute(
                """
                select f.id, f.card_key, f.question, f.answer, f.level, f.nugget_id,
                       f.section_id, s.anchor_slug as section_anchor_slug,
                       s.heading as section_heading, s.order_index as section_order_index
                from essaycards.flashcards f
                join essaycards.essay_sections s on s.id = f.section_id
                where f.essay_id = %s
                order by s.order_index asc, f.level asc, f.created_at asc
                """,
                (essay_id,),
            )
            question_rows = cur.fetchall()
            nuggets_by_section = _nuggets_by_section(
                cur, list({str(r["section_id"]) for r in question_rows})
            )
            rows = []
            for r in question_rows:
                d = dict(r)
                d["id"] = str(d["id"])
                d["section_id"] = str(d["section_id"])
                d["nugget_id"] = str(d["nugget_id"]) if d.get("nugget_id") else None
                d["section_nuggets"] = nuggets_by_section.get(d["section_id"], [])
                rows.append(d)

    dataset = Dataset(
        meta=DatasetMeta(
            object_type="question",
            label="Questions",
            total=len(rows),
            page=1,
            page_size=max(len(rows), 1),
            row_actions=[],
        ),
        **{"schema": QUESTION_SCHEMA},
        rows=rows,
    )
    return _dataset_response(dataset)


def _ordered_sections_with_cards(cur: Any, essay_id: str) -> list[dict[str, Any]]:
    """
    Every section of essay_id, in current order, each carrying its own
    cards — the common body of an ingest-shaped export package, shared by
    export_section (adds focus_section_id) and export_essay (no focus).
    Cards are exported as {id, q, a} only — deliberately NOT `level`: level
    is exclusively a POST /flashcards/upsert concern (see schema.sql), and
    POST /essays/ingest's card schema has no level field to read, so it can
    never be reset by an essay/section re-ingest. Read-only — issues no
    writes. Caller has already confirmed essay_id exists.
    """
    cur.execute(
        "select id, anchor_slug, heading, body_markdown "
        "from essaycards.essay_sections where essay_id = %s order by order_index asc",
        (essay_id,),
    )
    section_rows = cur.fetchall()

    cur.execute(
        "select section_id, card_key, question, answer from essaycards.flashcards "
        "where essay_id = %s order by created_at asc",
        (essay_id,),
    )
    cards_by_section: dict[str, list[dict[str, str]]] = {}
    for r in cur.fetchall():
        cards_by_section.setdefault(str(r["section_id"]), []).append(
            {"id": r["card_key"], "q": r["question"], "a": r["answer"]}
        )

    nuggets_by_section = _nuggets_by_section(cur, [str(r["id"]) for r in section_rows])

    return [
        {
            "section_id": str(r["id"]),
            "heading": r["heading"],
            "anchor_slug": r["anchor_slug"],
            "body_markdown": r["body_markdown"],
            "cards": cards_by_section.get(str(r["id"]), []),
            "nuggets": nuggets_by_section.get(str(r["id"]), []),
        }
        for r in section_rows
    ]


@router.get("/{essay_id}/export", response_model=None)
def export_essay(essay_id: str) -> JSONResponse:
    """
    Self-contained JSON export of ONE essay's full current content, shaped
    as a valid POST /ingest payload —
    title/slug/category/sort_index/status plus every section (each carrying
    its own heading/anchor_slug/body_markdown/cards), in current order.
    Reimports through the existing POST /essays/ingest via "Add / Update
    Essay" — there is no separate import endpoint. Because ingest is already
    scoped to exactly one essay per call (one `slug` per payload), importing
    this package can never touch any other essay
    (Sprint08_QuestionLevelsAndStructure/00_draft.md §6).

    Sibling of GET /essays/{essay_id}/sections/{section_id}/export (shares
    _ordered_sections_with_cards) minus `focus_section_id` — this variant is
    for "revise however many sections I direct" rather than one named
    section; ESSAY_EXPORT_PROMPT_INTRO (src/ShellEntry.tsx) instructs the
    external LLM to leave any section it wasn't asked to touch exactly as
    given, in the same order, for the same order_index reason documented on
    export_section.

    Bespoke JSON, not a Dataset — R-CON-BP-04 exemption, same rationale as
    GET /essays/{essay_id}/examination-package.

    404 ApiError if essay_id does not exist.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select title, slug, category, sort_index, status, main_spine_markdown "
                "from essaycards.essays where id = %s",
                (essay_id,),
            )
            essay_row = cur.fetchone()
            if not essay_row:
                return api_error("NOT_FOUND", f"Essay {essay_id} not found", status=404)

            sections = _ordered_sections_with_cards(cur, essay_id)
            main_spine_nuggets = _main_spine_nuggets(cur, essay_row["main_spine_markdown"])

    package = {
        "export_version": 1,
        "title": essay_row["title"],
        "slug": essay_row["slug"],
        "category": essay_row["category"],
        "sort_index": essay_row["sort_index"],
        "status": essay_row["status"],
        "main_spine_markdown": essay_row["main_spine_markdown"],
        "main_spine_nuggets": main_spine_nuggets,
        "sections": sections,
    }
    return JSONResponse(content=package)


@router.get("/{essay_id}/sections/{section_id}/export", response_model=None)
def export_section(essay_id: str, section_id: str) -> JSONResponse:
    """
    Self-contained JSON export of the essay's FULL current section list (not
    just section_id), shaped as a valid POST /ingest payload —
    title/slug/category/sort_index/status plus every section (each carrying
    its own heading/anchor_slug/body_markdown/cards), in current order, plus
    `focus_section_id` naming which section_id the request was for.

    The export MUST carry every section, in order — POST /essays/ingest
    assigns each submitted section's order_index from its position in the
    `sections` array (backend.ingest._upsert_section /
    _validate_ingest_body's `"order_index": s_idx`), not from any value
    carried in the payload. A payload with only the target section would
    therefore always land it at order_index 0 on reimport, silently moving it
    to the front of the essay for any section past the first. Carrying the
    whole array at its current order means an unedited reply reproduces every
    section's existing order_index; the export/insert prompts built from this
    package (SECTION_EXPORT_PROMPT_INTRO / SECTION_INSERT_PROMPT_INTRO in
    src/ShellEntry.tsx) instruct the external LLM to return every entry but
    the one it was asked to change exactly as given, in the same order.

    Two frontend flows share this endpoint: "Export section" (revise
    section_id's own content in place) and "Insert section" (the frontend
    splices a blank-template new section into the array, immediately after
    section_id, before copying to the clipboard). Both reimport through the
    existing POST /essays/ingest via "Add / Update Essay" — there is no
    separate import endpoint for either.

    Bespoke JSON, not a Dataset — R-CON-BP-04 exemption on the same rationale
    as GET /essays/{essay_id}/examination-package (see module docstring in
    backend/routers/examinations.py): copied to the clipboard for an external
    LLM, not rendered by a Dataset-consuming UI component.

    Each section's `section_id` is an extra field for traceability only —
    POST /essays/ingest reads none of them (or `focus_section_id`, or
    `export_version`), so they round-trip harmlessly through an unedited
    reply.

    404 ApiError if essay_id does not exist, or if section_id does not exist
    under this essay.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select title, slug, category, sort_index, status, main_spine_markdown "
                "from essaycards.essays where id = %s",
                (essay_id,),
            )
            essay_row = cur.fetchone()
            if not essay_row:
                return api_error("NOT_FOUND", f"Essay {essay_id} not found", status=404)

            sections = _ordered_sections_with_cards(cur, essay_id)
            if not any(s["section_id"] == section_id for s in sections):
                return api_error(
                    "NOT_FOUND", f"Section {section_id} not found in essay {essay_id}", status=404
                )

            main_spine_nuggets = _main_spine_nuggets(cur, essay_row["main_spine_markdown"])

            # focus_section_nuggets: FULL {nugget_key, title, body_markdown} for
            # every nugget currently referenced by the focus section only —
            # richer than the light {nugget_key, title} pairs every section in
            # `sections` also carries via _ordered_sections_with_cards.
            cur.execute(
                """
                select n.nugget_key, n.title, n.body_markdown
                from essaycards.section_nuggets sn
                join essaycards.nuggets n on n.id = sn.nugget_id
                where sn.section_id = %s
                order by n.title asc
                """,
                (section_id,),
            )
            focus_section_nuggets = [
                {"nugget_key": r["nugget_key"], "title": r["title"], "body_markdown": r["body_markdown"]}
                for r in cur.fetchall()
            ]

    package = {
        "export_version": 2,
        "focus_section_id": section_id,
        "title": essay_row["title"],
        "slug": essay_row["slug"],
        "category": essay_row["category"],
        "sort_index": essay_row["sort_index"],
        "status": essay_row["status"],
        "main_spine_markdown": essay_row["main_spine_markdown"],
        "main_spine_nuggets": main_spine_nuggets,
        "focus_section_nuggets": focus_section_nuggets,
        "sections": sections,
    }
    return JSONResponse(content=package)


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
    if not SLUG_LIKE_RE.match(slug):
        return None, api_error("VALIDATION_ERROR", f"slug '{slug}' must match ^[a-zA-Z0-9_-]+$")

    # Optional overview-page grouping metadata. category is free text (no fixed
    # set); sort_index orders the essay within its category group.
    category = body.get("category")
    if category is not None:
        if not isinstance(category, str) or not category.strip():
            return None, api_error(
                "VALIDATION_ERROR", "category, if present, must be a non-empty string"
            )
        category = category.strip()

    sort_index = body.get("sort_index", 0)
    if isinstance(sort_index, bool) or not isinstance(sort_index, int):
        return None, api_error(
            "VALIDATION_ERROR", "sort_index, if present, must be an integer"
        )

    status = body.get("status", DEFAULT_ESSAY_STATUS)
    if status not in VALID_ESSAY_STATUSES:
        return None, api_error(
            "VALIDATION_ERROR",
            f"status, if present, must be one of: {', '.join(VALID_ESSAY_STATUSES)}",
        )

    # Optional top-level main spine narrative (Sprint09_Nuggets). Default ''
    # on omission, same optional-key convention as category/sort_index/status.
    # Stored verbatim, not stripped — same convention as body_markdown.
    main_spine_markdown = body.get("main_spine_markdown", "")
    if not isinstance(main_spine_markdown, str):
        return None, api_error(
            "VALIDATION_ERROR", "main_spine_markdown, if present, must be a string"
        )

    # Optional full-package nuggets (Sprint09_Nuggets follow-up): lets one
    # payload define the nuggets a fresh essay's [[nugget:key]] references
    # need, instead of requiring a separate POST /nuggets/upsert call per
    # nugget before this one. Same field rules as POST /nuggets/upsert
    # (backend/routers/nuggets.py) — upserted in upsert_document before
    # reference resolution, so a key defined here is immediately resolvable
    # by this same payload's main_spine_markdown/sections.
    nuggets_raw = body.get("nuggets", [])
    if not isinstance(nuggets_raw, list):
        return None, api_error("VALIDATION_ERROR", "nuggets, if present, must be a list")

    nuggets: list[dict[str, Any]] = []
    seen_nugget_keys: set[str] = set()
    for n_idx, nugget_raw in enumerate(nuggets_raw):
        if not isinstance(nugget_raw, dict):
            return None, api_error("VALIDATION_ERROR", f"nuggets[{n_idx}] must be an object")

        nugget_key = nugget_raw.get("nugget_key")
        if not isinstance(nugget_key, str) or not nugget_key.strip():
            return None, api_error(
                "VALIDATION_ERROR", f"nuggets[{n_idx}].nugget_key is required and must be a non-empty string"
            )
        nugget_key = nugget_key.strip()
        if not SLUG_LIKE_RE.match(nugget_key):
            return None, api_error(
                "VALIDATION_ERROR", f"nuggets[{n_idx}].nugget_key '{nugget_key}' must match ^[a-zA-Z0-9_-]+$"
            )
        if nugget_key in seen_nugget_keys:
            return None, api_error("VALIDATION_ERROR", f"duplicate nugget_key '{nugget_key}' in payload")
        seen_nugget_keys.add(nugget_key)

        nugget_title = nugget_raw.get("title")
        if not isinstance(nugget_title, str) or not nugget_title.strip():
            return None, api_error(
                "VALIDATION_ERROR", f"nuggets[{n_idx}].title is required and must be a non-empty string"
            )
        nugget_title = nugget_title.strip()

        nugget_body_markdown = nugget_raw.get("body_markdown", "")
        if not isinstance(nugget_body_markdown, str):
            return None, api_error(
                "VALIDATION_ERROR", f"nuggets[{n_idx}].body_markdown, if present, must be a string"
            )

        nuggets.append({
            "nugget_key": nugget_key,
            "title": nugget_title,
            "body_markdown": nugget_body_markdown,
        })

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
        if not SLUG_LIKE_RE.match(anchor_slug):
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
            if not SLUG_LIKE_RE.match(card_id):
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

    doc = {
        "title": title,
        "slug": slug,
        "category": category,
        "sort_index": sort_index,
        "status": status,
        "main_spine_markdown": main_spine_markdown,
        "nuggets": nuggets,
        "sections": sections,
    }
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

        try:
            summary = upsert_document(conn, doc)
        except IngestionError as exc:
            return api_error("VALIDATION_ERROR", str(exc))

    return JSONResponse(content={
        "essay_id": summary.essay_id,
        "slug": doc["slug"],
        "nuggets_created": summary.nuggets_created,
        "nuggets_updated": summary.nuggets_updated,
        "sections_created": summary.sections_created,
        "sections_updated": summary.sections_updated,
        "cards_created": summary.flashcards_created,
        "cards_updated": summary.flashcards_updated,
    })
