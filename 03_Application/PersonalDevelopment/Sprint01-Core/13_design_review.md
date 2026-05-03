# Design Review — PersonalDevelopment (Learning Tile)

## Verdict
- Status: APPROVED
- Summary: All three blocking issues from the first review are resolved. `persistence.owns_persistent_state` is correctly set to `false`, TRAINING_UNIT_SCHEMA columns are fully enumerated (11 columns matching TrainingUnitRow), and the child-task fetch endpoint is declared in `contracts.consumes` with complete specification. The PreferenceStore contradiction in `deferred_decisions` was also resolved. Two minor pre-existing observations remain but neither blocks implementation.

## Confirmed Problems
None identified.

## Recommended Improvements

1. **Remove stale `open_questions[1]` that contradicts the now-resolved `contracts.consumes`**
   - Location: `10_architecture.json §open_questions[1]`
   - Improvement: Remove the question "Should child tasks be fetched via a dedicated endpoint or via GET /api/tasks?parent_task_id=..." — `contracts.consumes[4]` already resolves this with `GET /api/tasks?task_type=training_session&parent_task_id=<uuid>`. The corrector noted this residual in `12_design_corrections.md` but left it in place.
   - Why: An implementer reading `open_questions[1]` may believe the fetch mechanism is still undecided, contradicting `contracts.consumes[4]`. Violates R-CON-BP-09 at a prose level. Non-blocking — contracts.consumes is the authoritative section.

## Scaffold-Only Observations

1. **UnitDetailPage fetches from "or single-task GET" — endpoint not declared**
   - Location: `10_scaffolding.json §files[3]` (UnitDetailPage.tsx purpose field)
   - Observation: Purpose says "fetches unit from GET /tasks/training-units (or single-task GET)". No `GET /api/tasks/{task_id}` exists in TaskTracker's declared endpoints (confirmed via `atlas_dev_ref.md`) and none is listed in `contracts.consumes`. The "or single-task GET" alternative is unresolved and references an undeclared endpoint.
   - Impact on implementation: Low — the implementer will likely resolve this by fetching from the list endpoint or filtering the list result by id. The absence of a single-task GET in TaskTracker means the implementer must use the list. No blocking risk, but the scaffolding comment creates unnecessary ambiguity.

2. **`test_markdown_subtasks.py` has no declared test target in the backend** (retained from first review — not addressed by corrections)
   - Location: `10_scaffolding.json §files[7]`
   - Observation: This is a Python test module whose declared role mirrors the TypeScript `markdownSubtasks.ts` logic. No Python backend equivalent of the parsing function is declared anywhere in the architecture or scaffolding. The `deferrals.test_writer` assigns this scenario to pytest, but the runtime logic is TypeScript-only.
   - Impact on implementation: Implementer may write a duplicate Python parser or skip the file. Neither outcome is traceable to a backend module. Low correctness risk; moderate effort waste risk.

## Hard Rule Violations
None identified.

## Open Uncertainties

1. **`completed_at` behavior on status reversion (done → open)** (retained from first review — not in Minimal Change Set)
   - Location: `10_architecture.json §contracts.consumes[2]` (PATCH endpoint) and `§risks[2]`
   - Uncertainty: The design specifies `completed_at` is set server-side when status transitions to `done` and `completed_at IS NULL`. It does not specify whether `completed_at` is cleared when status is reverted from `done` to `open` or `in_progress`.
   - Why it matters: If a user marks a session done then reopens it, `completed_at` persists. `last_child_completed_at` on the parent training_unit — which drives sort order — may then reflect an activity that is no longer semantically "complete".
   - Suggested owner: Architecture

2. **Schema migration application path ambiguous**
   - Location: `10_architecture.json §persistence.notes` and `§deferrals.application_implementer[5]`
   - Uncertainty: Notes say the migration is applied "via TaskTracker's schema initialization path or as a separate migration script." These are two different mechanisms. The dev ref confirms TaskTracker uses `database.py init_schema()`, which has a documented drift pattern (EVD-2026-04-09-001). No definitive path is chosen.
   - Why it matters: If applied separately, the migration may not run during TaskTracker container startup, causing column-not-found errors at runtime.
   - Suggested owner: Implementer

## Minimal Change Set
None required. The design is approved as-is.

## Approval Condition
None — approved as-is.
