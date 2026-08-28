# Design Review — Calendar

**Verdict:** APPROVED
**Date:** 2026-05-07
**Reviewer:** sprint_design_reviewer

## Blocking Issues

_(None)_

## Non-Blocking Issues

| # | Location | Observation |
|---|----------|-------------|
| 1 | `10_architecture.json §interfaces.exposed_surfaces` | Extra non-schema fields (`params`, `body`, `patch_semantics`) embedded in exposed_surfaces entries. Additive and helpful for the implementer; not a contract violation. |
| 2 | `10_architecture.json §open_questions` | Inline resolutions make the open_questions section self-contained; conventions would place resolved decisions in contracts or internal_flow. Non-blocking. |

## Approval Condition

None — approved as-is.
