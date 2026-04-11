# Design Corrections — LabelEngine

## Applied Changes

1. **Correct ORDER BY to lower(l.name)**
   - Review Source: `11_design_review.md` Recommended Improvements #1 / Minimal Change Set item 1 & 2
   - Files Updated: `10_architecture.json`
   - Change: `internal_flow[1].description` SQL changed from `ORDER BY l.name` to `ORDER BY lower(l.name)`; `contracts.invariants[1]` updated from "Results are ordered by label name ascending (case-insensitive consistent with existing search)" to "Results are ordered by lower(name) ascending"

2. **Replace misleading route-conflict risk note**
   - Review Source: `11_design_review.md` Recommended Improvements #2 / Minimal Change Set item 3
   - Files Updated: `10_architecture.json`
   - Change: `risks[0]` replaced. Old text implied a real FastAPI path-shadowing conflict between `/api/labels` and `/api/labels/used`; new text accurately states no conflict exists and reframes as a routine registration hygiene note.

## Unchanged by Design

All other sections of `10_architecture.json` and `10_scaffolding.json` were preserved verbatim. No new scope, no structural changes, no additions beyond the three targeted edits.

## Review Alignment Check

- Minimal Change Set Applied: Yes
- Approval Condition Satisfied: Yes — SQL ordering is now `lower(l.name)` (internally consistent), risk note is accurate.
- Notes: None.
