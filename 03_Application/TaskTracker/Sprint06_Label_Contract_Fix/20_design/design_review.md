# Design Review — TaskTracker Sprint06_Label_Contract_Fix

**Verdict:** APPROVED_WITH_CHANGES
**Date:** 2026-04-09
**Reviewer:** sprint_design_reviewer

## Blocking Issues

| # | Location | Rule / Contract Violated | Required Change |
|---|----------|--------------------------|-----------------|
| 1 | `20_design/architecture.json` internal_flow step 4; `20_design/scaffolding.json` ShellEntry.tsx modifications | R-CON-BP-11 (Behavioral Completeness) | The design specifies three ShellEntry.tsx call sites (~435, ~732, ~893) but the actual file contains a **fourth** `{ labels: LabelRecord[] }` call site at lines 1102–1103 inside `TaskCreatePanel.handleLabelQueryChange`. This site calls `/tasks/labels/search` and casts the result as `{ labels: LabelRecord[] }` identically to the others. If left unchanged after the backend transform, it will silently receive a Dataset but attempt to access `.labels` (undefined), causing the autocomplete to stop working in the create panel. The design must include this call site. |

## Non-Blocking Issues

| # | Location | Observation |
|---|----------|-------------|
| 1 | `20_design/architecture.json` risks section | The risk "LabelEngine Sprint02 batch endpoint not yet deployed" is a deployment dependency, not a design risk. It is correctly identified and the silent-empty-dict fallback is an acceptable degradation posture. No design change required. |
| 2 | `20_design/scaffolding.json` ShellEntry.tsx modifications | The description for `apiFetch` type parameter change is phrased as an approximation (`{ rows: { id: string; name: string }[] }` rather than the full Dataset type). Acceptable for a fix sprint; the implementer should use the existing `Dataset` type import if available in the frontend, or a minimal structural type — both are implementable without ambiguity. |

## Approval Condition

Add the fourth ShellEntry.tsx call site (TaskCreatePanel lines ~1102–1103) to internal_flow step 4 and to the scaffolding.json ShellEntry.tsx modifications list, then this design may proceed directly to implementation.
