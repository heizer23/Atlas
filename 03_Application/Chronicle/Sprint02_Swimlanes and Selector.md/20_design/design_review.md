# Design Review — Chronicle Sprint02: Swimlanes and Selector

## Verdict
- Status: APPROVED_WITH_CHANGES
- Summary: The design is structurally sound, correctly layer-classified, and contract-complete for the primary happy paths. Two problems require resolution before implementation begins: (1) the rollback mechanism for the optimistic PATCH update is declared but not designed — the current CalendarPage implementation has no prior-state capture, and the design does not specify how rollback is executed; (2) cross-group selection is surfaced as a risk and left as an open question assigned to the implementer, but the design does not state a resolution — this creates an ambiguous boundary condition that the implementer cannot resolve without guessing. Both are solvable without redesign.

---

## Confirmed Problems

1. **Rollback of optimistic PATCH update is declared but not specified**
   - Severity: Major
   - Location: `20_design/architecture.json` → `contracts.failure_modes[2]` and `internal_flow[2]` (handle_toggle); `20_design/scaffolding.json` → CalendarPage.tsx handleToggle method
   - Why it is a problem: The failure mode states "the optimistic selection update is rolled back." The internal flow step 3 states "On failure, the update is rolled back and an error is surfaced." The scaffolding method purpose repeats this. However, the design does not specify how rollback is implemented: whether sources state is updated optimistically before the PATCH response (requiring a snapshot), or only after a confirmed server response (which is not a rollback pattern). The existing Sprint01 implementation of `handleToggle` in `CalendarPage.tsx` updates state only on confirmed server response — it does not apply an optimistic update at all. The design's claim of "optimistic update + rollback" is therefore either describing unimplemented behavior that must now be built, or it is mislabeled. An implementer cannot resolve this discrepancy from the artifacts alone.
   - Impact: If the implementer assumes optimistic update (apply immediately, rollback on failure), they must capture a snapshot of prior state — a non-trivial change to CalendarPage state management. If they preserve the Sprint01 pattern (update on success only), the rollback claim is vacuous and the design is inaccurate. Either outcome produces a contract mismatch between the design and the implementation.
   - Likely Cause (Design Phase): Incomplete Contract Thinking — the failure mode was declared without resolving whether "optimistic" is a genuine design intent or inherited language from a pattern that does not apply here.

2. **Cross-group selection boundary is unresolved and delegated to the implementer**
   - Severity: Major
   - Location: `20_design/architecture.json` → `risks[0]` and `open_questions[0]`
   - Why it is a problem: The design identifies that the chooser UI enforces same-group selection implicitly, but that a user with persisted cross-group selections (e.g., from a prior session or a direct PATCH call) could present CalendarPage with mixed-group sources in `selectedSources`. The open question asks whether CalendarPage should enforce the same-group invariant in code, but assigns resolution to the implementer. The design's invariants section does not state a resolution. The invariant "swimlanes are same-group only" (draft.md §4a, §4b) is stated as a feature boundary, but without a resolved enforcement point, the component boundary is ambiguous. An implementer asked to "not cross-group render" without a specified guard will produce inconsistent behavior.
   - Impact: If cross-group sources reach SwimlaneRenderer, the renderer has no stated behavior — it will either silently mix groups or fail. The design must declare whether CalendarPage filters selectedSources to the dominant application group, or whether this is a stated accepted gap. Either answer is acceptable; the absence of an answer is not.
   - Likely Cause (Design Phase): Ambiguous Definition — the out-of-scope statement ("cross-group combined rendering") was written as a UX constraint but not carried through to a data-layer enforcement decision.

---

## Recommended Improvements

1. **Clarify the year source for SwimlaneRenderer's event fetches**
   - Location: `20_design/architecture.json` → `internal_flow[3]` (fetch_events_per_source); `20_design/scaffolding.json` → SwimlaneRenderer.tsx
   - Improvement: The design states the year is derived from "current calendar year (client Date)." The backend `GET /calendar/events` accepts an explicit `year` query parameter and defaults to server-side `date.today().year`. The design should state explicitly whether SwimlaneRenderer passes the year parameter to the API or relies on the backend default. If the client and server clocks are in different time zones near year boundaries, behavior will diverge silently.
   - Why: Eliminates a year-boundary ambiguity that will produce hard-to-reproduce bugs without requiring any contract change.

2. **State the behavior when selectedSources drops from N to a lower count mid-render**
   - Location: `20_design/architecture.json` → `internal_flow[3]` (fetch_events_per_source)
   - Improvement: The design specifies that SwimlaneRenderer fetches on mount and "when sources changes." It does not specify whether in-flight fetches for deselected sources are cancelled (aborted) or ignored. Given parallel fetching, a race exists if the user deselects a source while fetches are in flight. The design should state the expected behavior: abort in-flight requests, or ignore stale responses via a request ID or dependency key comparison.
   - Why: Without this, implementers will make inconsistent choices, and stale responses may update state after deselection.

---

## Scaffold-Only Observations

1. **buildWeekGrid return type is not specified**
   - Location: `20_design/scaffolding.json` → SwimlaneRenderer.tsx → private_objects[2] (buildWeekGrid)
   - Observation: The scaffolding describes `buildWeekGrid` as returning "a structure that SwimlaneRenderer uses to render week rows with correct month labels" but does not name or define that structure. The two other private functions (`buildEventMap`, `getIntensityClass`) have sufficiently clear return semantics. `buildWeekGrid` is the most complex private function and will require the implementer to invent its output shape.
   - Impact on implementation: Low risk in isolation, but the ambiguity compounds with the transposed grid layout specification. An incorrect week structure can misalign month labels or produce incorrect row counts.

2. **CalendarPage removal_notes are implementation instructions, not scaffold**
   - Location: `20_design/scaffolding.json` → CalendarPage.tsx → removal_notes
   - Observation: The three removal_notes items ("Remove activeSrc state", "Remove all imports and references to HeatmapRenderer", "Replace HeatmapRenderer usage with SwimlaneRenderer") are implementation tasks, not structural scaffold declarations. They are useful but belong in the implementer deferrals section of architecture.json, where identical language already appears.
   - Impact on implementation: Duplication only; no functional risk.

---

## Hard Rule Violations

None identified.

The design is correctly classified as `03_Application`. Platform components (ErrorCard, Skeleton, apiFetch, isApiError) are consumed, not defined. No domain logic leaks into Platform. The `application` field is consumed as a grouping key without Chronicle assigning business meaning to it outside its own boundary. The Blueprint SQL view is consumed read-only. The PATCH endpoint writes only to the Blueprint-owned selection table with no schema change. The Dataset contract exception is correctly documented and consistent with the established Sprint01 precedent.

---

## Open Uncertainties

1. **Optimistic update intent: apply-then-rollback or confirm-then-apply**
   - Location: `20_design/architecture.json` → `internal_flow[2]`; `contracts.failure_modes[2]`
   - Uncertainty: The design uses "optimistic update" and "rollback" but the Sprint01 implementation uses confirm-then-apply. These are incompatible patterns. The design must declare which applies in Sprint02.
   - Why it matters: Changes the state management shape of CalendarPage. Optimistic update requires a prior-state snapshot; confirm-then-apply does not. Implementer cannot choose without guessing.
   - Suggested owner: Architecture

2. **Cross-group selection enforcement point**
   - Location: `20_design/architecture.json` → `open_questions[0]`
   - Uncertainty: Whether CalendarPage filters `selectedSources` to a single application group, or passes mixed-group sources through. The question is surfaced but unresolved.
   - Why it matters: If unresolved, SwimlaneRenderer has no defined behavior for mixed-group input and the acceptance criterion "cross-group combined rendering is not possible" has no verified enforcement path.
   - Suggested owner: Architecture

---

## Minimal Change Set

1. Resolve the optimistic-update question: either confirm that CalendarPage uses confirm-then-apply (matching the Sprint01 pattern, no snapshot needed), or declare that Sprint02 introduces true optimistic update with rollback and specify the snapshot mechanism. Update `internal_flow[2]` and `contracts.failure_modes[2]` to reflect the resolved decision.
2. Resolve the cross-group enforcement point: declare whether CalendarPage filters `selectedSources` to the first selected source's application value, or whether cross-group state is a stated accepted gap with no runtime guard. Remove the item from `open_questions` and add the decision as a stated invariant or stated risk.
3. Update `internal_flow[3]` (fetch_events_per_source) to state whether the year query parameter is passed explicitly by the client or omitted (relying on server default), and state the cancellation/ignore behavior for in-flight fetches when `sources` changes.

---

## Approval Condition

The design may proceed to implementation when all three items in the Minimal Change Set are resolved and recorded in the architecture artifact, leaving no open questions in `architecture.json`.
