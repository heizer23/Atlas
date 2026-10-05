"""
GET /progress/sections — one derived traffic-light row per section
(Sprint14_SectionProgressionAndRevalidation). Read endpoint -> Dataset
(R-CON-BP-04). All state logic lives in backend/progress.py.

Query behavior (R-CON-AL-01): optional essay_id; no essay_id -> every section
of every essay. Ordering: essays.category asc nulls last, essays.sort_index
asc, essays.created_at asc, essay_sections.order_index asc. Flat rows (client
groups by essay_id). No sections / unknown essay_id -> empty Dataset, not an
error. The state depends only on stored oral state and review_interval, not
on the clock.
"""

import uuid
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.database import get_db
from backend.progress import section_progress_sql
from platform_contracts import ColumnSchema, Dataset, DatasetMeta

router = APIRouter(tags=["progress"])

SECTION_PROGRESS_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="section_id",           label="Section",          type="string",  sortable=False, filterable=True),
    ColumnSchema(key="essay_id",             label="Essay",            type="string",  sortable=False, filterable=True),
    ColumnSchema(key="heading",              label="Section title",    type="string",  sortable=False, filterable=False),
    ColumnSchema(key="anchor_slug",          label="Anchor",           type="string",  sortable=False, filterable=False),
    ColumnSchema(key="order_index",          label="Section order",    type="number",  sortable=True,  filterable=False),
    ColumnSchema(key="state",                label="State",            type="string",  sortable=False, filterable=True),
    ColumnSchema(key="next_step",            label="Next step",        type="string",  sortable=False, filterable=False),
    ColumnSchema(key="guided_passed",        label="Guided passed",    type="boolean", sortable=False, filterable=False),
    ColumnSchema(key="unguided_passed",      label="Unguided passed",  type="boolean", sortable=False, filterable=False),
    ColumnSchema(key="guided_pass_source",   label="Guided pass source", type="string", sortable=False, filterable=False),
    ColumnSchema(key="guided_latest_score",  label="Guided score",     type="number",  sortable=False, filterable=False),
    ColumnSchema(key="unguided_latest_score", label="Unguided score",  type="number",  sortable=False, filterable=False),
    ColumnSchema(key="guided_passed_at",     label="Guided passed on", type="date",    sortable=False, filterable=False),
    ColumnSchema(key="unguided_passed_at",   label="Unguided passed on", type="date",  sortable=False, filterable=False),
    ColumnSchema(key="cards_total",          label="Cards",            type="number",  sortable=False, filterable=False),
    ColumnSchema(key="cards_established",    label="Established",      type="number",  sortable=False, filterable=False),
    ColumnSchema(key="is_locked",            label="Locked",           type="boolean", sortable=False, filterable=False),
]


def _dataset_response(dataset: Dataset) -> JSONResponse:
    return JSONResponse(content=dataset.model_dump(by_alias=True, mode="json"))


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


@router.get("/progress/sections", response_model=None)
def list_section_progress(essay_id: str | None = None) -> JSONResponse:
    rows: list[dict[str, Any]] = []
    if essay_id is None or _is_uuid(essay_id):
        where = "where e.id = %s" if essay_id else ""
        params = (essay_id,) if essay_id else ()
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    {section_progress_sql()}
                    {where}
                    order by e.category asc nulls last, e.sort_index asc, e.created_at asc,
                             s.order_index asc
                    """,
                    params,
                )
                for r in cur.fetchall():
                    d = dict(r)
                    d["section_id"] = str(d["section_id"])
                    d["essay_id"] = str(d["essay_id"])
                    for k in ("guided_passed_at", "unguided_passed_at"):
                        if d.get(k):
                            d[k] = d[k].isoformat()
                    rows.append(d)

    dataset = Dataset(
        meta=DatasetMeta(
            object_type="section_progress",
            label="Section Progress",
            total=len(rows),
            page=1,
            page_size=max(len(rows), 1),
            row_actions=[],
        ),
        **{"schema": SECTION_PROGRESS_SCHEMA},
        rows=rows,
    )
    return _dataset_response(dataset)
