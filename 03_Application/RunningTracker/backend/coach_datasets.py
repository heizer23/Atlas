"""Dataset builders for the coach row shapes declared in 10_architecture.json exposed_surfaces."""

import json
from typing import Optional

from backend.coach_ai import ProviderConfig
from backend.coach_payload import to_wire
from backend.coach_plan import first_targets, plan_summary, plan_total_s
from backend.config import (
    COACH_CONSENT_VERSION, COACH_MAX_CALLS_PER_DAY, COACH_PAYLOAD_VERSION,
)
from backend.datasets import _col, _dataset
from platform_contracts import Dataset

SETTINGS_SCHEMA = [
    _col("ai_enabled", "AI enabled", "boolean"), _col("consent_current", "Consent current", "boolean"),
    _col("consent_version_required", "Consent version", "number"), _col("consented_at", "Consented", "date"),
    _col("goal_text", "Goal", "string"), _col("key_configured", "Key configured", "boolean"),
    _col("destination_host", "Destination", "string"), _col("model", "Model", "string"),
    _col("payload_version", "Payload version", "number"), _col("prompt_version", "Prompt version", "string"),
    _col("calls_last_24h", "Calls (24 h)", "number"), _col("daily_cap", "Daily cap", "number"),
]
PREVIEW_SCHEMA = [
    _col("destination_host", "Destination", "string"), _col("model", "Model", "string"),
    _col("prompt_version", "Prompt version", "string"), _col("payload_version", "Payload version", "number"),
    _col("history_runs", "History runs", "number"), _col("byte_size", "Bytes", "number"),
    _col("payload_json", "Payload", "string", sortable=False),
]
ANALYSIS_SCHEMA = [
    _col("run_id", "Run", "string"), _col("assessment", "Assessment", "string", sortable=False),
    _col("previous_effect", "Previous recommendation", "string", sortable=False),
    _col("plan_rejected_reason", "Plan rejected", "string"), _col("plan_id", "Plan", "string"),
    _col("prompt_version", "Prompt version", "string"), _col("model", "Model", "string"),
    _col("analysed_at", "Analysed", "date"),
]
PROFILE_SCHEMA = [
    _col("key", "Key", "string"), _col("label", "Value", "string"), _col("basis", "Basis", "enum"),
    _col("value_text", "Text", "string"), _col("value_num", "Number", "number"), _col("unit", "Unit", "string"),
    _col("confidence", "Confidence", "number"), _col("n_runs", "Runs", "number"), _col("updated_at", "Updated", "date"),
]
PLAN_SCHEMA = [
    _col("status", "Status", "enum"), _col("plan_type", "Type", "enum"), _col("title", "Title", "string"),
    _col("summary", "Summary", "string", sortable=False), _col("rationale", "Rationale", "string", sortable=False),
    _col("total_s", "Duration (s)", "number"), _col("target_distance_m", "Distance (m)", "number"),
    _col("hr_min", "HR min", "number"), _col("hr_max", "HR max", "number"),
    _col("pace_fast_s_per_km", "Pace fast", "number"), _col("pace_slow_s_per_km", "Pace slow", "number"),
    _col("cad_min", "Cadence min", "number"), _col("cad_max", "Cadence max", "number"),
    _col("segment_count", "Segments", "number"), _col("created_at", "Created", "date"),
    _col("decided_at", "Decided", "date"), _col("run_id", "Run", "string"),
    _col("outcome_summary", "Outcome", "string", sortable=False),
]

_LABELS = {
    "natural_cadence_spm": "Natural cadence", "avg_step_length_m": "Average step length",
    "hr_at_median_pace_bpm": "Heart rate at median pace", "runs_per_week": "Runs per week",
    "km_per_week": "Kilometres per week", "pr_fastest_1k_s": "Fastest 1 km", "pr_longest_run_m": "Longest run",
    "aerobic_endurance": "Aerobic endurance", "fatigue_drift": "Fatigue and drift", "development_trend": "Development trend",
}


def settings_dataset(settings: dict, cfg: ProviderConfig, calls_24h: int) -> Dataset:
    """key_configured = cfg.configured(); the key itself is never included."""
    row = {
        "id": "settings", "ai_enabled": settings["ai_enabled"],
        "consent_current": bool(settings["ai_enabled"] and settings["consent_version"] == COACH_CONSENT_VERSION),
        "consent_version_required": COACH_CONSENT_VERSION, "consented_at": settings["consented_at"],
        "goal_text": settings["goal_text"], "key_configured": cfg.configured(),
        "destination_host": cfg.destination_host(), "model": cfg.model, "payload_version": COACH_PAYLOAD_VERSION,
        "prompt_version": cfg.prompt_version, "calls_last_24h": calls_24h, "daily_cap": COACH_MAX_CALLS_PER_DAY,
    }
    return _dataset("coach_settings", "Coach settings", SETTINGS_SCHEMA, [row])


def preview_dataset(run_id: str, payload: dict, cfg: ProviderConfig) -> Dataset:
    row = {
        "id": run_id, "destination_host": cfg.destination_host(), "model": cfg.model, "prompt_version": cfg.prompt_version,
        "payload_version": payload["payload_version"], "history_runs": len(payload["history"]),
        "byte_size": len(to_wire(payload).encode("utf-8")),
        "payload_json": json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
    }
    return _dataset("coach_preview", "Analysis preview", PREVIEW_SCHEMA, [row])


def analysis_dataset(row: Optional[dict]) -> Dataset:
    if row is None:
        return _dataset("coach_analysis", "Coach analysis", ANALYSIS_SCHEMA, [], total=0)
    out = {
        "id": str(row["run_id"]), "run_id": str(row["run_id"]), "assessment": row["assessment"],
        "previous_effect": row["previous_effect"], "plan_rejected_reason": row["plan_rejected_reason"],
        "plan_id": str(row["plan_id"]) if row["plan_id"] else None, "prompt_version": row["prompt_version"],
        "model": row["model"], "analysed_at": row["analysed_at"],
    }
    return _dataset("coach_analysis", "Coach analysis", ANALYSIS_SCHEMA, [out])


def profile_dataset(rows: list[dict]) -> Dataset:
    out = [{**r, "id": r["key"], "label": _LABELS.get(r["key"], r["key"])} for r in rows]
    return _dataset("coach_profile_item", "Athlete profile", PROFILE_SCHEMA, out)


def _outcome_summary(o: Optional[dict]) -> Optional[str]:
    if not o:
        return None
    text = f"{'completed' if o.get('completed') else 'partial'}, {round(o['done_s'] / 60)}/{round(o['planned_s'] / 60)} min"
    for key, name in (("hr", "HR"), ("pace", "pace"), ("cadence", "cadence")):
        frac = (o.get("in_range") or {}).get(key)
        if frac is not None:
            text += f", {name} in range {round(frac * 100)}%"
    return text


def plan_row(r: dict) -> dict:
    plan = r["active_plan"] or r["plan"]  # accepted plans show what the user accepted
    return {
        "id": str(r["id"]), "status": r["status"], "plan_type": r["plan_type"], "title": plan["title"],
        "summary": plan_summary(plan), "rationale": plan.get("rationale"), "total_s": plan_total_s(plan),
        "target_distance_m": plan.get("target_distance_m"), **first_targets(plan),
        "segment_count": len(plan["segments"]), "created_at": r["created_at"], "decided_at": r["decided_at"],
        "run_id": str(r["run_id"]) if r["run_id"] else None, "outcome_summary": _outcome_summary(r["outcome"]),
    }


def plans_dataset(rows: list[dict]) -> Dataset:
    return _dataset("coach_plan", "Training plans", PLAN_SCHEMA, [plan_row(r) for r in rows])
