# Design Review — LabelEngine

**Verdict:** APPROVED_WITH_CHANGES
**Date:** 2026-04-10
**Reviewer:** sprint_design_reviewer

## Blocking Issues

| # | Location | Rule / Contract Violated | Required Change |
|---|----------|--------------------------|-----------------|

_(None)_

## Non-Blocking Issues

| # | Location | Observation |
|---|----------|-------------|
| 1 | `10_architecture.json` `contracts.invariants[1]` + `internal_flow[1].description` (SQL) | Invariant states ordering is "case-insensitive consistent with existing search" but the SQL specifies `ORDER BY l.name` (case-sensitive collation). Existing `search_labels` uses `order by lower(name)`. These are inconsistent — labels beginning with uppercase would sort before lowercase. SQL should be `ORDER BY lower(l.name)` to honour the stated invariant. |
| 2 | `10_architecture.json` `risks[0]` | Risk note says `/api/labels/used` "may be shadowed by GET /api/labels". These are distinct path strings (`/api/labels` vs `/api/labels/used`); no shadowing is possible. FastAPI resolves path segments before query parameters. The risk note is misleading and should be removed or reworded to simply note that the implementer should verify route registration order as a hygiene check, not because a real conflict exists. |

## Confirmed Problems

_(None — no blocking issues found.)_

## Recommended Improvements

1. **Correct ORDER BY to lower(l.name)**
   - Location: `10_architecture.json` `internal_flow[1].description`
   - Improvement: Change SQL fragment from `ORDER BY l.name` to `ORDER BY lower(l.name)` and update the invariant to remove the parenthetical "consistent with existing search" (the corrected SQL makes this self-evident).
   - Why: Ensures case-insensitive alphabetical ordering consistent with all other label list surfaces in LabelEngine.

2. **Correct or remove misleading route-shadowing risk**
   - Location: `10_architecture.json` `risks[0]`
   - Improvement: Replace with: "Implementer should confirm that `/api/labels/used` is registered in the router before any catch-all route, as a standard hygiene check. No actual path conflict exists between `/api/labels` and `/api/labels/used`."
   - Why: The current text implies a real FastAPI routing conflict that does not exist; it could cause the implementer to add unnecessary workarounds.

## Scaffold-Only Observations

1. **`stub_kind: python_module_addition` is non-standard**
   - Location: `10_scaffolding.json` files[0] and files[1]
   - Observation: `python_module_addition` is not in the standard scaffolding schema. The scaffolding consumer may not understand this value.
   - Impact on implementation: Low — the role field and methods list are clear enough for a human implementer. No change strictly required, but worth noting.

## Hard Rule Violations

_(None)_

## Open Uncertainties

_(None)_

## Minimal Change Set

1. Update `internal_flow[1].description` SQL fragment: `ORDER BY l.name` → `ORDER BY lower(l.name)`
2. Update `contracts.invariants[1]`: remove parenthetical "case-insensitive consistent with existing search" and replace with "Results are ordered by lower(name) ascending"
3. Replace `risks[0]` text with accurate description of route registration hygiene (no actual conflict exists)

## Approval Condition

All three items in the Minimal Change Set are applied in the architecture artifact, producing an internally consistent SQL ordering statement and accurate risk description.
