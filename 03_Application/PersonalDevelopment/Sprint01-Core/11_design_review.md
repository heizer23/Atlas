# Design Review — PersonalDevelopment (Learning Tile)

**Verdict:** APPROVED_WITH_CHANGES
**Date:** 2026-04-30
**Reviewer:** sprint_design_reviewer

---

## Confirmed Problems

1. **persistence.owns_persistent_state contradicts stated ownership**
   - Severity: Major
   - Location: `10_architecture.json §persistence`
   - Why it is a problem: `owns_persistent_state` is set to `true`, yet the notes section explicitly states "PersonalDevelopment does not own a schema." The field `owns_persistent_state` declares ownership of persistent state; the notes disclaim it. These are directly contradictory within the same artifact section. R-CON-BP-09 requires cross-artifact (and intra-artifact) truth consistency.
   - Impact: The orchestrator and implementer will read `true` and infer this component owns the schema. If an implementer applies migration instructions derived from this flag — e.g., running schema initialization for PersonalDevelopment as a separate service — it will fail or duplicate work.
   - Likely Cause (Design Phase): Cross-Artifact Truth Inconsistency — the designer correctly described the migration scope in prose but set the boolean field to reflect the presence of the SQL artifact rather than actual ownership semantics.

2. **GET /api/tasks/training-units response schema not declared in TRAINING_UNIT_SCHEMA**
   - Severity: Major
   - Location: `10_architecture.json §deferrals.application_implementer` (last item) and `§contracts.consumes[0]`
   - Why it is a problem: The design defers "Add TRAINING_UNIT_SCHEMA ColumnSchema list in TaskTracker for the training-units endpoint response" entirely to the implementer with no specification of what columns are in the schema. The TrainingUnitRow shape is declared in `shared_views.consumes[0]` and `10_scaffolding.json §types.ts`, but no corresponding ColumnSchema list enumerates the columns with their types and visibility flags. Without this, R-CON-AL-01 is violated: the endpoint's output contract is incomplete and every implementer must guess which columns appear in the Dataset schema block.
   - Impact: The implementer cannot build the Dataset response without making undocumented choices. Different implementations may omit `last_child_completed_at`, `completed_child_count`, or `total_child_count` from the ColumnSchema, making the response shape undefined.
   - Likely Cause (Design Phase): Incomplete Contract Thinking — the row shape (TrainingUnitRow) was specified at the TypeScript interface level but the parallel Dataset ColumnSchema — which is the server-side contract — was deferred rather than specified.

3. **UnitDetailPage child task fetch mechanism is unresolved at design time**
   - Severity: Major
   - Location: `10_architecture.json §deferred_decisions[1]` and `§internal_flow[step 4]`
   - Why it is a problem: The design explicitly defers to the implementer whether child tasks are fetched via a dedicated endpoint or via `GET /api/tasks?parent_task_id=<uuid>`. Step 4 of `internal_flow` (subtask_activation) lists `unit.id` as an input to the child-task display, and Step 2 (`learning_list_load`) only fetches training-units — it does not fetch children. UnitDetailPage must fetch children independently, but the endpoint that provides them is not declared in `contracts.consumes`. R-CON-AL-01 requires all endpoints consumed by the frontend to be enumerated. If `?parent_task_id=<uuid>` is used, it requires an undeclared query parameter extension to `GET /api/tasks`; if a dedicated endpoint is used, it requires an undeclared new endpoint. Neither is in `contracts.consumes`.
   - Impact: The implementer either adds an undeclared endpoint (invisible to the design reviewer) or adds an undeclared query parameter (which also changes the behavioral contract of an existing endpoint without design review). Either path is an undocumented boundary extension.
   - Likely Cause (Design Phase): Ambiguous Definition — the draft left child-fetch as an open question; the design promoted the question to a formal open_question but did not resolve it, violating the requirement that all API contracts be enumerated before implementation.

4. **Label filter deferred with no scope boundary defined**
   - Severity: Minor
   - Location: `10_architecture.json §deferred_decisions[0]` and `§deferrals.ui_implementer[2]`
   - Why it is a problem: The ui_implementer deferral states "Apply label filter bar to the Learning tile list (same mechanism as TaskTracker label filter, using PreferenceStore scope=learning.unit-list)" while `deferred_decisions[0]` simultaneously states "Whether PreferenceStore should be used … deferred to implementer." These two statements contradict each other — one prescribes the implementation mechanism, the other defers the decision. This is an internal design inconsistency violating R-CON-BP-09.
   - Impact: Minor — the implementer may implement the label filter without PreferenceStore persistence, then be blocked in test review because the deferral suggested they had a choice they did not have. Scope confusion, not a correctness risk.

---

## Recommended Improvements

1. **Set `owns_persistent_state` to false and update `schema_artifact` accordingly**
   - Location: `10_architecture.json §persistence`
   - Improvement: Set `owns_persistent_state: false`. The migration SQL in `10_schema.sql` should be retained as an artifact but the field name changed to something like `migration_artifact` with a note that it targets TaskTracker-owned tables. Alternatively, document this as a `controlled_deviation` (as parent_task_id is) with a clear note that the migration must be applied in TaskTracker's initialization path.
   - Why: Removes the direct contradiction and corrects the signal this field sends to downstream agents.

2. **Declare TRAINING_UNIT_SCHEMA columns in the architecture**
   - Location: `10_architecture.json §deferrals.application_implementer` (last item)
   - Improvement: Replace the open-ended deferral with a complete column enumeration matching TrainingUnitRow: id, title, status, priority, labels (type: object_list), last_child_completed_at (type: date), completed_child_count (type: number), total_child_count (type: number), actual_duration_minutes (type: number), completed_at (type: date), description (type: string, detail_visible: true).
   - Why: The implementer needs an unambiguous schema to produce a valid Dataset. This information is already implicitly present in TrainingUnitRow — it only needs to be formalized.

3. **Resolve child-task fetch endpoint in contracts.consumes**
   - Location: `10_architecture.json §contracts.consumes` and `§deferred_decisions[1]`
   - Improvement: Choose one option and declare it: either add `GET /api/tasks?parent_task_id=<uuid>` to `contracts.consumes` (and add this parameter to the TaskTracker deferrals list), or declare a dedicated `GET /api/tasks/{task_id}/children` endpoint. Remove it from `deferred_decisions`.
   - Why: An implementer building `UnitDetailPage` cannot proceed without knowing which endpoint to call. The deferral as-is means the fetch contract is invisible to reviewers.

4. **Remove the PreferenceStore scope prescription from ui_implementer deferrals, or promote it out of deferred_decisions**
   - Location: `10_architecture.json §deferrals.ui_implementer[2]` and `§deferred_decisions[0]`
   - Improvement: Either (a) make the PreferenceStore decision firm and remove it from `deferred_decisions`, or (b) remove the scope prescription from `ui_implementer deferrals` to avoid the contradiction.
   - Why: The current state gives the implementer conflicting instructions.

---

## Scaffold-Only Observations

1. **`test_markdown_subtasks.py` is a Python test for TypeScript logic**
   - Location: `10_scaffolding.json §files[7]` (`03_Application/PersonalDevelopment/tests/test_markdown_subtasks.py`)
   - Observation: The scaffolding lists a Python test module that mirrors the TypeScript `markdownSubtasks.ts` logic. The test spec scenarios for markdown parsing (`Markdown Parsing — Section Absent` etc.) describe calling `parseSubtasks()` — which is a TypeScript function. The Python file either re-implements the same parsing logic independently (drift risk) or tests a backend Python equivalent that is not declared anywhere in the architecture.
   - Impact on implementation: If the implementer writes this as a pure Python reimplementation of the TypeScript parser, it is untethered from the actual runtime logic and adds maintenance surface. If there is no Python backend equivalent, this file has no valid test target. The implementer may skip it or guess. Low risk to correctness, moderate risk to wasted effort.

2. **`ShellEntry.tsx` import path in `main.tsx` change entry**
   - Location: `10_scaffolding.json §files[9]` (`02_Platform/Atlas_Shell/src/shell/main.tsx`)
   - Observation: The scaffolded import path is `import '../../../../03_Application/PersonalDevelopment/frontend/shellConfig'`. The existing imports in `main.tsx` use the pattern `../../../03_Application/<App>/src/shellConfig` (three `../` levels from `src/shell/`). The design specifies four `../` levels and a `frontend/` directory (not `src/`). If the actual PersonalDevelopment shellConfig lives at `frontend/shellConfig.ts`, the relative depth from `src/shell/main.tsx` should be verified. This is a path correctness question, not a design flaw.
   - Impact on implementation: A wrong relative import path will silently fail to register the Learning tile at runtime. The implementer must verify the actual directory depth.

---

## Hard Rule Violations

1. **R-CON-BP-09 — Cross-Artifact Truth Consistency**
   - Rule Source: `.claude/rules/R-CON-BP.md §R-CON-BP-09`
   - Location: `10_architecture.json §persistence` — `owns_persistent_state: true` vs. `notes: "PersonalDevelopment does not own a schema"`
   - Violation: The boolean field and the prose note state opposite things about schema ownership within the same artifact section.
   - Required Fix: Set `owns_persistent_state: false`. Update `schema_artifact` field name or add a `migration_artifact` field with a note clarifying the migration targets a foreign-owned table.

2. **R-CON-AL-01 — Query Behavior Explicitness**
   - Rule Source: `.claude/rules/R-CON-AL.md §R-CON-AL-01`
   - Location: `10_architecture.json §contracts.consumes` — child task fetch endpoint absent
   - Violation: UnitDetailPage requires a read endpoint to fetch child tasks (`training_session` tasks by parent), but no such endpoint is declared in `contracts.consumes`. The endpoint's supported parameters, ordering, and empty-result behavior cannot be evaluated because the endpoint itself is not named.
   - Required Fix: Add the child-task fetch endpoint to `contracts.consumes` with full parameter, ordering, and empty-result specification.

---

## Open Uncertainties

1. **`completed_at` behavior on status reversion (done → open)**
   - Location: `10_architecture.json §contracts.consumes[2]` (PATCH endpoint) and `§risks[2]`
   - Uncertainty: The design specifies that `completed_at` is set server-side when `status` transitions to `done` and `completed_at IS NULL`. It does not specify what happens if status is reverted from `done` to `open` or `in_progress`. Should `completed_at` be cleared? Left as-is?
   - Why it matters: If a user marks a session done, then reopens it, the `completed_at` persists. This could cause the training_unit's `last_child_completed_at` to reflect an activity date that is no longer semantically "complete". The training_units sort order depends on this value.
   - Suggested owner: Architecture

2. **Schema migration application path**
   - Location: `10_architecture.json §persistence.notes` and `§deferrals.application_implementer[5]`
   - Uncertainty: The notes say the migration is applied "via TaskTracker's schema initialization path or as a separate migration script" — these are two different mechanisms. The dev ref confirms TaskTracker uses `database.py init_schema()` (see EVD-2026-04-09-001). It is unclear whether `10_schema.sql` will be added to that init path, run separately, or integrated with a migration runner.
   - Why it matters: If the migration is applied separately, it may not run during TaskTracker container startup, causing `column not found` errors. If added to `init_schema()`, it must be idempotent (which it is — IF NOT EXISTS is present), but the existing drift pattern (EVD-2026-04-09-001) makes this risky.
   - Suggested owner: Implementer

---

## Minimal Change Set

1. Set `persistence.owns_persistent_state` to `false` in `10_architecture.json`; document `10_schema.sql` as a migration artifact targeting TaskTracker-owned tables, not a self-owned schema.
2. Add the TRAINING_UNIT_SCHEMA column list to `10_architecture.json §deferrals.application_implementer` — enumerate all columns with types matching TrainingUnitRow.
3. Choose and declare the child-task fetch endpoint in `10_architecture.json §contracts.consumes`; remove it from `deferred_decisions`.

---

## Approval Condition

All three items in the Minimal Change Set are addressed in a `12_design_corrections.md`: `owns_persistent_state` is set to `false`, TRAINING_UNIT_SCHEMA columns are enumerated, and the child-task fetch endpoint is declared in `contracts.consumes`.
