# Design Review — food_tracker (Re-review after corrections)

## Verdict
- Status: APPROVED_WITH_CHANGES
- Summary: All three issues from the previous review have been resolved correctly. The return-based failure contract for `_validate_and_normalise` is now properly specified, the cross-field validation ordering is fully defined, and the CORS surface is restricted to `GET POST` in both the design artifact and the sprint definition. One new implementability problem was uncovered during this review: the scaffold incorrectly declares a named export on `shellConfig.ts`. This directly contradicts the established platform pattern (confirmed against `AppRegistry.ts` and `WorkoutTracker/src/shellConfig.ts`) and would cause an implementer to produce a non-functional shell registration module. This single issue must be corrected before implementation proceeds.

---

## Previous Issue Resolution

1. **`_validate_and_normalise` raise-JSONResponse contract** — RESOLVED. `component_architecture.json` internal_flow step 2 and `component_scaffold.json` `_validate_and_normalise` both now specify the return-based contract: `(normalised_dict, None)` on success, `(None, error_dict)` on failure, with the route handler constructing the JSONResponse. No HTTP coupling in the private function.

2. **Cross-field validation ordering** — RESOLVED. `component_architecture.json` internal_flow step 2 now explicitly states that `good_fat_g <= fat_g` and `red_meat_g <= meat_g` are checked only after both operand fields have individually passed their `>= 0` checks, with early return on first individual failure.

3. **CORS `DELETE` method** — RESOLVED. `component_architecture.json` deferrals item 2 now specifies `CORS allow_methods GET POST` with an explicit prohibition on `DELETE`. The sprint definition §7.3 independently reads `methods GET POST`. Both artifacts are consistent.

---

## Confirmed Problems

1. **`shellConfig.ts` scaffold declares a named export that contradicts the established side-effect-only platform pattern**
   - Severity: Major
   - Location: `03_Application/FoodTracker/10_Design/component_scaffold.json` → `src/shellConfig.ts` → `public_objects` (entry `{ kind: "constant", name: "shellConfig", pattern: "shell_registration" }`)
   - Why it is a problem: The `AppRegistry.register()` mechanism is a void side-effect call. The shell loads each app's `shellConfig.ts` via a side-effect import; it never reads a named export. This is confirmed by `02_Platform/02_Atlas_Shell/src/registry/AppRegistry.ts`, which exposes no mechanism to receive an exported config — it is queried via `AppRegistry.getAll()` after registration fires on import. The established pattern is confirmed by `03_Application/WorkoutTracker/src/shellConfig.ts`, which contains no exports. The scaffold's `public_objects` entry for `shellConfig` is therefore a false contract: an implementer following it will write `export const shellConfig = { ... }` instead of calling `AppRegistry.register({...})` as a top-level side effect, producing a module that never actually registers the app.
   - Impact: The FoodTracker shell route `/food` will not appear in navigation. `AppRegistry.getAll()` will return no entry for `food`. The app will be invisible to the shell at runtime. This failure is silent — no error is thrown.
   - Likely Cause (Design Phase): Incomplete Contract Thinking — the designer specified a plausible-looking module export without verifying how the shell actually consumes the registration module.

---

## Recommended Improvements

1. **Clarify `VALIDATION_ERROR` wrapper code vs. specific failure codes in contracts**
   - Location: `component_architecture.json` → `contracts.failure_modes`
   - Improvement: The `failure_modes` list declares `PARSE_ERROR`, `MISSING_FIELD`, and `INVALID_FIELD` as distinct error codes, then also declares `VALIDATION_ERROR` as the "wrapper code returned for all validate/commit validation failures." The sprint definition §6.2 confirms the response envelope always uses `"code": "VALIDATION_ERROR"`, with specifics in the `detail` field. Revise the `failure_modes` list to clarify that `PARSE_ERROR`, `MISSING_FIELD`, and `INVALID_FIELD` describe the logical category of failure and appear in `detail.reason`, while `VALIDATION_ERROR` is the response envelope code for all three. As written, an implementer might reasonably implement three distinct `code` values in the response.
   - Why: Prevents misinterpretation of the failure_modes list as a specification of response envelope codes. The ambiguity exists in the post-correction artifacts and was not introduced by the corrections.

2. **Remove the `shellConfig` named export from `shellConfig.ts` scaffold**
   - Location: `component_scaffold.json` → `src/shellConfig.ts` → `public_objects`
   - Improvement: Remove the `public_objects` entry entirely. Replace with a note in the `role` field stating the module is a side-effect-only import that calls `AppRegistry.register({...})` at module scope and exports nothing. Align with `03_Application/WorkoutTracker/src/shellConfig.ts`.
   - Why: Eliminates the false contract surface and directly guides the implementer to the correct pattern.

3. **Move `FoodIntake` from `public_objects` to `private_objects` in `ShellEntry.tsx` scaffold**
   - Location: `component_scaffold.json` → `src/ShellEntry.tsx` → `public_objects`
   - Improvement: `FoodIntake` is rendered only by the default export within the same file. Move it to `private_objects` to accurately represent its visibility.
   - Why: The current placement overstates the component's API surface and may lead an implementer to expose it as an independent import target.

---

## Scaffold-Only Observations

1. **`FoodIntake` listed as a public export in `ShellEntry.tsx`**
   - Location: `component_scaffold.json` → `src/ShellEntry.tsx` → `public_objects`
   - Observation: `FoodIntake` is a component used only within `ShellEntry.tsx` as the element for the `/food` route. It has no consumers outside this file. Listing it under `public_objects` implies it can be independently imported.
   - Impact on implementation: Low runtime risk. An implementer may add an export statement that creates a bundler-visible symbol with no consumer, slightly inflating the public API surface.

2. **`database.py` `DATABASE_URL` fallback behavior is undeclared in design contracts**
   - Location: `component_scaffold.json` → `backend/database.py` role description
   - Observation: The scaffold states "Reads ATLAS_PG_* env vars (DATABASE_URL fallback)" but this precedence behavior is not declared in the component's environment contract. The `compose.yml` does not inject `DATABASE_URL`. The behavior is inherited via the "copy WorkoutTracker verbatim" instruction and is not visible in the explicit design contracts.
   - Impact on implementation: No risk in Sprint 01. Becomes a hidden configuration surface if future environments inject `DATABASE_URL` targeting a different host, silently overriding the `ATLAS_PG_*` values.

---

## Hard Rule Violations

1. **`architecture_as_ai_interface` — scaffold specifies a non-functional module export for `shellConfig.ts`**
   - Rule Source: `.claude/rules/01_role_of_architecture.md`
   - Location: `component_scaffold.json` → `src/shellConfig.ts` → `public_objects`
   - Violation: The scaffold's `public_objects` entry for `shellConfig` is an implicit coupling to a consumer behavior (named export consumption) that does not exist in the platform. An agent or implementer reading only the scaffold cannot infer that this export is unused. This violates the rule's requirement for explicit structure and stable semantic anchors. The correct behavior (side-effect import) is established by the platform and confirmed in the existing codebase but is not stated in the scaffold.
   - Required Fix: Remove the `public_objects` entry for `shellConfig`. State in the `role` field that the module is imported for its side effect only and has no exports.

---

## Open Uncertainties

1. **`VALIDATION_ERROR` code vs. `PARSE_ERROR` / `MISSING_FIELD` / `INVALID_FIELD` codes in the error response envelope**
   - Location: `component_architecture.json` → `contracts.failure_modes`; sprint definition §6.2
   - Uncertainty: `failure_modes` lists `PARSE_ERROR`, `MISSING_FIELD`, and `INVALID_FIELD` as named codes, and separately lists `VALIDATION_ERROR` as the code "returned for all validate/commit validation failures." The sprint definition shows only `VALIDATION_ERROR` as the response code. It is not stated whether `PARSE_ERROR` etc. appear as the envelope `code` or only inside `detail.reason`.
   - Why it matters: An implementer may implement either interpretation. If the specific codes appear as envelope codes, test assertions will differ from what the sprint definition illustrates.
   - Suggested owner: Architecture

---

## Minimal Change Set

1. Correct `component_scaffold.json` → `src/shellConfig.ts`: remove the `public_objects` entry for `shellConfig`; update the `role` field to state the module is a side-effect-only import that calls `AppRegistry.register({...})` at module scope with no exports, matching the `WorkoutTracker/src/shellConfig.ts` pattern.

---

## Approval Condition

- `component_scaffold.json` `src/shellConfig.ts` `public_objects` is empty and the `role` field explicitly describes a side-effect-only registration module with no exports.
