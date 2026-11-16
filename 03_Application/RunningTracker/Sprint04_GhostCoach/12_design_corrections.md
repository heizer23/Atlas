# Design Corrections — RunningTracker Sprint04_GhostCoach

## Applied Changes
1. **Allow-list host violation: one outcome everywhere**
   - Review Source: `11_design_review.md` Blocking Issue 1
   - Files Updated: `10_architecture.json`, `10_scaffolding.json`, `10_test_spec.md`
   - Change: Chose the "host test stays in `configured()`" option. A configured URL that is not https or whose host is not in COACH_ALLOWED_HOSTS gives AI_NOT_CONFIGURED 503, `key_configured` false, no network call and no `coach_ai_calls` row.
     - Architecture: failure_modes AI_NOT_CONFIGURED extended; "host not in the allow-list" removed from AI_UNAVAILABLE; KEY1 sentence aligned.
     - Scaffolding: `ProviderConfig.configured` purpose states the outcome; `ProviderError` host-not-allowed is marked defensive only (unreachable from the route). `settings_dataset` is unchanged (`key_configured = cfg.configured()`).
     - Test spec: scenario "Host outside the allow-list is refused without a call" now expects AI_NOT_CONFIGURED 503, key_configured false, no call row, no transport request.
2. **Source of `n_runs` declared as a pre-step**
   - Review Source: `11_design_review.md` Blocking Issue 2
   - Files Updated: `10_architecture.json`, `10_scaffolding.json`
   - Change: Added `coach_store.count_window_runs(conn) -> int` (min(COACH_MEASURED_WINDOW_RUNS, complete runs with metrics), over the latest runs overall, including runs newer than the analysed one). It is read in step 29 after `load_run_bundle` and before `validate_profile_updates`. Its value is the `n_runs` given to `validate_profile_updates` and `save_analysis` and is persisted unchanged. `refresh_measured_profile` purpose clarified (its returned size equals the pre-step value; `save_analysis` does not recompute). PROF1 and step 29 in the architecture updated to name it. `load_run_bundle` return tuple unchanged.

## Unchanged by Design
- All other sections of the three artifacts, `10_schema.sql` (no change required) and all Non-Blocking Issues (not in the required change set) were left verbatim.

## Review Alignment Check
- Required Changes Applied: Yes
- Approval Condition Satisfied: Yes
- Review Verdict: CHANGES_REQUIRED
- Every listed item confirmed applied: Yes
- Notes: The sprint returns to DESIGN_CREATED for re-review. No shell was available, so JSON validity was not machine-checked. All edits were string substitutions inside existing string values, plus one added sibling object in `coach_store` public_objects. Please run `python3 -m json.tool` on both JSON files (also review Non-Blocking 1). Choosing the 503 option changes the architecture prose (failure_modes) and the test spec to match the scaffolding, which was already authoritative.
