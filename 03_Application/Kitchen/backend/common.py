from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi.responses import JSONResponse

from platform_contracts import ColumnSchema, Dataset, DatasetMeta

BERLIN = ZoneInfo("Europe/Berlin")


def berlin_today() -> date:
    return datetime.now(BERLIN).date()


def plain(v: Any) -> Any:
    """Make DB values JSON-safe: Decimal -> int/float, date/uuid -> str, recurse containers."""
    if isinstance(v, Decimal):
        f = float(v)
        return int(f) if f.is_integer() else round(f, 4)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [plain(x) for x in v]
    if isinstance(v, UUID):
        return str(v)
    return v


def dataset_response(object_type: str, rows: list[dict[str, Any]], label: str | None = None,
                     status: int = 200) -> JSONResponse:
    """Dataset envelope; nested values stay inside rows and are rendered by Kitchen's own views."""
    rows = [plain(r) for r in rows]
    keys = list(rows[0].keys()) if rows else []
    ds = Dataset(
        meta=DatasetMeta(object_type=object_type, label=label or object_type, total=len(rows),
                         page=1, page_size=max(len(rows), 1), row_actions=[]),
        **{"schema": [ColumnSchema(key=k, label=k, type="string") for k in keys]},
        rows=rows,
    )
    return JSONResponse(status_code=status, content=ds.model_dump(by_alias=True, mode="json"))
