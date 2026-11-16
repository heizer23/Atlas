# Design Review — RunningTracker — Sprint04_GhostCoach

**Verdict:** CHANGES_REQUIRED
**Date:** 2026-11-15
**Reviewer:** sprint_design_reviewer

## Blocking Issues

| # | Location | Rule / Contract Violated | Required Change | Likely Cause (Design Phase) |
|---|----------|--------------------------|-----------------|-----------------------------|
| 1 | `10_scaffolding.json` backend/coach_ai.py `ProviderConfig.configured` (requires url host in COACH_ALLOWED_HOSTS) and `coach_datasets.settings_dataset` (key_configured = cfg.configured()) vs `10_architecture.json` surface POST analysis check order ("configured (503)"), failure_modes AI_UNAVAILABLE ("host not in the allow-list") and `10_test_spec.md` "Host outside the allow-list is refused without a call" (expects AI_UNAVAILABLE 502) | R-CON-BP-09 (cross-artifact consistency), R-CON-BP-11 | Pick one outcome for "configured URL host not in allow-list" and state it identically in all four places. Either `configured()` excludes the host test (and the later call_provider check yields AI_UNAVAILABLE 502, with the preceding record_call outcome stated), or the host test stays in `configured()` and the failure mode and test spec say AI_NOT_CONFIGURED 503. Also state whether `key_configured` is true in that case. | Incomplete Contract Thinking |
| 2 | `10_architecture.json` PROF1 and step 29 (run_analysis) vs `10_scaffolding.json` `validate_profile_updates(updates, n_runs)`, `save_analysis(..., n_runs, ...)`, `load_run_bundle` return tuple, `refresh_measured_profile` ("returns the window size (n_runs)") | R-CON-BP-10 (input sufficiency) | Declare where `n_runs` comes from at the moment `validate_profile_updates` runs. As written, validation (VAL1/PROF1) precedes the transaction in which `refresh_measured_profile` first produces `n_runs`, and `load_run_bundle` does not return it. Readings (len(history)+1, count of the latest window runs including runs newer than the analysed one, or a pre-step count) give different persisted `confidence` caps and different inferred-row accept/reject results for re-analysed older runs. Name the single pre-step or bundle field. | Incomplete Contract Thinking |

## Non-Blocking Issues

| # | Location | Observation |
|---|----------|-------------|
| 1 | JSON validity | `Bash` was unavailable to the reviewer, so no parser was run. Both `10_architecture.json` (452 lines) and `10_scaffolding.json` (611 lines) were read in full; no syntax defect (unbalanced bracket, trailing comma, bad escape) was found by inspection. Orchestrator should confirm with `python3 -m json.tool` on both files. |
| 2 | `10_architecture.json` PLAN1 interval-frequency rule vs force re-analysis | On `force=true` the still-recommended plan of this analysis is only superseded inside the final transaction, after `validate_plan` ran. If that plan is an interval plan it counts in the lookback and can cause a spurious `plan_interval_frequency`. State whether it is excluded from `recent_plan_types`. Prose-level edge case; the implementer can resolve either way without schema change. |
| 3 | `10_scaffolding.json` `load_run_bundle` "previous plan = newest coach_plans row created before this analysis" | On a forced re-analysis "before this analysis" is ambiguous (the plan created by the first analysis of the same run). Clarify. |
| 4 | `10_test_spec.md` "Modify with null versus omitted" Given: "a recommended hr_controlled-free plan" | Wording unclear; intent is a non-hr_controlled plan with HR, pace and cadence targets. |
| 5 | `10_scaffolding.json` `SettingsPatch.ai_enabled: Optional[bool]` | Explicit `ai_enabled: null` is not defined (omit vs null). Not user-clearable in the UI, so no R-CON-AL-04 round-trip impact; define as 422 or as omitted. |
| 6 | `10_architecture.json` CF5 | `.claude/supportDocs/atlas_dev_ref.md` still has no RunningTracker/AtlasPhone entry. Surfaced by the designer as a sprint-close task; accepted. |

## Verification notes (no action required)

- **Deferred items not pre-built:** confirmed. Plan types are exactly the five V1 types (no PR attempt); segment kinds, triggers, profile keys and schema contain no terrain, route-intelligence, experiment, challenge, per-gradient or step-length-target fields; PAYLOAD_V1_KEYS has no route data; prompt is required to forbid route/terrain advice and experiments; `coach_plan_golden.json` and forbidden list reinforce this.
- **§0 conflicts surfaced:** CF1 (roadmap scope), CF2 (numbering), CF3 (external exposure, with CO1/EGR1/KEY1/AUD1, opt-in default off, server-side key, minimal payload, no new inbound ports, loopback publication unchanged, `/native/coach` tailnet-only), CF4 (layer split) are all present in `open_questions`; the roadmap is explicitly not edited.
- **Layer placement:** application logic in 03_Application/RunningTracker; engine in AtlasPhone running.coach; only the domain-free SpeechOutput is added to the Mobile Platform; nothing in 02_Platform.
- **R-CON-BP-04 / R-CON-AL:** coach reads return Dataset; mutations return typed Dataset or ApiError; PATCH null/omit round trips defined for goal_text and PlanOverrides; time authority declared (T4); query behavior explicit.
- **R-CON-BP-07:** single runtime schema path `03_Application/RunningTracker/schema.sql` used consistently.
- **UI coverage:** `.tsx` files in scope and `10_test_spec.md` contains [UI] and [UI — manual] scenarios.
- **Schema consistency:** tables, check constraints and plan status lifecycle in `10_schema.sql` match PLAN1/OUT1/CO1 and the scaffold's coach_store functions.

## Approval Condition

Both blocking issues are resolved so that (1) the allow-list-host-violation outcome (status code, error code, key_configured value) is identical in `10_architecture.json`, `10_scaffolding.json` and `10_test_spec.md`, and (2) the source of `n_runs` used by `validate_profile_updates` is declared as a named pre-step or return field before validation runs.
