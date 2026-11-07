"""Net requirements for the central shopping list.

Kitchen (and later other sources) publish GROSS demand per article (`storagetracker.demands`). Storage owns the
procurement calculation:

    usable stock  = items.quantity, or 0 when the article's best-before date has passed (expired stock cannot be cooked)
    gross demand  = sum of all demands for the article, across sources (stock is subtracted ONCE, never per source)
    shortage      = max(0, gross demand - usable stock)
    purchase qty  = shortage, raised to min_purchase_qty, then rounded UP to a multiple of purchase_multiple

KANBAN articles carry no quantity: their demand is ignored, replenishment comes from their manual status (task).
Batches are never purchasable: they cannot appear in demands (rejected on sync).
"""
from __future__ import annotations

import math
from decimal import Decimal
from typing import Any


def _d(v: Any) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal(0)


def num(v: Decimal | float | int | None) -> int | float | None:
    """Integral values render as int (matches the rest of the API)."""
    if v is None:
        return None
    f = float(v)
    return int(f) if f.is_integer() else round(f, 4)


def round_purchase(shortage: Decimal, multiple: Any = None, minimum: Any = None) -> Decimal:
    """Smallest purchasable quantity >= shortage under the article's pack size / minimum order rule."""
    if shortage <= 0:
        return Decimal(0)
    qty = shortage
    if minimum is not None and qty < _d(minimum):
        qty = _d(minimum)
    if multiple is not None and _d(multiple) > 0:
        m = _d(multiple)
        qty = m * Decimal(math.ceil(qty / m))
    return qty


def build_shopping_list(conn: Any, today: Any) -> list[dict[str, Any]]:
    """One row per article that is either short (demand > usable stock) or has an open shopping task."""
    with conn.cursor() as cur:
        cur.execute(
            """
            select id, name, unit, quantity, expires_at, stock_management_type, purchase_multiple, min_purchase_qty,
                   category, source_tags, state, kind
            from storagetracker.items
            where archived_at is null and kind = 'ingredient'
            """
        )
        items = {r["id"]: dict(r) for r in cur.fetchall()}
        cur.execute(
            "select item_id, source, external_ref, qty, unit, required_date, label "
            "from storagetracker.demands order by required_date nulls last, source, external_ref"
        )
        demands = [dict(r) for r in cur.fetchall()]
        cur.execute(
            "select id, item_id, notes, origin, created_at from storagetracker.shopping_tasks "
            "where status = 'open' order by created_at"
        )
        tasks = {r["item_id"]: dict(r) for r in cur.fetchall()}
        # tasks of batches / archived items are not part of the purchasable list
        cur.execute("select id, name, unit, quantity, expires_at, stock_management_type, purchase_multiple, "
                    "min_purchase_qty, category, source_tags, state, kind from storagetracker.items "
                    "where id = any(%s)", (list(tasks.keys()) or [0],))
        for r in cur.fetchall():
            items.setdefault(r["id"], dict(r))

    by_item: dict[int, list[dict[str, Any]]] = {}
    for d in demands:
        by_item.setdefault(d["item_id"], []).append(d)

    rows: list[dict[str, Any]] = []
    for item_id in sorted(set(by_item) | set(tasks)):
        item = items.get(item_id)
        if item is None:
            continue
        kanban = item["stock_management_type"] == "KANBAN"
        lines = [] if kanban else by_item.get(item_id, [])
        stock = _d(item["quantity"])
        expired = item["expires_at"] is not None and item["expires_at"] < today
        usable = Decimal(0) if expired else stock
        gross = sum((_d(l["qty"]) for l in lines), Decimal(0))
        shortage = max(Decimal(0), gross - usable)
        task = tasks.get(item_id)
        if shortage <= 0 and task is None:
            continue
        purchase = round_purchase(shortage, item["purchase_multiple"], item["min_purchase_qty"])
        dates = [l["required_date"] for l in lines if l["required_date"]]
        origins = sorted({l["source"] for l in lines} if shortage > 0 else set())
        if task:
            origins.append(task["origin"])
        rows.append({
            "id": f"item-{item_id}",
            "item_id": item_id,
            "item_name": item["name"],
            "unit": item["unit"],
            "category": item["category"],
            "source_tags": item["source_tags"] or [],
            "stock_management_type": item["stock_management_type"],
            "state": item["state"],
            "stock": num(stock),
            "usable_stock": num(usable),
            "demand_qty": num(gross) if lines else None,
            "shortage": num(shortage) if shortage > 0 else None,
            "purchase_qty": num(purchase) if shortage > 0 else None,
            "needed_by": min(dates).isoformat() if dates else None,
            "origins": origins,
            "demands": [{"source": l["source"], "label": l["label"], "qty": num(l["qty"]),
                         "required_date": l["required_date"].isoformat() if l["required_date"] else None}
                        for l in lines] if shortage > 0 else [],
            "task_id": str(task["id"]) if task else None,
            "notes": task["notes"] if task else None,
        })
    rows.sort(key=lambda r: (r["needed_by"] is None, r["needed_by"] or "", r["item_name"].lower()))
    return rows
