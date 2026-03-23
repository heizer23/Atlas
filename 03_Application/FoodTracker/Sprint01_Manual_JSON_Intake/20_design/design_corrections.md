# Redesign Summary — food_tracker

## Applied Changes

1. **Replace `_validate_and_normalise` raise-JSONResponse contract with return-based failure signal**
   - Review Source: `design_review.md` → Confirmed Problem 1 (Major); Hard Rule Violation 1 (`architecture_as_ai_interface`); Minimal Change Set item 1
   - Files Updated: `10_Design/component_scaffold.json`, `10_Design/component_architecture.json`
   - Change: In `component_scaffold.json`, the `_validate_and_normalise` `returns` field was corrected from `dict` to `tuple[dict, None] | tuple[None, dict]`, and the `purpose` field was rewritten to specify the return-based contract: `(normalised_dict, None)` on success, `(None, error_dict)` on failure, where the route handler constructs the `JSONResponse`. The statement "Raises JSONResponse (ApiError shape, HTTP 422) on any validation failure — callers must not catch this." was removed entirely. In `component_architecture.json`, internal_flow step 2 `description` and `outputs` were updated to document the same return-based contract and to state that the route handler constructs the JSONResponse.

2. **Add explicit cross-field validation ordering for `good_fat_g` and `red_meat_g`**
   - Review Source: `design_review.md` → Confirmed Problem 2 (Major); Minimal Change Set item 2
   - Files Updated: `10_Design/component_architecture.json`
   - Change: In `component_architecture.json` internal_flow step 2 `description`, the following ordering rule was added: cross-field constraints (`good_fat_g <= fat_g`, `red_meat_g <= meat_g`) are checked only after both operand fields have individually passed their `>= 0` presence and type checks. If either operand field fails first, the cross-field check is skipped and the first failure is returned.

3. **Restrict CORS `allow_methods` to `GET` and `POST` only**
   - Review Source: `design_review.md` → Confirmed Problem 3 (Minor); Hard Rule Violation 2 (`security / least-privilege`); Minimal Change Set item 3
   - Files Updated: `10_Design/component_architecture.json`
   - Change: In `component_architecture.json` `deferrals.application_implementer` item 2, `CORS allow_methods GET POST DELETE` was changed to `CORS allow_methods GET POST` with an explicit note that `DELETE` must not be included in Sprint 01 and should be added only when a DELETE endpoint is defined in a future sprint.

4. **Remove named export from `shellConfig.ts` scaffold; update role to side-effect-only description**
   - Review Source: `design_review.md` (Re-review) → Confirmed Problem 1 (Major); Hard Rule Violation 1 (`architecture_as_ai_interface`); Minimal Change Set item 1
   - Files Updated: `10_Design/component_scaffold.json`
   - Change: In `component_scaffold.json` → `src/shellConfig.ts`, the `public_objects` array was emptied (the `{ kind: "constant", name: "shellConfig", pattern: "shell_registration" }` entry was removed). The `role` field was rewritten to state that the module is a side-effect-only registration module that calls `AppRegistry.register({...})` at module scope with no exports of any kind, confirmed against the `WorkoutTracker/src/shellConfig.ts` pattern and `AppRegistry.ts` which exposes no mechanism to receive a named export.

## Unchanged by Design

All sections of `component_architecture.json` and `component_scaffold.json` not referenced by the Minimal Change Set were preserved verbatim. This includes: classification, contracts, shared_views, interfaces, exposed_surfaces, internal_flow steps 1–6, dependencies, persistence, all ui_implementer and test_writer and reviewer deferrals, deferred_decisions, risks, open_questions, all scaffold file entries other than `src/shellConfig.ts`, and the full directory listing. `component_architecture.json` was not modified in this correction pass.

## Sprint Definition Note

Minimal Change Set item 3 (from the prior correction pass) also references the sprint definition §7.3 (`main.py` implementation pattern), which specifies `CORS: allow_methods GET POST DELETE` inline. The sprint definition is a Manager-owned source-of-truth artifact and was not modified here. The corrected intent is captured in `component_architecture.json` `deferrals.application_implementer`. The sprint definition §7.3 requires a separate update by the Manager to remove `DELETE` from the CORS methods list and resolve the "follow WorkoutTracker verbatim" ambiguity noted in the review's Open Uncertainties.

## Review Alignment Check

- Minimal Change Set Applied: Yes
- Approval Condition Satisfied: Yes
- Notes: The Recommended Improvements from the re-review (clarify VALIDATION_ERROR wrapper vs. specific codes in failure_modes; move FoodIntake to private_objects in ShellEntry.tsx) were not applied — neither appears in the Minimal Change Set and neither is explicitly marked required before implementation. The Open Uncertainty regarding VALIDATION_ERROR vs. PARSE_ERROR/MISSING_FIELD/INVALID_FIELD as envelope codes remains open; architecture should resolve it before implementation begins. The sprint definition §7.3 CORS conflict (from the prior review's Open Uncertainty 1) remains unresolved in that source document.
