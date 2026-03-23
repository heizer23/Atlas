# Design Review — food_tracker (Sprint 02: First Reporting Slice)

## Verdict
- Status: APPROVED_WITH_CHANGES
- Summary: The design is coherent, well-scoped, and correctly classified as Application layer. The internal flow, contract structure, and scaffold decomposition are implementable for the primary cases. Two problems require resolution before implementation: the `all_time + daily` scope has an unresolvable zero-fill enumeration gap (no period boundary is defined, so the bucket list cannot be constructed), and the `preview_model` shape for `POST /api/food/validate` is referenced but never formally declared in the Sprint 02 architecture artifact. One additional concern with implementer ambiguity in the ISO week SQL expression is flagged as a Major finding. These are targeted fixes; the overall design does not need to be reconsidered.

---

## Confirmed Problems

1. **`all_time + daily` bucket enumeration is undefined**
   - Severity: Critical
   - Location: `10_Design/component_architecture.json` → `internal_flow[7]` (step 8: `compute_bucket_boundaries`) and `contracts.invariants[11]` ("Zero-value bucket rows are generated for every date/period in the selected scope")
   - Why it is a problem: The sprint definition (Data Contract → Bucket Rules) lists `all_time + daily → day` as a valid combination. Step 8 says daily mode enumerates "every calendar day in the period." For `all_time` scope, there is no defined period boundary (no start date, no end date). The invariant that zero-fill produces a complete x-axis cannot be satisfied when the enumerable range is unbounded. The `_compute_buckets` helper signature (`query: ReportQuery`) gives the implementer no mechanism to determine day boundaries for this case. The risk section (risks[4]) describes the empty-data case but does not address the enumeration impossibility for non-empty data.
   - Impact: The implementer must invent a resolution (e.g., min/max from DB, hardcoded start year, skip zero-fill for this case) with no design authority to do so. Any invented resolution breaks the stated invariant or introduces hidden behavior. If the implementer skips zero-fill for `all_time + daily`, the x-axis will be sparse. If they query min/max first, they introduce an undeclared DB query.
   - Likely Cause (Design Phase): Incomplete Contract Thinking — the `all_time` scope was designed with the aggregated path in mind (year buckets are naturally bounded); the daily path was added to the sprint definition without propagating the boundary-definition requirement into the architecture.

2. **`preview_model` contract is undeclared in Sprint 02 architecture**
   - Severity: Major
   - Location: `10_Design/component_architecture.json` → `interfaces.exposed_surfaces[1]` (`POST /api/food/validate`, `ui_contract: "preview_model | ApiError"`)
   - Why it is a problem: The `preview_model` shape is defined in Sprint 01's definition (`FoodTracker01 — Manual JSON Intake.md`, §6.4) but is not reproduced or referenced as an explicit stable contract in the Sprint 02 `component_architecture.json`. The Sprint 02 architecture artifact is the authoritative design document for this sprint's implementation. An implementer reading only `component_architecture.json` cannot determine the exact response shape for `POST /api/food/validate`. The `ReportPage.tsx` does not consume the validate endpoint, but the `food.py` router (declared unchanged in Sprint 02) must still conform to it.
   - Impact: The validate endpoint's response shape is implicit. If an implementer modifies `food.py` for any reason, there is no authoritative contract artifact in Sprint 02 to verify against. This is an incomplete contract boundary for an interface that is explicitly declared as a provided surface.
   - Likely Cause (Design Phase): Ambiguous Definition — the Sprint 02 architecture forward-references Sprint 01 behavior without declaring which Sprint 01 artifacts govern it, leaving the contract expressed only in a prior sprint's definition document.

3. **ISO week SQL expression for `month + aggregated` group key is unspecified**
   - Severity: Major
   - Location: `10_Design/component_architecture.json` → `internal_flow[8]` (step 9: `query_food_logs`) and `10_Design/component_scaffold.json` → `files[5]` (`report.py`) → `private_objects._build_group_key_expr.purpose`
   - Why it is a problem: The `_build_group_key_expr` purpose field gives two examples (`to_char(logged_at,'YYYY-MM-DD')` for daily, `to_char(logged_at,'YYYY-MM')` for year+aggregated) but provides no example for the `month + aggregated → ISO week key` case. PostgreSQL's `to_char` with standard format codes does not directly produce `YYYY-WNN` ISO week format; the correct expression uses `IYYY` and `IW` format tokens (e.g. `to_char(logged_at, 'IYYY-"W"IW')`). Without specifying this, the implementer may produce a non-ISO week key (e.g. using `WW` which is not ISO), causing a mismatch between the group key in step 9 and the bucket ids generated in step 8.
   - Impact: If the group key in the SQL query does not match the bucket ids enumerated in `_compute_buckets`, the zero-fill merge in `_zero_fill` will produce all-zero rows for every bucket even when data exists. This is a silent data correctness failure that will not raise an error.
   - Likely Cause (Design Phase): Incomplete Contract Thinking — the bucket id format was specified (`YYYY-WNN`) but the SQL expression to produce that format was left to implementer discretion without noting the PostgreSQL-specific format token requirement.

---

## Recommended Improvements

1. **Define `all_time + daily` enumeration boundary behavior explicitly**
   - Location: `10_Design/component_architecture.json` → `internal_flow[7]` (step 8) and `contracts.invariants[11]`
   - Improvement: Add an explicit decision for how `_compute_buckets` determines the day range when `scope=all_time` and `mode=daily`. Two valid options: (a) query `MIN(logged_at)` and `MAX(logged_at)` from `foodtracker.food_logs` before step 8 and use those as the day boundary (requires declaring a pre-step DB query), or (b) exclude zero-fill for `all_time + daily` (make the invariant scope-conditional). The decision must be declared in the architecture, not left to the implementer.
   - Why: The current invariant is impossible to satisfy for `all_time + daily` without an undeclared mechanism. An implementer cannot invent this resolution without violating the contract.

2. **Declare `preview_model` as an explicit named contract reference in Sprint 02 artifacts**
   - Location: `10_Design/component_architecture.json` → `interfaces.exposed_surfaces[1]`
   - Improvement: Replace the bare reference `"preview_model | ApiError"` with an explicit citation of the governing artifact (e.g., `"preview_model (shape defined in 00_Requirements/FoodTracker01 — Manual JSON Intake.md §6.4) | ApiError"`). Add a note that `food.py` is unchanged and that the Sprint 01 definition governs its contract for this sprint.
   - Why: Without this reference, the Sprint 02 architecture artifact is incomplete as a standalone design document. The `provided` surface contract must be traceable from within the Sprint 02 artifacts.

3. **Specify the PostgreSQL ISO week format expression in `_build_group_key_expr`**
   - Location: `10_Design/component_scaffold.json` → `files[5]` (`report.py`) → `private_objects._build_group_key_expr.purpose`
   - Improvement: Extend the purpose field to include the explicit ISO week expression: `to_char(logged_at, 'IYYY-"W"IW')` for `month + aggregated`. Add a note that `IW` is the ISO week number (01–53) and `IYYY` is the ISO year, and that these must match the `YYYY-WNN` bucket id format exactly.
   - Why: PostgreSQL has two week-numbering systems (`WW` vs `IW`); the wrong choice produces a syntactically valid but semantically incorrect group key that silently mismatches the bucket enumeration.

---

## Scaffold-Only Observations

1. **`ChartPanel.isDrillable=false` click behavior is undefined in the scaffold**
   - Location: `10_Design/component_scaffold.json` → `files[6]` (`ReportPage.tsx`) → `public_objects.ChartPanel.args`
   - Observation: The `isDrillable: boolean` prop controls whether a bar click calls `onDrillDown`. The scaffold does not specify what the chart renders or how the bar click behaves when `isDrillable=false` — it does not say whether the bar is still clickable (but the callback is suppressed) or whether the chart renders without click affordance. This is a UI implementation decision but the boundary between parent-controlled state and chart-panel behavior is underspecified.
   - Impact on implementation: The implementer must decide unilaterally whether to visually suppress the drill affordance in daily mode. A cursor or tooltip difference between drillable and non-drillable states is not described. Low risk but may produce inconsistent UX without guidance.

2. **`_currentPeriodKey` uses browser clock; server time is canonical**
   - Location: `10_Design/component_scaffold.json` → `files[6]` (`ReportPage.tsx`) → `private_objects._currentPeriodKey.purpose`
   - Observation: The helper computes the default `period_key` on the frontend (e.g., current `YYYY-MM`) using browser local time. The sprint definition (System Behavior → Time Grouping) states "Use server time for this slice." The architecture does not resolve this tension. For the default load case, the frontend must supply a `period_key` that matches what the server considers "current" — if the client and server are in different timezones, the default period key may be one day or month off.
   - Impact on implementation: Low probability of divergence in a personal homelab context, but the design's stated principle ("use server time") conflicts with the implementation mechanism (client-supplied period_key computed from browser clock). The architecture deferred this decision without calling it a deferral.

---

## Hard Rule Violations

1. **Rule: Contracts and Boundaries (`03_contracts_and_boundaries.md`) — `preview_model` is an undeclared public interface**
   - Rule Source: `.claude/rules/03_contracts_and_boundaries.md`
   - Location: `10_Design/component_architecture.json` → `interfaces.exposed_surfaces[1]`
   - Violation: The rule requires that public interfaces be declared explicitly. `POST /api/food/validate` is a declared public surface, but its success response shape (`preview_model`) is not defined anywhere in the Sprint 02 architecture artifact. The contract is implicit, relying on a consumer reading a prior sprint's definition document.
   - Required Fix: The `preview_model` shape must be explicitly referenced (by artifact path and section) in `component_architecture.json` so the Sprint 02 design artifact is self-consistent as an interface declaration.

---

## Open Uncertainties

1. **`all_time + daily` zero-fill: DB scan vs. no-fill**
   - Location: `10_Design/component_architecture.json` → `internal_flow[7]` (step 8) and `contracts.invariants[11]`
   - Uncertainty: Whether zero-fill applies to `all_time + daily` and, if so, what the enumeration boundary source is (DB min/max vs. a defined start date vs. no zero-fill for this scope).
   - Why it matters: Any resolution changes the declared invariant and may require adding a pre-step DB query not described in the internal flow. An implementer cannot resolve this without changing the design.
   - Suggested owner: Architecture

2. **Server time vs. browser time for default `period_key`**
   - Location: `10_Design/component_scaffold.json` → `files[6]` (`ReportPage.tsx`) → `private_objects._currentPeriodKey.purpose`; sprint definition → System Behavior → Time Grouping
   - Uncertainty: The sprint definition says to use server time, but the only mechanism to supply `period_key` is a client-supplied query parameter. There is no `/api/food/current-period` endpoint or server-supplied default. The implementer must use the browser clock or add a server endpoint, neither of which is declared.
   - Why it matters: Timezone drift between client and server can cause the default report to load the wrong month on the user's first visit.
   - Suggested owner: Architecture

---

## Minimal Change Set

1. Define explicit behavior for `all_time + daily` bucket enumeration in `component_architecture.json` internal_flow step 8: either declare a pre-step DB query for `MIN(logged_at)`/`MAX(logged_at)`, or explicitly exclude zero-fill for `all_time + daily` with a scope-conditional update to invariant 11.
2. Add an explicit `preview_model` contract reference in `component_architecture.json` `interfaces.exposed_surfaces[1]`, citing the governing artifact (`FoodTracker01 — Manual JSON Intake.md §6.4`).
3. Add the exact PostgreSQL ISO week SQL expression (`to_char(logged_at, 'IYYY-"W"IW')`) to `component_scaffold.json` `_build_group_key_expr` purpose for the `month + aggregated` case.

---

## Approval Condition

The design may proceed to implementation when all three items in the Minimal Change Set are addressed in the design artifacts and the `all_time + daily` enumeration behavior is unambiguously declared with a single chosen resolution.
