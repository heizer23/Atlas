# Design Review — RunningTracker — Sprint04_GhostCoach

**Verdict:** APPROVED
**Date:** 2026-11-15
**Reviewer:** sprint_design_reviewer

## Blocking Issues

_(None)_

## Non-Blocking Issues

| # | Location | Observation |
|---|----------|-------------|
| 1 | JSON validity | No shell or parser was available. `10_architecture.json` (452 lines) and `10_scaffolding.json` (612 lines) were read in full, with attention to the correction edits. In `coach_store` the new `count_window_runs` object (scaffolding line 154) follows `refresh_measured_profile` with a comma and is the last array element before `],`. All strings are balanced and the escaped quotes at line 467 are valid. No syntax defect was found. Running `python3 -m json.tool` on both files remains advisable. |
| 2 | `10_architecture.json` PLAN1 interval rule vs force re-analysis (carried from review 11, NB2) | The plan from the analysis being forced is superseded only inside the final transaction, after `validate_plan` runs. State whether it is excluded from `recent_plan_types`. The implementer can resolve this either way without a schema change. |
| 3 | `10_scaffolding.json` `load_run_bundle` "newest coach_plans row created before this analysis" (carried, NB3) | On force the phrase is ambiguous. Clarify. |
| 4 | `10_test_spec.md` "Modify with null versus omitted" Given: "hr_controlled-free plan" (carried, NB4) | Wording only. |
| 5 | `10_scaffolding.json` `SettingsPatch.ai_enabled` (carried, NB5) | Explicit `ai_enabled: null` is undefined. This has no UI round-trip impact. |
| 6 | `10_architecture.json` CF5 (carried, NB6) | `atlas_dev_ref.md` has no RunningTracker entry. This is a sprint-close task. |
| 7 | `10_test_spec.md` profile-update scenario (line ~93-95) | The test is worded in terms of "run count". The implementer should assert against `count_window_runs` (capped at COACH_MEASURED_WINDOW_RUNS), which the 3-run and 10-run cases already satisfy. |

## Approval Condition

None — approved as-is.

## Verification of Blocking Issue Resolution

- **Issue 1, allow-list host outcome: resolved and consistent.** Every artifact now gives the same outcome for a configured URL that is not https or whose host is outside COACH_ALLOWED_HOSTS. That outcome is AI_NOT_CONFIGURED 503, `key_configured` false, no network call and no `coach_ai_calls` row.
  - `10_architecture.json`: KEY1, the AI_NOT_CONFIGURED failure mode, and the POST analysis check order ("configured (503)"). The AI_UNAVAILABLE failure mode no longer lists the allow-list host.
  - `10_scaffolding.json`: `ProviderConfig.configured` states the outcome. `settings_dataset` uses `key_configured = cfg.configured()`. `ProviderError` host-not-allowed is marked defensive and unreachable from the route.
  - `10_test_spec.md`: "Host outside the allow-list is refused without a call" expects 503, `key_configured` false, no call row and no transport request. "Analysis check order" is consistent with this.
  - The remaining mention of the host check, the pre-call host check in `deferrals.application_implementer` "Provider call", is defensive. It does not contradict the route behavior.
- **Issue 2, source of `n_runs`: resolved.** Both artifacts agree on a named pre-step.
  - `coach_store.count_window_runs(conn)` is read in step 29 after the bundle load and before `validate_profile_updates`. It returns min(COACH_MEASURED_WINDOW_RUNS, complete runs with metrics), counted over the latest runs overall.
  - The same value is passed to `validate_profile_updates` and `save_analysis`, and persisted unchanged.
  - `refresh_measured_profile` returns a size equal to this value and `save_analysis` does not recompute it.
  - PROF1 and step 29 in the architecture, and the scaffolding signatures, state this identically. `load_run_bundle`'s return tuple is unchanged, so there is no signature conflict.
- **No new contradiction introduced.** The `n_runs` column of `ProfileRow` and the confidence-cap and minimum-run rules are unchanged. No schema change was needed. The deferred-item and layer verification from review 11 still holds.
