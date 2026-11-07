"""Publish Kitchen's gross demand to StorageTracker (the central shopping list lives there).

Kitchen never deducts stock and never computes a buy quantity: it sends the complete current snapshot of raw-ingredient
demand (service.compute_demand) and StorageTracker nets it. The outcome of every attempt is stored in
kitchen.demand_sync so failures are visible (GET /kitchen/demand/status) and safely retryable (POST /kitchen/demand/sync):
a snapshot is idempotent and replaces the previous one atomically, so retrying never duplicates anything.

sync_quietly() is called after plan/recipe/cook changes and at startup; it never raises, so a StorageTracker outage
cannot break planning or the Cook/Eat/Undo flows.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

from backend import service
from backend import storage_client as st
from backend.database import get_db

log = logging.getLogger("kitchen")

_LOCK_KEY = "kitchen:demand_sync"


def sync_demand() -> dict[str, Any]:
    """One full compute + publish attempt. Serialized across requests by an advisory lock, so a slow older snapshot
    can never overwrite a newer one. Always returns the stored status (never raises)."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("select pg_advisory_xact_lock(hashtext(%s))", (_LOCK_KEY,))
            lines: list[dict[str, Any]] = []
            issues: list[dict[str, Any]] = []
            try:
                lines, issues = service.compute_demand(conn)
                res = st.put_demands(lines)
                _record(conn, "ok", line_count=len(lines), issues=issues, snapshot_hash=res.get("snapshot_hash"))
            except st.DemandRejected as e:
                log.warning("Demand snapshot rejected: %s", e)
                _record(conn, "error", error=str(e), problems=e.problems, issues=issues)
            except Exception as e:  # noqa: BLE001 - storage down, bad token, bug: always recorded, never raised
                log.warning("Demand sync failed: %s", e)
                _record(conn, "error", error=str(e), issues=issues)
            conn.commit()
    except Exception as e:  # noqa: BLE001 - even the bookkeeping failed (DB down)
        log.error("Demand sync bookkeeping failed: %s", e)
    return get_status()


def sync_quietly() -> None:
    sync_demand()


def sync_at_startup(attempts: int = 8, delay: float = 5.0) -> None:
    """Recovery after (re)start: push the current snapshot once StorageTracker answers. Runs in the background."""
    def run() -> None:
        for _ in range(attempts):
            if sync_demand()["status"] == "ok":
                return
            time.sleep(delay)
    threading.Thread(target=run, name="kitchen-demand-sync", daemon=True).start()


def _record(conn: Any, status: str, *, line_count: int = 0, issues: list[dict[str, Any]] | None = None,
            snapshot_hash: str | None = None, error: str | None = None,
            problems: list[dict[str, Any]] | None = None) -> None:
    with conn.cursor() as cur:
        if status == "ok":
            cur.execute(
                """update kitchen.demand_sync set status = 'ok', last_attempt_at = now(), last_ok_at = now(),
                          last_error = null, problems = '[]'::jsonb, issues = %s::jsonb, line_count = %s,
                          snapshot_hash = %s where id""",
                (json.dumps(issues or []), line_count, snapshot_hash))
        else:
            # line_count / snapshot_hash keep describing the last ACCEPTED snapshot (what Storage still holds)
            cur.execute(
                """update kitchen.demand_sync set status = 'error', last_attempt_at = now(), last_error = %s,
                          problems = %s::jsonb, issues = %s::jsonb where id""",
                (error, json.dumps((problems or [])[:50]), json.dumps(issues or [])))


def get_status() -> dict[str, Any]:
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("select * from kitchen.demand_sync where id")
                row = cur.fetchone()
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "last_error": f"Kitchen database unavailable: {e}", "problems": [], "issues": [],
                "line_count": 0, "last_attempt_at": None, "last_ok_at": None}
    d = dict(row)
    d.pop("id", None)
    d.pop("snapshot_hash", None)
    return d
