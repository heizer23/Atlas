# Design Review — label_engine

## Verdict
- Status: APPROVED
- Summary: All three minimal change set items from the previous review (iteration 1) have been correctly addressed. The pagination model for GET /api/groups is now a declared design-time contract with unambiguous `total` semantics. The `object_type` casing invariant is declared in `contracts.invariants` and enforced by a CHECK constraint in `schema.sql`. The GET /api/labels?q= endpoint now declares case-insensitive prefix match in the endpoint contract. No regressions or new problems were introduced. The design is ready for implementation.

---

## Re-Review — Iteration 2 (2026-04-07)

### Minimal Change Set Verification

1. **Pagination model for GET /api/groups** — RESOLVED. `GroupedObjectsResponse` in `shared_views` includes `meta: { total, page, page_size, page_count }`. `internal_flow[6]` describes paginate-items-before-grouping with explicit `total` semantics. `deferred_decisions[0]` and `open_questions[2]` are marked RESOLVED with cross-references. `deferrals.platform_implementer` directs the implementer to the concrete model.
2. **`object_type` casing invariant** — RESOLVED. Invariant is declared in `contracts.invariants`. `schema.sql` adds `constraint object_labels_object_type_lowercase check (object_type = lower(object_type))`, which enforces the invariant at the database layer.
3. **Case-sensitivity of GET /api/labels?q=** — RESOLVED. `interfaces.exposed_surfaces[0]` now declares: case-insensitive prefix match with reference to `ix_labels_name_lower`. Example given (`q=out` matches `'Outside'`).

**Final verdict: APPROVED. No further design changes required before implementation.**

---

---

## Confirmed Problems

1. **Pagination contract for GET /api/groups is unresolved at design time**
   - Severity: Major
   - Location: `20_design/architecture.json` → `internal_flow[5]` (group_assembly), `deferred_decisions[0]`, `open_questions[2]`
   - Why it is a problem: The design explicitly states "implementer must choose and document in implementation_notes" between two semantically different pagination models (paginate items before grouping vs. paginate the group list). These two models produce different `total` values, different page counts, and different consumer behavior. The choice determines the API contract, not an implementation detail. A GroupedObjectsResponse that paginates items before grouping yields a `total` of matching objects; one that paginates groups yields a `total` of groups. Both are defensible but they are different contracts. Leaving this to the implementer means the contract is undefined at the design boundary.
   - Impact: The TaskTracker backend, which is the declared consumer of GET /api/groups, cannot be implemented to a stable contract until this decision is made. If the implementer and the TaskTracker implementer make different assumptions, the integration will fail silently (wrong total, incomplete groups, or missing items).
   - Likely Cause (Design Phase): Incomplete Contract Thinking — the pagination decision was recognized as needed but treated as an implementation detail rather than a contract decision.

2. **`object_type` is stored but not bounded — creates undeclared state**
   - Severity: Major
   - Location: `20_Design/schema.sql` → `labels.object_labels.object_type`, `20_design/architecture.json` → `contracts.invariants`, `contracts.failure_modes`
   - Why it is a problem: `object_type` is stored as a free-text column in `labels.object_labels` and is the only filter key for `GET /api/groups`. The design states "LabelEngine does not validate this value — callers supply it." No constraint, enumeration, or canonical source for valid values is declared. If a caller stores `"Task"` and another stores `"task"`, GET /api/groups will return two separate groups or miss data depending on the query. The design does not state whether `object_type` matching is case-sensitive. This is a state ownership gap: the set of valid `object_type` values is a contract dimension that has no declared owner.
   - Impact: Two callers can silently diverge on `object_type` casing or spelling, producing phantom empty groups or split results. The behavior is undefined in the architecture contract.
   - Likely Cause (Design Phase): State Ownership Ambiguity — `object_type` was added as a technical convenience column without assigning ownership of the value set to any actor.

---

## Recommended Improvements

1. **Resolve the pagination model in the design, not in implementation_notes**
   - Location: `20_design/architecture.json` → `deferred_decisions[0]`, `interfaces.exposed_surfaces[5]` (GET /api/groups)
   - Improvement: Choose one pagination model — recommended: paginate the flat object list before grouping, with `total` = total matching object count. Declare `total` and `page_count` fields in `GroupedObjectsResponse` or add a `meta` wrapper. Update `shared_views` to reflect the chosen response shape with pagination fields.
   - Why: The consumer (TaskTracker backend) requires a stable contract. This is a design-time decision, not an implementation detail.

2. **Declare `object_type` casing contract**
   - Location: `20_design/architecture.json` → `contracts.invariants`, `20_Data/schema.sql`
   - Improvement: Add an invariant stating that `object_type` values are case-sensitive and must be lowercase (e.g., `"task"`, not `"Task"`). Document this in the invariants list. Optionally add a CHECK constraint to the schema enforcing `object_type = lower(object_type)`.
   - Why: Without a declared casing convention, callers will diverge. A single sentence in the invariants list is sufficient.

---

## Scaffold-Only Observations

1. **`_run_inline_ddl` in database.py duplicates schema.sql — synchronization risk**
   - Location: `20_design/scaffolding.json` → `02_Platform/LabelEngine/app/database.py` → `private_objects._run_inline_ddl`
   - Observation: The scaffold specifies an inline DDL fallback that must be "kept in sync with 20_Data/schema.sql." This creates two authoritative sources for the same DDL. The `object_type` column and new indexes added in schema.sql may not be reproduced in the inline fallback.
   - Impact on implementation: If the inline fallback is used (e.g., in tests or a cold start without the file), the schema diverges. Implementer must ensure exact parity or remove the fallback and make schema.sql unconditionally required.

2. **No health endpoint scaffolded**
   - Location: `20_design/scaffolding.json` → `02_Platform/LabelEngine/app/routers/`
   - Observation: The open_questions note asks whether GET /health should be added for consistency with other platform services. No router or route for this is scaffolded.
   - Impact on implementation: Minor inconsistency with platform service conventions. Implementer will need to add it or explicitly document the omission.

---

## Hard Rule Violations

None identified.

---

## Open Uncertainties

1. **`object_type` casing and value set ownership**
   - Location: `20_design/architecture.json` → `contracts.failure_modes`, `20_Data/schema.sql` → `labels.object_labels.object_type`
   - Uncertainty: No declared owner, no enumeration, no casing rule for `object_type` values. Whether `"task"` and `"Task"` are the same or different is undefined.
   - Why it matters: All grouped query results depend on exact `object_type` matching. A casing mismatch between writer and reader produces a broken grouped view with no error.
   - Suggested owner: Architecture

2. **Label name case-sensitivity for search (GET /api/labels?q=)**
   - Location: `20_design/architecture.json` → `interfaces.exposed_surfaces[0]` (GET /api/labels), `internal_flow[3]` (label_resolution), `deferred_decisions[1]`
   - Uncertainty: The design defers case-sensitivity of label name search to the implementer. The `ix_labels_name_lower` index supports a case-insensitive prefix search, but the contract does not declare whether GET /api/labels?q=out matches "Outside". The attach path (`internal_flow[3]`) does declare case-insensitive exact matching for resolution, but the search endpoint contract is silent.
   - Why it matters: Label picker UX depends on this: if search is case-sensitive, typing "out" will not suggest "Outside" and the user sees a false "no match" state, triggering inline label creation for a duplicate.
   - Suggested owner: Implementer (with recommendation to match the case-insensitive approach already established for label resolution)

3. **Port 8050 collision status**
   - Location: `20_design/architecture.json` → `open_questions[0]`, `risks[3]`
   - Uncertainty: The atlas_system_map.generated.json does not include LabelEngine (it predates this sprint). Registered ports from compose.yml files: 8010 (TaskTracker), 8011 (WorkoutTracker), 8012 (FoodTracker), 8013 (Chronicle), 8020 (Notifications), 8021 (CalendarConnector), 8040 (LinkingEngine). Port 8050 is not assigned to any currently deployed service. However, the system map is dated 2026-03-20 and is not authoritative for new deployments.
   - Why it matters: If 8050 is occupied at deploy time, the service fails to start.
   - Suggested owner: Implementer (verify at deploy time; 8050 appears free based on current artifact evidence)

---

## Orchestrator-Flagged Item Disposition

1. **Pagination strategy for GET /api/groups** — Not documented. Decision is formally deferred to the implementer. Raised as Confirmed Problem #1.
2. **Case-sensitivity for label name matching** — Partially documented: case-insensitive exact match is established for the attach/resolve path (`internal_flow[3]`). The search endpoint (GET /api/labels?q=) case-sensitivity is not declared. Raised as Open Uncertainty #2.
3. **Dockerfile build context matches LinkingEngine pattern** — The scaffolding.json role for the Dockerfile states "copies platform_packages from repo root context." The LinkingEngine Dockerfile uses `context: ../..` (repo root) and copies `02_Platform/packages`. The LabelEngine compose.yml role declares the same pattern. This is correctly specified in the scaffold. No finding.
4. **Labels schema does not cross-reference other schemas** — schema.sql uses `labels.labels` and `labels.object_labels` only. The `label_id` foreign key references `labels.labels(id)` — an intra-schema reference. No cross-schema foreign keys exist. Confirmed clean.
5. **Port 8050 collision** — 8050 is not used by any service with a deployed compose.yml in the current codebase. No collision detected from available evidence. Raised as Open Uncertainty #3 for implementer verification at deploy time.

---

## Minimal Change Set

1. Resolve the GET /api/groups pagination model in `architecture.json` before implementation: choose paginate-items-before-grouping or paginate-groups, declare the chosen `total` semantics, and update `GroupedObjectsResponse` in `shared_views` to include pagination metadata.
2. Add an invariant to `architecture.json` → `contracts.invariants` declaring that `object_type` values are case-sensitive and must be lowercase. Optionally enforce with a CHECK constraint in `20_Data/schema.sql`.
3. Declare the case-sensitivity of GET /api/labels?q= in `architecture.json` → `interfaces.exposed_surfaces[0]` (recommended: case-insensitive prefix match, consistent with the index `ix_labels_name_lower` already present in schema.sql).

---

## Approval Condition

The design may proceed to implementation when the pagination model for GET /api/groups is declared as a contract decision in `architecture.json`, with `GroupedObjectsResponse` updated to reflect the chosen `total` semantics.
