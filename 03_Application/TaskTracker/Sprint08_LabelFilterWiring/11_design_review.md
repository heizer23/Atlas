# Design Review — TaskTracker Sprint08_LabelFilterWiring

**Verdict:** APPROVED
**Date:** 2026-04-10
**Reviewer:** sprint_design_reviewer

## Blocking Issues

_(None)_

## Non-Blocking Issues

| # | Location | Observation |
|---|----------|-------------|
| 1 | `10_architecture.json` → `interfaces.exposed_surfaces` — PUT entry | `ui_contract` is declared as `"ApiError"` but the PUT endpoint proxies PreferenceStore which returns `PreferenceRecord` (a typed record) on 200. Per R-CON-BP-04, mutation endpoints may return a typed body on success. Declaring only `"ApiError"` could mislead the implementer into discarding the 200 body. Recommend `"PreferenceRecord | ApiError"`. |
| 2 | `10_architecture.json` → `classification.non_goals` | States "New backend endpoints beyond thin proxy additions" but the sprint adds three new proxy endpoints. The non_goal was intended to exclude new domain endpoints, not proxy routes. Wording is self-contradictory. No implementation risk — the intent is unambiguous from the rest of the design. |
| 3 | `10_scaffolding.json` → `files[0].public_objects` — `list_used_labels` | Does not explicitly state that this route must be declared before `GET /{task_id}/labels` in the router file. The existing `GET /labels/search` establishes the pattern, so the implementer will likely follow it — but explicit ordering guidance would reduce ambiguity. |

## Approval Condition

None — approved as-is. The design is complete, implementable without guessing, and all critical risks (value encoding, mount ordering, LabelEngine deployment dependency) are explicitly surfaced.
