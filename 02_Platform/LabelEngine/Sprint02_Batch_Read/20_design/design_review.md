# Design Review — label_engine Sprint02_Batch_Read

**Verdict:** APPROVED
**Date:** 2026-04-09
**Reviewer:** sprint_design_reviewer

## Blocking Issues

_(None)_

## Non-Blocking Issues

| # | Location | Observation |
|---|----------|-------------|
| 1 | `20_design/scaffolding.json` → `app/routers/objects.py` → `batch_labels` public_objects | The `public_objects` entry uses a `methods` array nested under a function kind, which is structurally unusual (methods arrays are for class kinds). The method body duplicates the function-level definition. No implementation ambiguity — minor scaffold schema inconsistency only. |
| 2 | `20_design/architecture.json` → `contracts.failure_modes` | `422 OBJECT_IDS_REQUIRED` is labelled as triggered by Pydantic validation; however the draft defines an empty `object_ids` list as valid (returns `{}` immediately). These are distinct cases — Pydantic validates field presence, the empty-list short-circuit is application logic. The distinction is clear from `internal_flow` step 1, so no implementation risk, but the failure_mode description could be tighter. |

## Approval Condition

None — approved as-is.
