"""Repository for the coach tables and the finish hook (Ghost Coach).

All functions take an open psycopg2 connection (callers use get_db()); none performs a network call. Transaction
boundaries belong to the caller (router / native.finish), except where noted.
"""

import logging
from typing import Optional

from psycopg2.extras import Json

from backend.coach_payload import RunFacts, avg_pace
from backend.coach_plan import CoachPlanV1, PlanRejected, apply_overrides, compute_outcome, plan_total_s
from backend.coach_profile import compute_measured_profile
from backend.config import (
    COACH_HISTORY_RUNS, COACH_INTERVAL_LOOKBACK_PLANS, COACH_MEASURED_KEYS, COACH_MEASURED_WINDOW_RUNS,
    COACH_MIN_RUN_S, COACH_PAYLOAD_VERSION,
)
from backend.security import AppError

log = logging.getLogger("runningtracker")

_COMPLETE_WITH_METRICS = "r.status = 'complete' and r.started_at is not null and r.moving_s is not null"


# ---- settings / audit ------------------------------------------------------------------------------------------------

def get_settings(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute("select ai_enabled, consent_version, consented_at, goal_text, updated_at "
                    "from runningtracker.coach_settings where id = 1")
        return cur.fetchone()


def update_settings(conn, fields: dict, current_consent_version: int) -> dict:
    """CO1/Q4: only keys present in `fields` change. Enabling needs consent_version == current; disabling clears consent."""
    sets, params = [], []
    if "ai_enabled" in fields:
        if fields["ai_enabled"]:
            if fields.get("consent_version") != current_consent_version:
                raise AppError("CONSENT_VERSION_MISMATCH", "Consent version is missing or outdated.", 422)
            sets += ["ai_enabled = true", "consent_version = %s", "consented_at = now()"]
            params.append(current_consent_version)
        else:
            sets += ["ai_enabled = false", "consent_version = null", "consented_at = null"]
    if "goal_text" in fields:
        goal = (fields["goal_text"] or "").strip() or None
        if goal is not None and len(goal) > 500:
            raise AppError("VALIDATION_ERROR", "goal_text must be at most 500 characters.", 422)
        sets.append("goal_text = %s")
        params.append(goal)
    if sets:
        with conn.cursor() as cur:
            cur.execute(f"update runningtracker.coach_settings set {', '.join(sets)}, updated_at = now() where id = 1", params)
    return get_settings(conn)


def count_calls_24h(conn) -> int:
    with conn.cursor() as cur:
        cur.execute("select count(*) as n from runningtracker.coach_ai_calls where called_at > now() - interval '24 hours'")
        return cur.fetchone()["n"]


def record_call(conn, run_id: str, outcome: str) -> None:
    with conn.cursor() as cur:
        cur.execute("insert into runningtracker.coach_ai_calls (run_id, outcome) values (%s, %s)", (run_id, outcome))


# ---- run facts ---------------------------------------------------------------------------------------------------------

_FACTS_SELECT = f"""
    select r.id, r.run_type, r.started_at, r.moving_s, r.distance_m, r.status,
           m.avg_hr, m.max_hr, m.splits, m.pace_series, m.hr_series, m.recovery, m.cadence
    from runningtracker.runs r join runningtracker.run_metrics m on m.run_id = r.id
    where {_COMPLETE_WITH_METRICS}
"""


def _facts_for(conn, rows: list[dict]) -> list[RunFacts]:
    out = []
    for r in rows:
        with conn.cursor() as cur:
            cur.execute("select started_at, ended_at from runningtracker.run_pauses where run_id = %s order by started_at", (r["id"],))
            pauses = [((p["started_at"] - r["started_at"]).total_seconds(), (p["ended_at"] - r["started_at"]).total_seconds())
                      for p in cur.fetchall()]
            cur.execute("select plan_type, outcome from runningtracker.coach_plans where run_id = %s", (r["id"],))
            plan = cur.fetchone()
        rec, cad = r["recovery"] or {}, r["cadence"] or {}
        out.append(RunFacts(
            started_at=r["started_at"], run_kind=r["run_type"], distance_m=r["distance_m"] or 0.0, moving_s=r["moving_s"],
            avg_hr=r["avg_hr"], max_hr=r["max_hr"], avg_cadence_spm=cad.get("avg_spm"),
            hrr60=rec.get("hrr60"), hrr120=rec.get("hrr120"), splits=r["splits"] or [], pace_series=r["pace_series"] or [],
            hr_series=r["hr_series"] or [], cadence_series=cad.get("series") or [], pauses=pauses,
            plan_type=plan["plan_type"] if plan else None, plan_outcome=plan["outcome"] if plan else None))
    return out


def _window(conn, limit: int) -> list[RunFacts]:
    with conn.cursor() as cur:
        cur.execute(_FACTS_SELECT + " order by r.started_at desc limit %s", (limit,))
        rows = cur.fetchall()
    return _facts_for(conn, rows)


def count_window_runs(conn) -> int:
    """PROF1 pre-step: min(COACH_MEASURED_WINDOW_RUNS, complete runs with metrics), counted over the latest runs overall."""
    with conn.cursor() as cur:
        cur.execute(f"select count(*) as n from runningtracker.runs r join runningtracker.run_metrics m on m.run_id = r.id "
                    f"where {_COMPLETE_WITH_METRICS}")
        return min(COACH_MEASURED_WINDOW_RUNS, cur.fetchone()["n"])


def list_profile(conn) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("select key, basis, value_text, value_num, unit, confidence, n_runs, updated_at "
                    "from runningtracker.coach_profile_items order by (basis = 'measured') desc, key asc")
        return cur.fetchall()


def _plan_view(row: Optional[dict]) -> Optional[dict]:
    if not row:
        return None
    plan = row["active_plan"] or row["plan"]
    return {"plan_type": row["plan_type"], "planned_s": plan_total_s(plan), "status": row["status"], "outcome": row["outcome"]}


def load_run_bundle(conn, run_id: str):
    """(current RunFacts, history newest first, profile rows, goal_text, previous plan dict) or None for an unknown run.
    Raises RUN_NOT_ANALYSABLE (409) unless the run is complete, has metrics and moving_s >= COACH_MIN_RUN_S.
    Previous plan = the newest plan created before this analysis (plans of this very analysis are excluded)."""
    with conn.cursor() as cur:
        cur.execute("select status from runningtracker.runs where id = %s", (run_id,))
        run = cur.fetchone()
        if run is None:
            return None
        cur.execute(_FACTS_SELECT + " and r.id = %s", (run_id,))
        row = cur.fetchone()
    if row is None or (row["moving_s"] or 0) < COACH_MIN_RUN_S:
        raise AppError("RUN_NOT_ANALYSABLE", "This run cannot be analysed (not complete, no metrics, or too short).", 409)
    current = _facts_for(conn, [row])[0]
    with conn.cursor() as cur:
        cur.execute(_FACTS_SELECT + " and r.started_at < %s order by r.started_at desc limit %s",
                    (current.started_at, COACH_HISTORY_RUNS))
        history = _facts_for(conn, cur.fetchall())
        cur.execute("select id, analysed_at from runningtracker.coach_analyses where run_id = %s", (run_id,))
        analysis = cur.fetchone()
        cur.execute(
            "select plan_type, status, plan, active_plan, outcome from runningtracker.coach_plans "
            "where (%s::uuid is null or analysis_id is distinct from %s::uuid) "
            "and created_at < coalesce(%s::timestamptz, now()) order by created_at desc limit 1",
            (analysis["id"] if analysis else None, analysis["id"] if analysis else None,
             analysis["analysed_at"] if analysis else None))
        previous = _plan_view(cur.fetchone())
    goal = get_settings(conn)["goal_text"]
    return current, history, list_profile(conn), goal, previous


def recent_plan_types(conn, run_id: str, force: bool) -> list[str]:
    """Types of the latest COACH_INTERVAL_LOOKBACK_PLANS plans that are neither disregarded nor superseded (interval rule).
    On a forced re-analysis the still-recommended plan of this analysis is about to be superseded and does not count."""
    with conn.cursor() as cur:
        cur.execute(
            "select p.plan_type from runningtracker.coach_plans p "
            "left join runningtracker.coach_analyses a on a.id = p.analysis_id "
            "where p.status not in ('disregarded', 'superseded') "
            "and not (%s and p.status = 'recommended' and a.run_id = %s) "
            "order by p.created_at desc limit %s", (force, run_id, COACH_INTERVAL_LOOKBACK_PLANS))
        return [r["plan_type"] for r in cur.fetchall()]


# ---- analysis ------------------------------------------------------------------------------------------------------------

_ANALYSIS_SELECT = """
    select a.run_id, a.assessment, a.previous_effect, a.plan_rejected_reason, a.prompt_version, a.model, a.analysed_at,
           (select p.id from runningtracker.coach_plans p where p.analysis_id = a.id order by p.created_at desc limit 1) as plan_id
    from runningtracker.coach_analyses a
"""


def get_analysis(conn, run_id: str) -> Optional[dict]:
    with conn.cursor() as cur:
        cur.execute(_ANALYSIS_SELECT + " where a.run_id = %s", (run_id,))
        return cur.fetchone()


def save_analysis(conn, run_id: str, response, profile_updates: list[dict], plan: Optional[CoachPlanV1],
                  plan_rejected_reason: Optional[str], sent_payload: dict, model: str, prompt_version: str,
                  n_runs: int, force: bool) -> dict:
    """One transaction (the caller commits): analysis, inferred profile rows, measured refresh, plan rows."""
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into runningtracker.coach_analyses
                (run_id, assessment, previous_effect, profile_updates, plan_rejected_reason, payload_version,
                 prompt_version, model, sent_payload, analysed_at)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            on conflict (run_id) do update set
                assessment = excluded.assessment, previous_effect = excluded.previous_effect,
                profile_updates = excluded.profile_updates, plan_rejected_reason = excluded.plan_rejected_reason,
                payload_version = excluded.payload_version, prompt_version = excluded.prompt_version,
                model = excluded.model, sent_payload = excluded.sent_payload, analysed_at = excluded.analysed_at
            returning id
            """,
            (run_id, response.assessment, response.previous_recommendation_effect, Json(profile_updates),
             plan_rejected_reason, sent_payload.get("payload_version", COACH_PAYLOAD_VERSION), prompt_version, model,
             Json(sent_payload)))
        analysis_id = cur.fetchone()["id"]
        for u in profile_updates:
            cur.execute(
                """
                insert into runningtracker.coach_profile_items (key, basis, value_text, value_num, unit, confidence, n_runs, updated_at)
                values (%s, 'inferred', %s, null, null, %s, %s, now())
                on conflict (key) do update set basis = 'inferred', value_text = excluded.value_text, value_num = null,
                    unit = null, confidence = excluded.confidence, n_runs = excluded.n_runs, updated_at = now()
                """, (u["key"], u["value_text"], u["confidence"], n_runs))
        if force:  # the earlier recommendation of this analysis is replaced
            cur.execute("update runningtracker.coach_plans set status = 'superseded', analysis_id = null "
                        "where analysis_id = %s and status = 'recommended'", (analysis_id,))
        if plan is not None:
            cur.execute(
                "insert into runningtracker.coach_plans (analysis_id, plan_schema_version, plan_type, status, plan) "
                "values (%s, %s, %s, 'recommended', %s)",
                (analysis_id, plan.schema_version, plan.type, Json(plan.to_json())))
    refresh_measured_profile(conn)
    return get_analysis(conn, run_id)


def refresh_measured_profile(conn) -> int:
    """Upsert deterministic measured rows, delete measured rows without a basis; returns the window size."""
    window = _window(conn, COACH_MEASURED_WINDOW_RUNS)
    rows = compute_measured_profile(window)
    with conn.cursor() as cur:
        for r in rows:
            cur.execute(
                """
                insert into runningtracker.coach_profile_items (key, basis, value_text, value_num, unit, confidence, n_runs, updated_at)
                values (%s, 'measured', %s, %s, %s, null, %s, now())
                on conflict (key) do update set basis = 'measured', value_text = excluded.value_text,
                    value_num = excluded.value_num, unit = excluded.unit, confidence = null,
                    n_runs = excluded.n_runs, updated_at = now()
                """, (r["key"], r["value_text"], r["value_num"], r["unit"], r["n_runs"]))
        cur.execute("delete from runningtracker.coach_profile_items where basis = 'measured' and key = any(%s) and not (key = any(%s))",
                    (list(COACH_MEASURED_KEYS), [r["key"] for r in rows]))
    return len(window)


# ---- plans -----------------------------------------------------------------------------------------------------------------

_PLAN_COLS = "id, analysis_id, plan_type, status, plan, active_plan, run_id, outcome, created_at, decided_at"


def next_session(conn) -> Optional[dict]:
    with conn.cursor() as cur:
        cur.execute(f"select {_PLAN_COLS} from runningtracker.coach_plans where status = 'accepted' and run_id is null "
                    "order by decided_at desc limit 1")
        row = cur.fetchone()
        if row is None:
            cur.execute(f"select {_PLAN_COLS} from runningtracker.coach_plans where status = 'recommended' "
                        "order by created_at desc limit 1")
            row = cur.fetchone()
    return row


def list_plans(conn, limit: int) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(f"select {_PLAN_COLS} from runningtracker.coach_plans order by created_at desc, id asc limit %s", (limit,))
        return cur.fetchall()


def decide_plan(conn, plan_id: str, status: str, overrides: Optional[dict], overrides_present: bool) -> dict:
    """PLAN1 transitions; the caller commits. 404 / INVALID_TRANSITION 409 / PLAN_INVALID 422."""
    with conn.cursor() as cur:
        cur.execute(f"select {_PLAN_COLS} from runningtracker.coach_plans where id = %s for update", (plan_id,))
        row = cur.fetchone()
        if row is None:
            raise AppError("NOT_FOUND", "Plan not found.", 404)
        current = row["status"]
        allowed = {("recommended", "accepted"), ("recommended", "disregarded"), ("accepted", "accepted"),
                   ("accepted", "disregarded")}
        if (current, status) not in allowed or (current == "accepted" and row["run_id"] is not None):
            raise AppError("INVALID_TRANSITION", f"A {current} plan cannot become {status}.", 409)
        if status == "disregarded":
            cur.execute("update runningtracker.coach_plans set status = 'disregarded', decided_at = now() where id = %s", (plan_id,))
        else:
            base = row["active_plan"] if current == "accepted" else row["plan"]
            if overrides_present and overrides:
                try:
                    active = apply_overrides(base, overrides).to_json()
                except PlanRejected as exc:
                    raise AppError("PLAN_INVALID", f"The modified plan is not valid ({exc.reason}).", 422)
            else:
                active = base
            cur.execute("update runningtracker.coach_plans set status = 'superseded' "
                        "where status = 'accepted' and run_id is null and id <> %s", (plan_id,))
            cur.execute("update runningtracker.coach_plans set status = 'accepted', active_plan = %s, decided_at = now() "
                        "where id = %s", (Json(active), plan_id))
        cur.execute(f"select {_PLAN_COLS} from runningtracker.coach_plans where id = %s", (plan_id,))
        return cur.fetchone()


def active_plan_for_phone(conn) -> Optional[dict]:
    with conn.cursor() as cur:
        cur.execute("select id, plan_schema_version, active_plan from runningtracker.coach_plans "
                    "where status = 'accepted' and run_id is null order by decided_at desc limit 1")
        row = cur.fetchone()
    if row is None:
        return None
    return {"plan_id": str(row["id"]), "schema_version": row["plan_schema_version"], "plan": row["active_plan"]}


# ---- finish hook -------------------------------------------------------------------------------------------------------------

def on_run_finished(conn, run_id: str, coach_plan_id: Optional[str]) -> None:
    """OUT1 + measured refresh. Replay-safe. Never raises: a savepoint keeps the finish transaction usable."""
    try:
        with conn.cursor() as cur:
            cur.execute("savepoint coach_hook")
        try:
            _link_and_outcome(conn, run_id, coach_plan_id)
            refresh_measured_profile(conn)
            with conn.cursor() as cur:
                cur.execute("release savepoint coach_hook")
        except Exception:
            with conn.cursor() as cur:
                cur.execute("rollback to savepoint coach_hook")
            raise
    except Exception as exc:  # class only, never content (G1)
        log.warning("coach finish hook failed: %s", type(exc).__name__)


def _link_and_outcome(conn, run_id: str, coach_plan_id: Optional[str]) -> None:
    with conn.cursor() as cur:
        if coach_plan_id:
            cur.execute(
                "update runningtracker.coach_plans set run_id = %s where id = %s and status = 'accepted' and run_id is null "
                "and not exists (select 1 from runningtracker.coach_plans where run_id = %s)", (run_id, coach_plan_id, run_id))
        cur.execute("select id, active_plan from runningtracker.coach_plans where run_id = %s", (run_id,))
        plan = cur.fetchone()
    if plan is None:
        return
    facts = _facts_for(conn, _run_rows(conn, run_id))
    if not facts:
        return
    f = facts[0]
    outcome = compute_outcome(plan["active_plan"], f.moving_s, f.pauses, f.hr_series, f.pace_series, f.cadence_series,
                              f.avg_hr, avg_pace(f), f.avg_cadence_spm)
    with conn.cursor() as cur:
        cur.execute("update runningtracker.coach_plans set outcome = %s, status = 'completed' where id = %s",
                    (Json(outcome), plan["id"]))


def _run_rows(conn, run_id: str) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(_FACTS_SELECT + " and r.id = %s", (run_id,))
        return cur.fetchall()
