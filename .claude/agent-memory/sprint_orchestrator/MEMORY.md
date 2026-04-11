# Sprint Orchestrator — Memory Index

## Project
- [Notifications Sprint1 Pattern](project_notifications_sprint1.md) — First Platform-layer Notifications sprint; two-agent (Atlas Claude / Android Claude) delivery split via FCM payload boundary
- [CalendarConnector Sprint02 Pattern](project_calendar_connector_sprint2.md) — OAuth scope upgrade sprint; AWAITING_HUMAN_REVIEW; two operator deployment actions required before end-to-end testing
- [CalendarConnector Sprint03 Pattern](project_calendar_connector_sprint3.md) — Event lifecycle sprint (create/update/delete + Postgres event index); DRAFT_READY; three open questions unresolved in draft
- [TaskTracker Sprint02 Pattern](project_tasktracker_sprint02.md) — Effort field + mobile row + editable detail; DESIGN_APPROVED; human gate required before sprint_implement
- [LinkingEngine Sprint01 Pattern](project_linking_engine_sprint01.md) — Generic object-linking Platform service; AWAITING_HUMAN_REVIEW; pre-existing app code reconciled with design artifacts

- [LabelEngine Sprint01 Pattern](project_labelengine_sprint01.md) — Minimal label/object many-to-many; AWAITING_HUMAN_REVIEW; human gate required before sprint_implement_reviewer; design gap (AttachLabelRequest.object_type) resolved by implementer
- [LabelEngine Sprint02 Pattern](project_labelengine_sprint02.md) — Batch read endpoint (POST /api/objects/labels/batch); AWAITING_HUMAN_REVIEW; route ordering risk mitigated; fixes F-001 TaskTracker boundary violation
- [LabelEngine Sprint02_ReverseLookup Pattern](project_labelengine_sprint02_reverselookup.md) — GET /api/labels/used surgical addition; IMPLEMENTATION_IN_PROGRESS; one review cycle; ORDER BY lower() fix
- [NumericSeries Sprint01 Pattern](project_numericseries_sprint01.md) — Time-series measurement tracker; recharts sparkline; AWAITING_HUMAN_REVIEW; open question resolved as 404 on unknown label external write
- [StorageTracker Sprint01 Pattern](project_storagetracker_sprint01.md) — Household item tracker; SPRINT_COMPLETE; full automated loop; port 8022 (8020 taken by Notifications); tests written but run inside Docker

## Feedback
- [Skip specs reviewer stage](feedback_skip_specs_stage.md) — DRAFT_READY routes directly to designer; sprint_specs_reviewer is never used

## Reference
