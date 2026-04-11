# Design Review — TaskTracker — Sprint07_LabelFilter

**Verdict:** APPROVED_WITH_CHANGES
**Date:** 2026-04-10
**Reviewer:** sprint_design_reviewer

---

## Blocking Issues

| # | Location | Rule / Contract Violated | Required Change |
|---|----------|--------------------------|-----------------|
| 1 | `10_architecture.json` → `backend_layer.modified_endpoints[0].new_parameter.description` | R-CON-BP-09 Cross-Artifact Truth Consistency | The parameter description reads "When non-empty, restricts results to tasks that have at least one of the given labels attached." This contradicts `actual_implementation_design.description` which states the backend ignores the parameter and filtering is client-side. The description must match the actual behavior: "Accepted for forward-compatibility; in this sprint, filtering is applied client-side by the frontend using labels already embedded in task rows. Backend behavior is unchanged regardless of this parameter." |

---

## Non-Blocking Issues

| # | Location | Observation |
|---|----------|-------------|
| 1 | `10_architecture.json` → `frontend_layer.insertion_point.LabelFilterBar_rendered` | States "Only rendered when not in selected or creating state." — correct, since selected/creating states replace the page entirely with TaskDetailEdit/TaskCreatePanel. Implementer should note that `displayedTasks` and `activeLabels` derivation do not need guards for these states because the render path that shows them is never reached when selected/creating. |
| 2 | `10_architecture.json` → `frontend_layer.fetchTasks_changes.selectedLabelIds_update` | Specifies "Do not remove any existing selectedLabelIds entry." — implementer must confirm this does not cause stale label IDs to persist indefinitely when labels are detached from all tasks. For a personal-scale tool this is acceptable; no rule violation. |
| 3 | `10_scaffolding.json` → files[1].changes[4] | "Pass displayedTasks instead of tasks to TaskGroupedList and renderPendingTab." — `renderPendingTab` is an inner function closing over `tasks` state. The implementer must update it to close over `displayedTasks` instead, or receive it as a parameter. Sufficient guidance exists; implementer can resolve without ambiguity. |
| 4 | `10_architecture.json` → endpoint name "GET /tasks/labels/active" | Returns ALL globally-known labels, not just those with task attachments. Risk is documented and acknowledged. No rule violation; acceptable given LabelEngine constraints and personal-scale assumptions. |

---

## Approval Condition

Correct the `new_parameter.description` for the `label_ids` parameter in `10_architecture.json` so that it accurately describes the actual backend behavior (parameter accepted, filtering is client-side in this sprint). No other blocking changes required. After this correction, the design may proceed to implementation without further review.
