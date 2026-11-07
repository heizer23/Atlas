"""Internal demand sync (service-to-service). Kitchen publishes its complete current GROSS demand; Storage nets it.

Contract
- PUT  /api/internal/demands/{source}          replace the source's complete snapshot, atomically.
- GET  /api/internal/demands/{source}          current stored lines.
- GET  /api/internal/demands/{source}/status   last accepted snapshot + last rejected attempt (actionable errors).
- Auth: header `X-Atlas-Service-Token` must equal env ATLAS_SERVICE_TOKEN (fail closed when unset). These paths are
  not proxied by the Atlas Shell nginx: they are reachable only inside the Docker network / on the loopback port.
- Only rows of `{source}` are ever touched; other sources, manual shopping tasks and stock are never affected.
- Any invalid line rejects the WHOLE snapshot (422 with one entry per problem); the previous snapshot stays valid and
  the rejection is recorded in demand_sync.last_error. Identical re-sends change nothing (idempotent).
- Demand is not a stock movement.

Line: {ref: str (stable, unique per source), item_id: int, qty: number > 0, unit: str (= article base unit),
       required_date?: YYYY-MM-DD, label?: str}
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from datetime import date
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.database import get_db
from platform_errorhandling import api_error

router = APIRouter(prefix="/internal/demands", tags=["demands"])

SOURCE_RE = re.compile(r"^[a-z][a-z0-9_-]{1,30}$")
MAX_LINES = 5000


def _auth(request: Request) -> JSONResponse | None:
    expected = os.environ.get("ATLAS_SERVICE_TOKEN", "")
    if not expected:
        return api_error("SERVICE_TOKEN_NOT_CONFIGURED",
                         "ATLAS_SERVICE_TOKEN is not set on StorageTracker; internal endpoints are disabled", status=503)
    given = request.headers.get("X-Atlas-Service-Token", "")
    if not hmac.compare_digest(given.encode(), expected.encode()):
        return api_error("UNAUTHORIZED", "Missing or invalid X-Atlas-Service-Token", status=401)
    return None


def _norm(s: str) -> str:
    return " ".join(s.strip().lower().split())


def _problem(index: int | None, ref: Any, field: str, message: str) -> dict[str, Any]:
    return {"index": index, "ref": ref, "field": field, "message": message}


def validate_payload(body: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Shape validation only (no DB). Returns (clean lines, problems)."""
    problems: list[dict[str, Any]] = []
    if not isinstance(body, dict) or not isinstance(body.get("lines"), list):
        return [], [_problem(None, None, "lines", 'body must be a JSON object {"lines": [ ... ]}')]
    if len(body["lines"]) > MAX_LINES:
        return [], [_problem(None, None, "lines", f"at most {MAX_LINES} lines per snapshot")]
    clean: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, raw in enumerate(body["lines"]):
        if not isinstance(raw, dict):
            problems.append(_problem(i, None, "line", "each line must be an object"))
            continue
        ref = raw.get("ref")
        n0 = len(problems)
        if not isinstance(ref, str) or not ref.strip() or len(ref) > 200:
            problems.append(_problem(i, ref, "ref", "ref must be a non-empty string (max 200 chars)"))
        elif ref in seen:
            problems.append(_problem(i, ref, "ref", "duplicate ref within the snapshot"))
        else:
            seen.add(ref)
        item_id = raw.get("item_id")
        if isinstance(item_id, bool) or not isinstance(item_id, int):
            problems.append(_problem(i, ref, "item_id", "item_id must be an integer article number"))
        qty = raw.get("qty")
        if isinstance(qty, bool) or not isinstance(qty, (int, float)) or qty != qty or qty in (float("inf"), float("-inf")):
            problems.append(_problem(i, ref, "qty", "qty must be a number"))
        elif qty <= 0:
            problems.append(_problem(i, ref, "qty", f"qty must be > 0 (got {qty}); omit lines without demand"))
        unit = raw.get("unit")
        if not isinstance(unit, str) or not unit.strip():
            problems.append(_problem(i, ref, "unit", "unit must be a non-empty string"))
        req = raw.get("required_date")
        req_date = None
        if req is not None:
            try:
                req_date = date.fromisoformat(req)
            except (TypeError, ValueError):
                problems.append(_problem(i, ref, "required_date", "required_date must be YYYY-MM-DD or null"))
        label = raw.get("label")
        if label is not None and not isinstance(label, str):
            problems.append(_problem(i, ref, "label", "label must be a string or null"))
        if len(problems) == n0:
            clean.append({"ref": ref, "item_id": item_id, "qty": qty, "unit": unit.strip(),
                          "required_date": req_date, "label": label})
    return clean, problems


def validate_items(cur: Any, lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every line must reference an active purchasable article whose base unit matches (never converted)."""
    ids = sorted({l["item_id"] for l in lines})
    cur.execute("select id, name, unit, kind, archived_at from storagetracker.items where id = any(%s)", (ids or [0],))
    items = {r["id"]: r for r in cur.fetchall()}
    problems = []
    for i, l in enumerate(lines):
        it = items.get(l["item_id"])
        if it is None:
            problems.append(_problem(i, l["ref"], "item_id", f"article {l['item_id']} does not exist"))
        elif it["kind"] != "ingredient":
            problems.append(_problem(i, l["ref"], "item_id",
                                     f"article {l['item_id']} ({it['name']}) is a cooked batch, not a purchasable SKU"))
        elif it["archived_at"] is not None:
            problems.append(_problem(i, l["ref"], "item_id", f"article {l['item_id']} ({it['name']}) is archived"))
        elif it["unit"] is not None and _norm(it["unit"]) != _norm(l["unit"]):
            problems.append(_problem(i, l["ref"], "unit",
                                     f"unit '{l['unit']}' does not match article {l['item_id']} ({it['name']}) "
                                     f"base unit '{it['unit']}' (no conversion)"))
    return problems


def snapshot_hash(lines: list[dict[str, Any]]) -> str:
    canon = sorted(
        ({"ref": l["ref"], "item_id": l["item_id"], "qty": float(l["qty"]), "unit": _norm(l["unit"]),
          "required_date": l["required_date"].isoformat() if l["required_date"] else None, "label": l["label"]}
         for l in lines), key=lambda x: x["ref"])
    return hashlib.sha256(json.dumps(canon, sort_keys=True).encode()).hexdigest()


def _record_rejection(source: str, problems: list[dict[str, Any]]) -> None:
    """Own transaction: the rejected snapshot rolls back, the rejection record must survive."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """insert into storagetracker.demand_sync (source, last_error, last_error_at)
                   values (%s, %s::jsonb, now())
                   on conflict (source) do update set last_error = excluded.last_error, last_error_at = now()""",
                (source, json.dumps(problems[:50])))
        conn.commit()


@router.put("/{source}", response_model=None)
async def replace_snapshot(source: str, request: Request) -> JSONResponse:
    if (denied := _auth(request)):
        return denied
    if not SOURCE_RE.match(source):
        return api_error("VALIDATION_ERROR", "source must match [a-z][a-z0-9_-]{1,30}")
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = None
    lines, problems = validate_payload(body)
    if not problems:
        with get_db() as conn:
            with conn.cursor() as cur:
                problems = validate_items(cur, lines)
    if problems:
        _record_rejection(source, problems)
        return api_error("DEMAND_SNAPSHOT_REJECTED",
                         f"Snapshot rejected ({len(problems)} problem(s)); previous demand for '{source}' is unchanged",
                         detail=problems[:50], status=422)

    digest = snapshot_hash(lines)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select pg_advisory_xact_lock(hashtext(%s))", (f"demands:{source}",))
            # re-validate under the lock: an article may have been deleted/archived since the check above
            late = validate_items(cur, lines)
            if late:
                conn.rollback()
                _record_rejection(source, late)
                return api_error("DEMAND_SNAPSHOT_REJECTED",
                                 f"Snapshot rejected ({len(late)} problem(s)); previous demand for '{source}' is unchanged",
                                 detail=late[:50], status=422)
            cur.execute("select snapshot_hash from storagetracker.demand_sync where source = %s", (source,))
            prev = cur.fetchone()
            changed = prev is None or prev["snapshot_hash"] != digest
            refs = [l["ref"] for l in lines]
            cur.execute("delete from storagetracker.demands where source = %s and external_ref <> all(%s)",
                        (source, refs or [""]))
            for l in lines:
                cur.execute(
                    """insert into storagetracker.demands (source, external_ref, item_id, qty, unit, required_date, label)
                       values (%s, %s, %s, %s, %s, %s, %s)
                       on conflict (source, external_ref) do update
                         set item_id = excluded.item_id, qty = excluded.qty, unit = excluded.unit,
                             required_date = excluded.required_date, label = excluded.label, updated_at = now()
                       where (storagetracker.demands.item_id, storagetracker.demands.qty, storagetracker.demands.unit,
                              storagetracker.demands.required_date, storagetracker.demands.label)
                             is distinct from (excluded.item_id, excluded.qty, excluded.unit,
                                               excluded.required_date, excluded.label)""",
                    (source, l["ref"], l["item_id"], l["qty"], l["unit"], l["required_date"], l["label"]))
            cur.execute(
                """insert into storagetracker.demand_sync (source, snapshot_hash, line_count, last_ok_at, last_error, last_error_at)
                   values (%s, %s, %s, now(), null, null)
                   on conflict (source) do update
                     set snapshot_hash = excluded.snapshot_hash, line_count = excluded.line_count,
                         last_ok_at = now(), last_error = null, last_error_at = null""",
                (source, digest, len(lines)))
        conn.commit()
    return JSONResponse(content={"source": source, "line_count": len(lines), "changed": changed,
                                 "snapshot_hash": digest})


@router.get("/{source}/status", response_model=None)
def status(source: str, request: Request) -> JSONResponse:
    if (denied := _auth(request)):
        return denied
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select * from storagetracker.demand_sync where source = %s", (source,))
            row = cur.fetchone()
    if row is None:
        return JSONResponse(content={"source": source, "snapshot_hash": None, "line_count": 0, "last_ok_at": None,
                                     "last_error": None, "last_error_at": None})
    d = dict(row)
    for k in ("last_ok_at", "last_error_at"):
        d[k] = d[k].isoformat() if d.get(k) else None
    return JSONResponse(content=d)


@router.get("/{source}", response_model=None)
def list_lines(source: str, request: Request) -> JSONResponse:
    if (denied := _auth(request)):
        return denied
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select external_ref as ref, item_id, qty, unit, required_date, label "
                        "from storagetracker.demands where source = %s order by external_ref", (source,))
            rows = [dict(r) for r in cur.fetchall()]
    for r in rows:
        r["qty"] = float(r["qty"])
        r["required_date"] = r["required_date"].isoformat() if r["required_date"] else None
    return JSONResponse(content={"source": source, "rows": rows, "total": len(rows)})
