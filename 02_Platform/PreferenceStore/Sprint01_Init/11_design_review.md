# Design Review — PreferenceStore

**Verdict:** APPROVED
**Date:** 2026-04-10
**Reviewer:** sprint_design_reviewer

## Blocking Issues

_(None)_

## Non-Blocking Issues

| # | Location | Observation |
|---|----------|-------------|
| 1 | `10_architecture.json` → `deferrals.platform_implementer` / `10_scaffolding.json` → `app/models.py` → `PutPreferenceRequest.value` | `value: Any` in Pydantic v2 accepts the field but may not cleanly accept explicit `null` without `model_config` or `Optional[Any]`. The definition requires null to be a valid stored value. Implementer must verify the Pydantic model accepts `{"value": null}` without coercion or rejection. This is an implementation detail within the implementer's scope, but the design should call it out explicitly. |
| 2 | `10_architecture.json` → `open_questions` | Port 8060 is confirmed free based on inspection of existing compose.yml files (8020 Notifications, 8021 CalendarConnector, 8040 LinkingEngine, 8050 LabelEngine). Open question can be considered resolved. |

## Approval Condition

None — approved as-is. The design is complete, implementable, and compliant with all applicable rules. The Pydantic null-value concern is minor and within the implementer's normal scope.
