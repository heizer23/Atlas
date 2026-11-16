"""Ghost Coach routes. `router` (/coach, web) and `native_router` (/native/coach, tailnet only, device token).

Flow steps 27-31 of Sprint04_GhostCoach/10_architecture.json. analysis holds NO database connection during the
provider call (read -> close -> call -> new transaction). Failures use AppError -> platform ApiError envelope.
"""

import logging
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from backend import coach_store
from backend.coach_ai import (
    InvalidAiResponse, ProviderError, call_provider, load_prompt, parse_ai_response, provider_config,
)
from backend.coach_datasets import (
    analysis_dataset, plans_dataset, preview_dataset, profile_dataset, settings_dataset,
)
from backend.coach_payload import build_payload, to_wire
from backend.coach_plan import PlanRejected, validate_plan
from backend.coach_profile import validate_profile_updates
from backend.config import COACH_CONSENT_VERSION, COACH_MAX_CALLS_PER_DAY, COACH_PLAN_LIST_DEFAULT, COACH_PLAN_LIST_MAX
from backend.database import get_db
from backend.datasets import ds_response
from backend.security import AppError, DeviceContext, native_guard, require_device

log = logging.getLogger("runningtracker")

router = APIRouter(prefix="/coach", tags=["coach"])
native_router = APIRouter(prefix="/native/coach", tags=["coach-native"], dependencies=[Depends(native_guard)])

# Test seam: tests install an httpx transport (fake provider). None in production.
_transport = None


class SettingsPatch(BaseModel):
    """Presence is read from model_fields_set so an omitted field and an explicit null differ (R-CON-AL-04)."""
    model_config = ConfigDict(extra="forbid")
    ai_enabled: Optional[bool] = None
    consent_version: Optional[int] = None
    goal_text: Optional[str] = None


class PlanPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["accepted", "disregarded"]
    overrides: Optional[dict] = None  # key presence inside is preserved: omitted = unchanged, null = clear


def _run_id(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise AppError("NOT_FOUND", "Run not found.", 404)


@router.get("/settings", response_model=None)
def get_settings_route() -> JSONResponse:
    with get_db() as conn:
        settings, calls = coach_store.get_settings(conn), coach_store.count_calls_24h(conn)
    return ds_response(settings_dataset(settings, provider_config(), calls))


@router.patch("/settings", response_model=None)
def patch_settings_route(body: SettingsPatch) -> JSONResponse:
    fields = {k: getattr(body, k) for k in body.model_fields_set}
    if "ai_enabled" in fields and fields["ai_enabled"] is None:
        raise AppError("VALIDATION_ERROR", "ai_enabled must be true or false.", 422)
    with get_db() as conn:
        settings = coach_store.update_settings(conn, fields, COACH_CONSENT_VERSION)
        conn.commit()
        calls = coach_store.count_calls_24h(conn)
    return ds_response(settings_dataset(settings, provider_config(), calls))


def _bundle(conn, rid: str):
    bundle = coach_store.load_run_bundle(conn, rid)
    if bundle is None:
        raise AppError("NOT_FOUND", "Run not found.", 404)
    return bundle


@router.get("/analysis-preview", response_model=None)
def get_analysis_preview(run_id: str) -> JSONResponse:
    """Exactly the document analysis would send; no outbound call, works without consent or key."""
    rid = _run_id(run_id)
    with get_db() as conn:
        current, history, profile, goal, previous = _bundle(conn, rid)
    return ds_response(preview_dataset(rid, build_payload(current, history, profile, goal, previous), provider_config()))


@router.post("/runs/{run_id}/analysis", response_model=None)
def post_analysis(run_id: str, force: bool = False) -> JSONResponse:
    rid = _run_id(run_id)
    cfg = provider_config()
    with get_db() as conn:  # phase 1: checks and payload (connection released before the provider call)
        current, history, profile, goal, previous = _bundle(conn, rid)  # 404, 409
        settings = coach_store.get_settings(conn)
        if not (settings["ai_enabled"] and settings["consent_version"] == COACH_CONSENT_VERSION):
            raise AppError("CONSENT_REQUIRED", "Enable AI and accept the current consent on the Coach page first.", 403)
        if not cfg.configured():
            raise AppError("AI_NOT_CONFIGURED", "The AI provider is not configured on the server.", 503)
        existing = coach_store.get_analysis(conn, rid)
        if existing is not None and not force:
            return ds_response(analysis_dataset(existing))
        if coach_store.count_calls_24h(conn) >= COACH_MAX_CALLS_PER_DAY:
            raise AppError("RATE_LIMITED", "Daily analysis limit reached. Try again later.", 429)
        n_runs = coach_store.count_window_runs(conn)
        payload = build_payload(current, history, profile, goal, previous)
        recent_types = coach_store.recent_plan_types(conn, rid, force)

    try:
        system = load_prompt(cfg.prompt_version)
        text = call_provider(cfg, system, to_wire(payload), _transport)
    except ProviderError as exc:
        if exc.code != "prompt_missing":
            _record(rid, "provider_error")
        log.warning("coach provider call failed: %s", exc.code)
        raise AppError("AI_UNAVAILABLE", "The AI provider is unavailable. Try again later.", 502)
    try:
        response = parse_ai_response(text)
    except InvalidAiResponse as exc:
        _record(rid, "invalid_response")
        log.warning("coach provider response invalid: %s", exc.code)
        raise AppError("AI_INVALID_RESPONSE", "The AI provider returned an unusable answer.", 502)
    _record(rid, "ok")

    updates = validate_profile_updates(response.profile_updates, n_runs)
    plan, rejected = None, None
    if response.next_session is not None:
        try:
            plan = validate_plan(response.next_session, recent_types)
        except PlanRejected as exc:
            rejected = exc.reason
    with get_db() as conn:  # phase 2: one transaction
        row = coach_store.save_analysis(conn, rid, response, updates, plan, rejected, payload, cfg.model,
                                        cfg.prompt_version, n_runs, force)
        conn.commit()
    return ds_response(analysis_dataset(row))


def _record(run_id: str, outcome: str) -> None:
    with get_db() as conn:
        coach_store.record_call(conn, run_id, outcome)
        conn.commit()


@router.get("/runs/{run_id}/analysis", response_model=None)
def get_run_analysis(run_id: str) -> JSONResponse:
    rid = _run_id(run_id)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select 1 from runningtracker.runs where id = %s", (rid,))
            if cur.fetchone() is None:
                raise AppError("NOT_FOUND", "Run not found.", 404)
        row = coach_store.get_analysis(conn, rid)
    return ds_response(analysis_dataset(row))


@router.get("/profile", response_model=None)
def get_profile() -> JSONResponse:
    with get_db() as conn:
        rows = coach_store.list_profile(conn)
    return ds_response(profile_dataset(rows))


@router.get("/next-session", response_model=None)
def get_next_session() -> JSONResponse:
    with get_db() as conn:
        row = coach_store.next_session(conn)
    return ds_response(plans_dataset([row] if row else []))


@router.get("/plans", response_model=None)
def get_plans(limit: int = Query(COACH_PLAN_LIST_DEFAULT, ge=1, le=COACH_PLAN_LIST_MAX)) -> JSONResponse:
    with get_db() as conn:
        rows = coach_store.list_plans(conn, limit)
    return ds_response(plans_dataset(rows))


@router.patch("/plans/{plan_id}", response_model=None)
def patch_plan(plan_id: str, body: PlanPatch) -> JSONResponse:
    try:
        pid = str(uuid.UUID(plan_id))
    except ValueError:
        raise AppError("NOT_FOUND", "Plan not found.", 404)
    if body.status == "disregarded" and body.overrides is not None:
        raise AppError("VALIDATION_ERROR", "overrides are only allowed when accepting a plan.", 422)
    with get_db() as conn:
        row = coach_store.decide_plan(conn, pid, body.status, body.overrides, body.overrides is not None)
        conn.commit()
    return ds_response(plans_dataset([row]))


@native_router.get("/next-plan", response_model=None)
def native_next_plan(device: DeviceContext = Depends(require_device)) -> dict:
    """The accepted plan without a linked run, for offline coaching on the phone."""
    with get_db() as conn:
        found = coach_store.active_plan_for_phone(conn)
    return found or {"plan_id": None, "schema_version": None, "plan": None}
