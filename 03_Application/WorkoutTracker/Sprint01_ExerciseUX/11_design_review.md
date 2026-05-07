# Design Review — workout_tracker

**Verdict:** APPROVED
**Date:** 2026-05-06
**Reviewer:** sprint_design_reviewer

## Verdict
- Status: APPROVED
- Summary: The design is minimal, correct, and fully implementable. All three items from the draft are explicitly covered in internal_flow and scaffolding. The sprint correctly constrains itself to a single file change (ShellEntry.tsx), with no schema or endpoint additions. Open question about history sort order is appropriately deferred to the implementer. UI test spec is present with [UI — manual] scenarios for all three behaviors.

## Confirmed Problems

None identified.

## Recommended Improvements

1. **persistence_type inconsistency**
   - Location: `03_Application/WorkoutTracker/Sprint01_ExerciseUX/10_architecture.json §persistence`
   - Improvement: Change `"persistence_type": "postgres"` to `"persistence_type": "none"` (or `null`) since `owns_persistent_state` is `false` and no schema changes are made this sprint.
   - Why: The current value implies this sprint owns postgres state, which contradicts `owns_persistent_state: false`. A downstream reader scanning only the `persistence_type` field could be misled.

## Scaffold-Only Observations

1. **Existing directory listed unnecessarily**
   - Location: `03_Application/WorkoutTracker/Sprint01_ExerciseUX/10_scaffolding.json §directories`
   - Observation: `03_Application/WorkoutTracker/src` already exists and no new directories are created this sprint.
   - Impact on implementation: None — the implementer will not attempt to create an existing directory.

## Hard Rule Violations

None identified.

## Open Uncertainties

1. **History row sort order**
   - Location: `03_Application/WorkoutTracker/Sprint01_ExerciseUX/10_architecture.json §open_questions[0]`
   - Uncertainty: Whether `/workout/exercises/history` returns rows sorted by `workout_date` ascending, or if the frontend must sort before inserting `liveRow`.
   - Why it matters: If history rows are unsorted, the lexicographic insertion index will be wrong, placing `liveRow` at an incorrect position.
   - Suggested owner: Implementer — check the backend endpoint response and sort if needed before splicing.

## Minimal Change Set

None required — design is approved as-is.

## Approval Condition

None — approved as-is.
