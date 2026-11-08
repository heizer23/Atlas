"""Persist route progress / ghost profile for a run (derived data; replaced on every recompute)."""

from psycopg2.extras import Json

from backend.config import PROGRESS_ALGO_VERSION
from backend.ghost import build_progress


def recompute_progress(conn, run_id: str) -> None:
    """Recompute the run's progress on its route. No route / not complete -> any stored row is removed."""
    with conn.cursor() as cur:
        cur.execute(
            """
            select r.status, r.started_at, r.route_id, rt.geometry, rt.geometry_version
            from runningtracker.runs r left join runningtracker.routes rt on rt.id = r.route_id
            where r.id = %s
            """,
            (run_id,),
        )
        run = cur.fetchone()
        if run is None or run["route_id"] is None or run["status"] != "complete" or run["started_at"] is None:
            cur.execute("delete from runningtracker.run_route_progress where run_id = %s", (run_id,))
            return
        cur.execute("select stream, sample_ts, payload from runningtracker.run_samples where run_id = %s order by seq", (run_id,))
        fixes, hrs = [], []
        for s in cur.fetchall():
            p = s["payload"]
            if s["stream"] == "location" and p.get("latitude") is not None and p.get("longitude") is not None:
                fixes.append((s["sample_ts"], p["latitude"], p["longitude"], p.get("accuracyMeters")))
            elif s["stream"] == "heart_rate" and isinstance(p.get("bpm"), (int, float)):
                hrs.append((s["sample_ts"], p["bpm"]))
        cur.execute("select started_at, ended_at from runningtracker.run_pauses where run_id = %s", (run_id,))
        pauses = [(r["started_at"], r["ended_at"]) for r in cur.fetchall()]
        res = build_progress(run["geometry"], fixes, hrs, pauses, run["started_at"])
        cur.execute(
            """
            insert into runningtracker.run_route_progress
                (run_id, route_id, geometry_version, algo_version, qualified, reason, end_progress_m, coverage,
                 matched_fixes, off_course_fixes, profile, computed_at)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            on conflict (run_id) do update set
                route_id = excluded.route_id, geometry_version = excluded.geometry_version,
                algo_version = excluded.algo_version, qualified = excluded.qualified, reason = excluded.reason,
                end_progress_m = excluded.end_progress_m, coverage = excluded.coverage,
                matched_fixes = excluded.matched_fixes, off_course_fixes = excluded.off_course_fixes,
                profile = excluded.profile, computed_at = excluded.computed_at
            """,
            (run_id, run["route_id"], run["geometry_version"], PROGRESS_ALGO_VERSION, res.qualified, res.reason,
             res.end_progress_m, res.coverage, res.matched, res.off_course, Json(res.profile)),
        )


def resolve_ghost(conn, route_id: str, selector: str) -> str | None:
    """none -> None; latest / fastest / <run id> -> a concrete qualified run on the route, else ValueError(reason).
    latest = newest started_at; fastest = lowest moving_s (any run type)."""
    if selector == "none":
        return None
    with conn.cursor() as cur:
        if selector in ("latest", "fastest"):
            order = "r.started_at desc" if selector == "latest" else "r.moving_s asc nulls last, r.started_at desc"
            cur.execute(
                f"""
                select r.id from runningtracker.runs r
                join runningtracker.run_route_progress p on p.run_id = r.id and p.qualified
                where r.route_id = %s and r.status = 'complete' order by {order} limit 1
                """,
                (route_id,),
            )
        else:
            cur.execute(
                """
                select r.id from runningtracker.runs r
                join runningtracker.run_route_progress p on p.run_id = r.id and p.qualified
                where r.id = %s and r.route_id = %s and r.status = 'complete'
                """,
                (selector, route_id),
            )
        row = cur.fetchone()
    if row is None:
        raise ValueError("no_eligible_ghost")
    return str(row["id"])
