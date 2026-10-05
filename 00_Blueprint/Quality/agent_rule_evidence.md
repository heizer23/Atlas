# Agent Rule Evidence

Cumulative store of patterns observed during design reviews, implementation reviews, audits, and implementation runs.

**Governed by:** R-PRO-BP-02 (`.claude/rules/R-PRO-BP.md`)

Entries are observational and do not block current runs. Promotion into rules, agent instructions, or skills requires an explicit audit or human decision.

---

## Schema

```yaml
---
entry_id: EVD-YYYY-MM-DD-NNN
date: YYYY-MM-DD
source_agent: <agent name>
run_type: design_review | implementation_review | audit | implementer_note
component: <component name>
sprint: <sprint name or "n/a">
pattern_name: <short label — reuse across entries for the same pattern>
short_description: <one sentence>
evidence: "<exact quote or file:line reference>"
likely_root_cause: rule_gap | agent_gap | definition_quality | spec_ambiguity | none
candidate_response: rule | agent_instruction | skill | design_template | none
severity: critical | major | minor | informational
recurrence_hint: "<'First observed' or 'Also seen in EVD-...'>"
linked_immediate_artifact: <path to immediate artifact>
---
```

---

## Entries

---
entry_id: EVD-2026-04-09-001
date: 2026-04-09
source_agent: audit_architecture
run_type: audit
component: TaskTracker
sprint: Sprint05
pattern_name: inline_schema_drift
short_description: database.py init_schema() contains inline DDL that is two sprints behind schema.sql, omitting effort_hours and the pending status value.
evidence: "database.py:41-63 — init_schema() creates tasktracker.tasks with check (status in ('open', 'in_progress', 'done')); schema.sql:10-11 has ('open', 'in_progress', 'pending', 'done') and includes effort_hours column"
likely_root_cause: definition_quality
candidate_response: rule
severity: major
recurrence_hint: "First observed"
linked_immediate_artifact: 00_Blueprint/Quality/Tasktracker/Audit_Sprint05/Architecture_Audit_Report.md
---

---
entry_id: EVD-2026-04-09-002
date: 2026-04-09
source_agent: audit_architecture
run_type: audit
component: TaskTracker
sprint: Sprint05
pattern_name: proxy_endpoint_non_dataset_no_exception
short_description: Label proxy endpoints return LabelEngine-native response shapes rather than Dataset, with no formal exception record covering the deviation from R-CON-BP-04.
evidence: "tasks.py:352-425 — all six label endpoints return JSONResponse(content=resp.json()) verbatim; ShellEntry.tsx:435-436 destructures res.labels not res.rows; no ARCHITECTURE_EXCEPTIONS.md exists for TaskTracker"
likely_root_cause: rule_gap
candidate_response: rule
severity: major
recurrence_hint: "First observed — likely recurs wherever applications proxy platform service endpoints"
linked_immediate_artifact: 00_Blueprint/Quality/Tasktracker/Audit_Sprint05/Architecture_Audit_Report.md
---

---
entry_id: EVD-2026-04-09-003
date: 2026-04-09
source_agent: audit_architecture
run_type: audit
component: TaskTracker
sprint: Sprint05
pattern_name: direct_platform_schema_query
short_description: fetch_labels_for_tasks queries the LabelEngine's internal labels.* schema directly via SQL rather than calling the LabelEngine API, coupling TaskTracker to platform-internal DB layout.
evidence: "tasks.py:72-95 — SELECT from labels.object_labels and labels.labels using TaskTracker's own DB connection pool; write operations (attach/detach) use LabelEngine API via HTTP"
likely_root_cause: none
candidate_response: design_template
severity: major
recurrence_hint: "First observed — N+1 avoidance pattern; may recur in other applications that co-locate with platform services"
linked_immediate_artifact: 00_Blueprint/Quality/Tasktracker/Audit_Sprint05/Architecture_Audit_Report.md
---

---
entry_id: EVD-2026-04-09-004
date: 2026-04-09
source_agent: audit_architecture
run_type: audit
component: TaskTracker
sprint: Sprint05
pattern_name: current_architecture_staleness
short_description: CurrentArchitecture/ folder reflects Sprint02 state; Sprint04 and Sprint05 changes (grouping, views, pending, label proxy) are absent, misleading future agents.
evidence: "CurrentArchitecture/architecture.json:2 — sprint: Sprint02-Optimization_and_Effort; no mention of TaskGroupedList, ViewTab, pending_board, or set_task_labels"
likely_root_cause: rule_gap
candidate_response: rule
severity: minor
recurrence_hint: "First observed — likely systemic across applications that maintain CurrentArchitecture/ folders without a sprint-update gate"
linked_immediate_artifact: 00_Blueprint/Quality/Tasktracker/Audit_Sprint05/Architecture_Audit_Report.md
---

---
entry_id: EVD-2026-04-09-005
date: 2026-04-09
source_agent: audit_architecture
run_type: audit
component: TaskTracker
sprint: Sprint05
pattern_name: direct_platform_schema_read_no_exception
short_description: TaskTracker queries LabelEngine's internal labels.* schema directly via SQL for batch reads, bypassing the LabelEngine HTTP API with no formal exception record covering the boundary crossing.
evidence: "tasks.py:72-95 — fetch_labels_for_tasks executes SELECT from labels.object_labels and labels.labels using TaskTracker's own DB connection pool; write operations (attach/detach) use LabelEngine API via httpx; no ARCHITECTURE_EXCEPTIONS.md exists for TaskTracker"
likely_root_cause: rule_gap
candidate_response: rule
severity: major
recurrence_hint: "Also seen in EVD-2026-04-09-003 — same pattern, confirmed with deeper evidence; MS-002 suggests this will recur across any list-view application consuming platform label data"
linked_immediate_artifact: 01_System/AuditRuns/LabelEngine_auditrun_04_09_2026/Architecture_Audit_Report.md
---

---
entry_id: EVD-2026-04-09-006
date: 2026-04-09
source_agent: audit_architecture
run_type: audit
component: TaskTracker
sprint: Sprint05
pattern_name: proxy_endpoint_non_dataset_design_intent_not_followed
short_description: LabelEngine design artifact explicitly expected TaskTracker to serve Dataset-shaped responses to the UI from label proxy endpoints; the implementation passes through LabelEngine's native shapes verbatim with no exception record.
evidence: "architecture.json ui_implementer deferrals: 'serves Dataset-shaped responses to the UI where the UI contract applies'; tasks.py:352-425 all proxy endpoints return JSONResponse(content=resp.json()); ShellEntry.tsx:435-436,732-733,893-895 destructures res.labels not res.rows"
likely_root_cause: agent_gap
candidate_response: agent_instruction
severity: major
recurrence_hint: "Also seen in EVD-2026-04-09-002 — same root pattern; this entry adds evidence that the design explicitly anticipated Dataset transformation and the implementation departed without acknowledgment"
linked_immediate_artifact: 01_System/AuditRuns/LabelEngine_auditrun_04_09_2026/Architecture_Audit_Report.md
---

---
entry_id: EVD-2026-04-09-007
date: 2026-04-09
source_agent: audit_architecture
run_type: audit
component: TaskTracker
sprint: Sprint05
pattern_name: undeclared_dataset_row_field_as_frontend_logic_sidechannel
short_description: list_tasks embeds a labels array into Dataset rows not declared in TASK_SCHEMA; frontend TaskGroupedList reads this field for grouping logic, creating an undeclared payload side-channel with no Atlas rule governing the pattern.
evidence: "tasks.py:229-233 — r['labels'] appended to each row before Dataset construction; TASK_SCHEMA at lines 25-33 has 7 columns, labels absent; ShellEntry.tsx:1380 — const primary = task.labels?.[0]?.name used for group header logic; UI_Data_Contract.md §2 says undeclared fields are silently ignored by rendering primitives but is silent on app-logic consumption"
likely_root_cause: rule_gap
candidate_response: rule
severity: major
recurrence_hint: "First observed — governance gap MS-001; will recur wherever applications embed auxiliary data in Dataset rows for frontend logic"
linked_immediate_artifact: 01_System/AuditRuns/LabelEngine_auditrun_04_09_2026/Architecture_Audit_Report.md
---

---
entry_id: EVD-2026-04-09-008
date: 2026-04-09
source_agent: sprint_design_reviewer
run_type: design_review
component: TaskTracker
sprint: Sprint06_Label_Contract_Fix
pattern_name: frontend_call_site_enumeration_incomplete_in_draft
short_description: Draft and resulting design enumerated three ShellEntry.tsx call sites consuming res.labels; a fourth at ~line 1102 (TaskCreatePanel.handleLabelQueryChange) was missed and caught only on first design review, requiring a correction loop.
evidence: "design_review.md iteration 1: APPROVED_WITH_CHANGES — blocking issue: fourth call site at ShellEntry.tsx:1102-1103 not covered by architecture.json internal_flow step 4 or scaffolding.json; design_corrections.md confirms fix applied"
likely_root_cause: definition_quality
candidate_response: agent_instruction
severity: major
recurrence_hint: "First observed — pattern likely recurs whenever a draft describes frontend changes by partial enumeration rather than by querying the codebase for all usages of the affected pattern"
linked_immediate_artifact: 03_Application/TaskTracker/Sprint06_Label_Contract_Fix/20_design/design_review.md
---

---
entry_id: EVD-2026-04-09-009
date: 2026-04-09
source_agent: audit_architecture
run_type: audit
component: atlas_shell
sprint: n/a
pattern_name: application_domain_css_in_platform_stylesheet
short_description: TaskTracker-specific CSS classes (.tasks-toolbar, .tasks-filters, .filter-chip) were added to platform-ui/index.css, the platform-level design token and component stylesheet.
evidence: "platform-ui/index.css:610-645 — three CSS blocks with the comment '/* ─── Tasks page ─── */' define .tasks-toolbar, .tasks-filters, .filter-chip, and .filter-chip.active; no other application has corresponding blocks in this file; no platform UI primitive component uses these class names"
likely_root_cause: rule_gap
candidate_response: rule
severity: major
recurrence_hint: "First observed — will recur as each application adds custom page chrome; no rule currently prohibits application CSS blocks in platform-ui/index.css"
linked_immediate_artifact: 02_Platform/Atlas_Shell/Architecture_Audit_Report.md
---

---
entry_id: EVD-2026-04-09-010
date: 2026-04-09
source_agent: audit_architecture
run_type: audit
component: atlas_shell
sprint: n/a
pattern_name: exception_record_references_superseded_file
short_description: Both active exception records in ARCHITECTURE_EXCEPTIONS.md cite src/apps/index.ts as the deviating file, but this file does not exist; the actual mechanism is main.tsx side-effect imports of application shellConfig.ts files.
evidence: "ARCHITECTURE_EXCEPTIONS.md R-EXC-PC-01: 'defined in src/apps/index.ts'; R-EXC-PC-02: 'via React.lazy(() => import(\"@workout/ShellEntry\")) in src/apps/index.ts'; Glob(src/apps/**) returns no results; main.tsx:40-44 performs side-effect imports of 03_Application/*/src/shellConfig files"
likely_root_cause: definition_quality
candidate_response: none
severity: major
recurrence_hint: "First observed — pattern of exception records becoming stale after implementation refactoring"
linked_immediate_artifact: 02_Platform/Atlas_Shell/Architecture_Audit_Report.md
---

---
entry_id: EVD-2026-04-09-011
date: 2026-04-09
source_agent: audit_architecture
run_type: audit
component: atlas_shell
sprint: n/a
pattern_name: duplicated_aggregation_utility_across_chart_components
short_description: An identical agg() aggregation function (sum/avg/count/max/min) is copy-pasted verbatim into BarChart.tsx, LineChart.tsx, and ComboChart.tsx with no shared utility module.
evidence: "BarChart.tsx:102-112, LineChart.tsx:72-82, ComboChart.tsx:102-112 — all three define function agg(vals: number[], method: string): number with identical switch bodies; parameter type is string rather than the Aggregation union type defined in types.ts"
likely_root_cause: none
candidate_response: none
severity: major
recurrence_hint: "First observed — bounded to platform-ui chart components"
linked_immediate_artifact: 02_Platform/Atlas_Shell/Architecture_Audit_Report.md
---

---
entry_id: EVD-2026-04-09-012
date: 2026-04-09
source_agent: audit_architecture
run_type: audit
component: atlas_shell
sprint: n/a
pattern_name: platform_ui_hidden_shared_mutable_state
short_description: WarningPlaceholder mutates the internal request log ring buffer of client.ts by calling getRequestLog() and directly invoking unshift() on the returned live array reference, with no declared write interface.
evidence: "WarningPlaceholder.tsx:13-21 — const log = getRequestLog(); log.unshift({...}); client.ts:50 — export function getRequestLog(): RequestLogEntry[] { return requestLog; } returns the live array, not a copy; UI_Data_Contract.md §4 acknowledges the [PLATFORM GAP] injection behavior but does not specify the mechanism or which components may write to the log"
likely_root_cause: rule_gap
candidate_response: rule
severity: major
recurrence_hint: "First observed — governance gap MS-001; may recur as additional platform-ui components are built that need to surface diagnostic events"
linked_immediate_artifact: 02_Platform/Atlas_Shell/Architecture_Audit_Report.md
---

---
entry_id: EVD-2026-04-09-013
date: 2026-04-09
source_agent: audit_architecture
run_type: audit
component: atlas_shell
sprint: n/a
pattern_name: contract_document_version_header_mismatch
short_description: UI_Data_Contract.md header declares v0.4 but R-CON-BP-04 in the rule registry declares VERSION v0.5; the document body contains v0.5 content (§9 Endpoint Categories) but the version header was not bumped.
evidence: "UI_Data_Contract.md:3 — '> **Version:** v0.4'; UI_Data_Contract.md:258-267 — §9 Endpoint Categories and Dataset Obligation is present; UI_Data_Contract.md:291 — '- Added §9 (Endpoint Categories and Dataset Obligation)' listed under 'Changes from v0.3' while header still reads v0.4; R-CON-BP.md R-CON-BP-04: 'VERSION: v0.5'"
likely_root_cause: definition_quality
candidate_response: none
severity: major
recurrence_hint: "First observed — version header drift between rule registry and contract document"
linked_immediate_artifact: 02_Platform/Atlas_Shell/Architecture_Audit_Report.md
---

---
entry_id: EVD-2026-04-10-001
date: 2026-04-10
source_agent: sprint_design_reviewer
run_type: design_review
component: LabelEngine
sprint: Sprint02_ReverseLookup
pattern_name: invariant_sql_mismatch
short_description: Architecture invariant declared case-insensitive ordering but the SQL fragment used case-sensitive ORDER BY l.name; caught in design review and required correction.
evidence: "10_architecture.json contracts.invariants[1]: 'ordered case-insensitive consistent with existing search'; internal_flow[1].description SQL: 'ORDER BY l.name'; existing search_labels uses lower(name); corrected to ORDER BY lower(l.name) in 12_design_corrections"
likely_root_cause: definition_quality
candidate_response: agent_instruction
severity: major
recurrence_hint: "First observed — pattern likely recurs whenever a designer states a sorting invariant in prose but writes SQL separately without verifying alignment"
linked_immediate_artifact: 02_Platform/LabelEngine/Sprint02_ReverseLookup/11_design_review.md
---

---
entry_id: EVD-2026-04-11-001
date: 2026-04-11
source_agent: sprint_design_reviewer
run_type: design_review
component: StorageTracker
sprint: Sprint02_ShoppingTasks
pattern_name: cross_artifact_row_shape_inconsistency
short_description: The by_source endpoint row shape was declared as nested (source_tag + tasks list) in exposed_surfaces but flat (one row per task×source_tag) in internal_flow and test_spec, violating R-CON-BP-09.
evidence: "11_design_review.md blocking issue #1: 'exposed_surfaces says each row has source_tag: str and tasks: list of ShoppingTaskRow (nested); internal_flow.step_17 says one row per (task, source_tag) combination (flat); 10_test_spec.md also describes flat rows'"
likely_root_cause: definition_quality
candidate_response: agent_instruction
severity: major
recurrence_hint: "First observed — pattern likely recurs when a designer describes an aggregated view in exposed_surfaces conceptually (grouped) but designs the Dataset rows as flat"
linked_immediate_artifact: 03_Application/StorageTracker/Sprint02_ShoppingTasks/11_design_review.md
---

---
entry_id: EVD-2026-04-11-002
date: 2026-04-11
source_agent: sprint_design_reviewer
run_type: design_review
component: StorageTracker
sprint: Sprint02_ShoppingTasks
pattern_name: shared_row_type_column_omission
short_description: ShoppingTaskRow shared type definition omitted source_tags despite being required by both the list filter and the by_source view; caught as a blocking R-CON-BP-11 violation in design review.
evidence: "11_design_review.md blocking issue #2: 'ShoppingTaskRow does not include source_tags in the column list (lists: id, item_id, item_name, status, notes, created_at, completed_at); the by_source view requires source_tag per row and list endpoint is filtered by source_tag'"
likely_root_cause: definition_quality
candidate_response: agent_instruction
severity: major
recurrence_hint: "First observed — pattern: shared row type defined before all consuming endpoints are fully designed, leaving columns required only by later endpoints unaccounted for"
linked_immediate_artifact: 03_Application/StorageTracker/Sprint02_ShoppingTasks/11_design_review.md
---

---
entry_id: EVD-2026-04-12-001
date: 2026-04-12
source_agent: sprint_orchestrator
run_type: execution_issue
component: NumericSeries
sprint: Sprint02_ChronosAndUX
pattern_name: orchestrator_missing_bash_tool
short_description: The sprint orchestrator could not launch the test-runner stage because the Bash tool was unavailable in its execution context; required human to re-invoke the orchestrator in a context with Bash access.
evidence: "Sprint02_ChronosAndUX/99_sprint_log.md: '2026-04-12T00:15:00Z BLOCKED on test-runner: Bash tool not available in this orchestrator context; sprint_test_runner requires docker exec'"
likely_root_cause: agent_gap
candidate_response: agent_instruction
severity: major
recurrence_hint: "First observed — orchestrator agent definition does not explicitly require or verify Bash tool availability before routing to test-runner"
linked_immediate_artifact: 03_Application/NumericSeries/Sprint02_ChronosAndUX/99_sprint_log.md
---

---
entry_id: EVD-2026-04-12-002
date: 2026-04-12
source_agent: sprint_design_reviewer
run_type: design_review
component: NumericSeries
sprint: Sprint03_Chronos&UXpt2
pattern_name: time_authority_deferred_to_implementer
short_description: Design introduced a split date+time input but deferred the timezone encoding decision to the implementer, violating R-CON-AL-06 which requires the design to declare the authoritative time source and consistency strategy.
evidence: "10_architecture.json §internal_flow[5] (datetime_input): 'Implementer must choose one and document it'; §open_questions[0]: 'should the combined value be sent as naive local ... or UTC ... the design must resolve this'"
likely_root_cause: definition_quality
candidate_response: agent_instruction
severity: major
recurrence_hint: "First observed — time authority questions in UI input forms are consistently deferred to implementers rather than resolved in the design phase"
linked_immediate_artifact: 03_Application/NumericSeries/Sprint03_Chronos&UXpt2/11_design_review.md
---

---
entry_id: EVD-2026-04-14-001
date: 2026-04-14
source_agent: sprint_design_reviewer
run_type: design_review
component: FoodTracker
sprint: Sprint06_Search_Scale_Averages
pattern_name: missing_schema_artifact_when_persistence_declared
short_description: Designer declared persistence.owns_persistent_state == true and named 10_schema.sql as the schema artifact, but did not produce the file in the sprint folder.
evidence: "10_architecture.json §persistence: {owns_persistent_state: true, schema_artifact: '10_schema.sql'}; Glob(Sprint06_Search_Scale_Averages/10_schema.sql) returns no results"
likely_root_cause: definition_quality
candidate_response: agent_instruction
severity: major
recurrence_hint: "First observed in Sprint06 — first sprint to use the R-PRO-BP-01 v2 format for FoodTracker; prior sprints used legacy folder structure"
linked_immediate_artifact: 03_Application/FoodTracker/Sprint06_Search_Scale_Averages/11_design_review.md
---

---
entry_id: EVD-2026-04-14-002
date: 2026-04-14
source_agent: sprint_design_reviewer
run_type: design_review
component: FoodTracker
sprint: Sprint06_Search_Scale_Averages
pattern_name: missing_test_spec_with_tsx_in_scope
short_description: Scaffolding lists three .tsx files as changed but no 10_test_spec.md was produced, violating R-PRO-BP-01 §10 which requires a test spec with at least one UI scenario when frontend files are in scope.
evidence: "10_scaffolding.json §files: ReportPage.tsx, EntriesPage.tsx, EntryDetailPage.tsx all listed as changed; Glob(Sprint06_Search_Scale_Averages/10_test_spec.md) returns no results"
likely_root_cause: definition_quality
candidate_response: agent_instruction
severity: major
recurrence_hint: "First observed in Sprint06 — first FoodTracker sprint requiring a test spec under the new process contract; pattern may recur in first sprints of any application transitioning to R-PRO-BP-01 v2 format"
linked_immediate_artifact: 03_Application/FoodTracker/Sprint06_Search_Scale_Averages/11_design_review.md
---

---
entry_id: EVD-2026-04-14-003
date: 2026-04-14
source_agent: sprint_design_reviewer
run_type: design_review
component: FoodTracker
sprint: Sprint06_Search_Scale_Averages
pattern_name: stale_exception_contract_after_field_addition
short_description: Sprint adds a field (quantity_g) to a named exception contract (EntryDetail) but does not update the ARCHITECTURE_EXCEPTIONS.md field list, violating R-CON-BP-09.
evidence: "10_architecture.json §internal_flow[step 6]: adds quantity_g to _serialise_entry_detail; ARCHITECTURE_EXCEPTIONS.md §EXC-FT-03: EntryDetail field list is '{id, logged_at, meal_type, dish_name, kcal, protein_g, carbs_g, fiber_g, fat_g, good_fat_g, meat_g, red_meat_g, sodium_mg, confidence, notes, standard, source_standard_id}' — quantity_g absent"
likely_root_cause: definition_quality
candidate_response: agent_instruction
severity: major
recurrence_hint: "First observed — pattern: named contract defined in exception registry is not treated as a formal contract document requiring updates alongside each field addition sprint"
linked_immediate_artifact: 03_Application/FoodTracker/Sprint06_Search_Scale_Averages/11_design_review.md
---

---
entry_id: EVD-2026-04-14-004
date: 2026-04-14
source_agent: sprint_design_reviewer
run_type: design_review
component: FoodTracker
sprint: Sprint07_Base_Quantity
pattern_name: stale_exception_contract_after_field_rename
short_description: Sprint renames quantity_g to base_quantity in all code artifacts but does not instruct the implementer to update the EntryDetail named contract in ARCHITECTURE_EXCEPTIONS.md, violating R-CON-BP-09.
evidence: "10_architecture.json §internal_flow[step 5]: 'base_quantity replaces quantity_g'; ARCHITECTURE_EXCEPTIONS.md §EXC-FT-03: EntryDetail field list still includes 'quantity_g: float | null'; no deferral item targets ARCHITECTURE_EXCEPTIONS.md"
likely_root_cause: definition_quality
candidate_response: agent_instruction
severity: major
recurrence_hint: "Also seen in EVD-2026-04-14-003 — recurring pattern: ARCHITECTURE_EXCEPTIONS.md field list is not treated as a formal contract requiring update alongside every rename sprint"
linked_immediate_artifact: 03_Application/FoodTracker/Sprint07_Base_Quantity/11_design_review.md
---

---
entry_id: EVD-2026-04-30-001
date: 2026-04-30
source_agent: sprint_design_reviewer
run_type: design_review
component: PersonalDevelopment
sprint: Sprint01-Core
pattern_name: ownership_flag_contradicts_prose_note
short_description: Designer set owns_persistent_state=true while the notes field in the same section states "PersonalDevelopment does not own a schema", creating a direct intra-artifact boolean/prose contradiction.
evidence: "10_architecture.json §persistence: owns_persistent_state=true; §persistence.notes: 'PersonalDevelopment does not own a schema. The 10_schema.sql artifact contains ALTER TABLE migrations against tasktracker.tasks (owned by TaskTracker).'"
likely_root_cause: definition_quality
candidate_response: design_template
severity: major
recurrence_hint: "First observed — pattern: boolean ownership fields are set based on the presence of an SQL artifact rather than actual table ownership semantics; likely to recur in extension sprints that migrate foreign-owned tables"
linked_immediate_artifact: 03_Application/PersonalDevelopment/Sprint01-Core/11_design_review.md
---

---
entry_id: EVD-2026-04-30-002
date: 2026-04-30
source_agent: sprint_design_reviewer
run_type: design_review
component: PersonalDevelopment
sprint: Sprint01-Core
pattern_name: consumed_endpoint_absent_from_contracts
short_description: UnitDetailPage requires a child-task fetch endpoint to display training_session tasks, but no such endpoint is declared in contracts.consumes; the decision was deferred to the implementer rather than resolved in design.
evidence: "10_architecture.json §deferred_decisions[1]: 'Whether UnitDetailPage fetches child tasks via a dedicated endpoint or via GET /api/tasks?parent_task_id=<uuid>... owner: implementer'; §contracts.consumes: no child-fetch endpoint listed; §internal_flow step 4 lists unit.id as input without specifying how children are retrieved"
likely_root_cause: definition_quality
candidate_response: agent_instruction
severity: major
recurrence_hint: "First observed — pattern: open questions about which endpoint a page component uses are deferred to the implementer rather than resolved in design, making contracts.consumes incomplete"
linked_immediate_artifact: 03_Application/PersonalDevelopment/Sprint01-Core/11_design_review.md
---

---
entry_id: EVD-2026-05-03-001
date: 2026-05-03
source_agent: sprint_design_reviewer
run_type: design_review
component: FoodTracker
sprint: Sprint08_UI_Update
pattern_name: contradictory_internal_flow_branching
short_description: internal_flow step described two mutually exclusive implementation approaches for the same behavior, then chose one without cleanly removing the other, making the implementer's expected behavior undefined.
evidence: "10_architecture.json §internal_flow step 3 (json_logging_date_context): 'inject the selectedDate into the pastedJson by parsing it ... Alternatively (simpler and equally valid) ... Simpler approach chosen: prepopulate template only'"
likely_root_cause: definition_quality
candidate_response: agent_instruction
severity: major
recurrence_hint: "First observed — pattern: designer evaluates multiple implementation options inline within internal_flow rather than resolving to one approach before writing the artifact"
linked_immediate_artifact: 03_Application/FoodTracker/Sprint08_UI_Update/11_design_review.md
---

---
entry_id: EVD-2026-05-07-001
date: 2026-05-07
source_agent: sprint_design_reviewer
run_type: design_review
component: Calendar
sprint: Sprint01_Core
pattern_name: dependency_driver_inconsistency
short_description: Design introduced asyncpg (async Postgres driver) for a new application while every other Atlas application uses psycopg2 — no justification given, creating a codebase inconsistency.
evidence: "10_architecture.json §dependencies.external_required: asyncpg listed as required; all 03_Application components use psycopg2 (grep confirms 40+ files)"
likely_root_cause: agent_gap
candidate_response: agent_instruction
severity: major
recurrence_hint: "First observed — pattern: designer selects a technically-valid but non-canonical dependency without checking the established codebase pattern"
linked_immediate_artifact: 03_Application/Calendar/Sprint01_Core/11_design_review.md
---

---
entry_id: EVD-2026-08-27-001
date: 2026-08-27
source_agent: sprint_design_reviewer
run_type: design_review
component: EssayCards
sprint: Sprint01_Core
pattern_name: mutation_error_shape_bypass_on_malformed_body
short_description: Mutation endpoint's manual grade-value validation only covers the wrong-value case; a missing or wrong-typed body field triggers framework-level RequestValidationError, which the installed exception handler does not convert to ApiError, bypassing the R-CON-BP-04 error-envelope contract.
evidence: "10_architecture.json §interfaces.exposed_surfaces (POST .../review) and 10_scaffolding.json backend/routers/flashcards.py ReviewRequest: 'grade: str, deliberately not a Literal/enum so an invalid value is validated manually in the handler' — install_exception_handlers (02_Platform/packages/platform_errorhandling/logFastapi.py) only registers a handler for the generic Exception type, not RequestValidationError"
likely_root_cause: spec_ambiguity
candidate_response: agent_instruction
severity: major
recurrence_hint: "First observed — pattern: designer validates the anticipated bad-value input state but does not trace the full input-state space against which validation layer (Pydantic vs. handler) actually processes each state"
linked_immediate_artifact: 03_Application/EssayCards/Sprint01_Core/11_design_review.md
---

---
entry_id: EVD-2026-08-27-002
date: 2026-08-27
source_agent: sprint_design_reviewer
run_type: design_review
component: EssayCards
sprint: Sprint01_Core
pattern_name: stale_dependency_path_reference
short_description: architecture.json references a platform package via two different paths in the same document — one correct (matches dependencies.internal_required and actual repo layout), one stale/non-existent (matches an outdated reference also present in root CLAUDE.md).
evidence: "10_architecture.json §interfaces.consumes: 'platform_errorhandling from 02_Platform/03_ErrorHandling/' (path does not exist) vs §dependencies.internal_required: '02_Platform/packages/platform_errorhandling' (actual path, confirmed by filesystem search and StorageTracker's real import)"
likely_root_cause: definition_quality
candidate_response: rule
severity: major
recurrence_hint: "First observed — pattern: designer copied a stale path from root CLAUDE.md's Repository References section rather than verifying against the actual package location"
linked_immediate_artifact: 03_Application/EssayCards/Sprint01_Core/11_design_review.md
---

---
entry_id: EVD-2026-08-28-001
date: 2026-08-28
source_agent: sprint_implement
run_type: implementer_note
component: EssayCards
sprint: Sprint01_Core
pattern_name: nested_list_field_outside_columnschema
short_description: Resolved the design review's open uncertainty about the essay-detail Dataset's nested `sections` field by embedding it as a plain list-valued key on the single returned row, omitted from ESSAY_SCHEMA (ColumnSchema has no array/object ColumnType) — following the exact precedent already established by StorageTracker's item-detail `history` field.
evidence: "13_design_review.md §Open Uncertainties #1: 'No explicit ColumnSchema for the essay-detail Dataset's nested sections field ... Round 1 left this to the implementer (StorageTracker history-field precedent) ... Suggested owner: Implementer.' Implemented in backend/routers/essays.py get_essay(): row[\"sections\"] = [...] is set on the dict before constructing Dataset(**{\"schema\": ESSAY_SCHEMA}, rows=[row]) — sections is not listed in ESSAY_SCHEMA, mirroring StorageTracker/backend/routers/items.py get_item()'s row[\"history\"] = history."
likely_root_cause: definition_quality
candidate_response: design_template
severity: major
recurrence_hint: "Also seen in StorageTracker Sprint01/02 (history field) and Calendar — recurring gap: platform_contracts.ColumnSchema/ColumnType has no representation for nested/embedded list fields on a Dataset row, so every app that embeds detail sub-rows must independently decide to omit them from schema rather than following a documented convention"
linked_immediate_artifact: 03_Application/EssayCards/Sprint01_Core/13_design_review.md
---

---
entry_id: EVD-2026-08-28-002
date: 2026-08-28
source_agent: sprint_implement
run_type: implementer_note
component: EssayCards
sprint: Sprint02_JsonIngestion
pattern_name: unspecified_string_normalization_left_to_implementer
short_description: Resolved the design review's non-blocking "Recommended Improvement" about title/slug/body_markdown whitespace normalization by making POST /essays/ingest strip title, slug, heading, anchor_slug, and card id (matching the markdown CLI path's effective behavior — front-matter title/slug are `.strip()`ped, anchor_slug/card_key can carry no whitespace from their extraction source) while leaving body_markdown, q, and a stored verbatim (matching the markdown path, which never strips question/answer text).
evidence: "11_design_review.md §Recommended Improvements #1: 'Specify ... whether title and body_markdown are trimmed before being written into doc, and whether slug/anchor_slug/card id are trimmed before the regex is applied ... currently unaddressed by both 10_architecture.json and 10_scaffolding.json.' Implemented in backend/routers/essays.py::_validate_ingest_body() with an inline comment documenting the chosen split; verdict was APPROVED with this left open as a non-blocking improvement, so no design artifact update was required before implementation."
likely_root_cause: spec_ambiguity
candidate_response: design_template
severity: major
recurrence_hint: "First observed"
linked_immediate_artifact: 03_Application/EssayCards/Sprint02_JsonIngestion/11_design_review.md
---

---
entry_id: EVD-2026-08-28-003
date: 2026-08-28
source_agent: claude (main session, acting as implementer)
run_type: implementer_note
component: EssayCards
sprint: Sprint02_JsonIngestion
pattern_name: post_tests_passing_direct_ux_fixes_outside_agent_pipeline
short_description: Three UX fixes were applied directly to IngestView (src/ShellEntry.tsx) after Sprint02 had already reached TESTS_PASSING, in response to problems the human found during the required manual pass on the sprint's [UI — manual] scenarios — done by the coordinating session directly (Edit tool) rather than by re-invoking sprint_implement, since each fix was small, frontend-only, and did not touch the approved API contract, schema, or any tested backend behavior.
evidence: "User manual-testing feedback, in order: (1) 'the stub json should explain exactly how the json needs to be filled so chatgpt can fill it' -> added STUB_PROMPT (copy-to-clipboard fill-in prompt) and clipboard copy/paste buttons; (2) 'i still see \"title\": \"...\"' -> discovered the textarea's separate placeholder prop had never been updated to match, added self-documenting PLACEHOLDER_JSON; (3) JSON POST failed with unescaped internal quotes from LLM-generated content -> added an explicit escaping rule + a worked example demonstrating \\\" to STUB_PROMPT. None of these changed backend/routers/essays.py, 10_architecture.json, or 10_schema.sql; all 46 existing tests were unaffected (frontend-only, no new automated coverage added for the clipboard buttons themselves, which remain untested browser-API interactions)."
likely_root_cause: none
candidate_response: none
severity: major
recurrence_hint: "First observed — first EssayCards sprint where the human's own manual-UI-testing pass (required by the [UI — manual] convention) surfaced fixable issues before close, rather than just confirming behavior"
linked_immediate_artifact: 03_Application/EssayCards/Sprint02_JsonIngestion/99_sprint_log.md
---

---
entry_id: EVD-2026-08-30-001
date: 2026-08-30
source_agent: sprint_design_reviewer
run_type: design_review
component: EssayCards
sprint: Sprint03_Images
pattern_name: incomplete_failure_branch_contract
short_description: The image-scan design fully specifies the happy path but leaves the per-file failure branch under-contracted — the skipped[].reason enum differs across architecture/scaffold/flow, and the per-file transaction/savepoint boundary that continue-on-failure and intra-scan slug-collision resolution depend on is never stated.
evidence: "10_architecture.json exposed_surfaces POST /images/scan reason set 'not-an-image'|'format-mismatch'|'gif-too-large'|'too-large' vs internal_flow step 10(f) \"record skipped('error')\" and scaffolding SkippedFile adding 'error'; internal_flow step 10 says \"on INSERT failure unlink the file and record skipped('error') ... and continue\" with no commit/SAVEPOINT boundary, incompatible with psycopg2 whole-transaction abort and with 10_test_spec.md \"Scan resolves a slug collision\" for two never-before-seen files."
likely_root_cause: agent_gap
candidate_response: design_template
severity: major
recurrence_hint: "First observed"
linked_immediate_artifact: 03_Application/EssayCards/Sprint03_Images/11_design_review.md
---

---
entry_id: EVD-2026-08-30-002
date: 2026-08-30
source_agent: sprint_design_reviewer
run_type: design_review
component: EssayCards
sprint: Sprint03_Images
pattern_name: deferral_contradicts_fixed_decision
short_description: The correction that fixed the per-file transaction boundary hard-asserted "commit that file's row before moving to the next file" in internal_flow and the invariant, but left deferred_decisions item 4 still offering "a single commit after the batch" as an implementer choice — the deferral now contradicts the constraint it defers to.
evidence: "10_architecture.json deferred_decisions item 4 'per-file SAVEPOINTs with a single commit after the batch, vs. an explicit commit after each file ... is the implementer's choice, as long as the internal_flow step 10 boundary holds' vs internal_flow step 10(f) 'RELEASE the SAVEPOINT and commit that file's row before moving to the next file' and the [NEW] invariant 'that row is committed before the next file ... because prior in-scan imports are already committed, _resolve_slug sees their slugs'."
likely_root_cause: agent_gap
candidate_response: agent_instruction
severity: major
recurrence_hint: "Also seen in EVD-2026-08-30-001 (same sprint/design area — failure-branch and transaction-boundary contract left under-specified); this pass: correction resolved the boundary but did not sweep the pre-correction deferral that referenced it"
linked_immediate_artifact: 03_Application/EssayCards/Sprint03_Images/13_design_review.md
---

---
entry_id: EVD-2026-08-30-003
date: 2026-08-30
source_agent: sprint_implement
run_type: implementer_note
component: EssayCards
sprint: Sprint03_Images
pattern_name: new_backend_dependency_requires_test_image_rebuild
short_description: Sprint03 adds Pillow to pyproject.toml; the shared Dockerfile installs it, but the already-running atlas-essaycards and atlas-essaycards-test images predate the dependency, so both were rebuilt during implementation rather than left for the test-runner stage (which only docker-execs pytest, it does not rebuild).
evidence: "pyproject.toml dependencies += 'Pillow>=10'; 01_System/test/compose.test.yml essaycards-test builds from 03_Application/EssayCards/Dockerfile which runs 'pip install -e \".[dev]\"'. Implementer ran 'make essaycards-up' (config.env + secrets.env) and 'docker compose -f 01_System/test/compose.test.yml build essaycards-test'. Verified in-container: PIL 12.3.0, scan_staging downscales 2600x1300 -> 2000x1000, skips non-image + oversized GIF, per-file commit works."
likely_root_cause: none
candidate_response: none
severity: major
recurrence_hint: "First observed"
linked_immediate_artifact: 03_Application/EssayCards/Sprint03_Images/10_scaffolding.json
---

---
entry_id: EVD-2026-08-30-004
date: 2026-08-30
source_agent: sprint_implement
run_type: implementer_note
component: EssayCards
sprint: Sprint03_Images
pattern_name: implicit_psycopg2_begin_not_reliable_before_savepoint
short_description: scan_staging issued the per-file "SAVEPOINT import_one" assuming psycopg2's implicit BEGIN had already opened a transaction, but under the FastAPI run_in_threadpool request path the pooled connection was still IDLE, so SAVEPOINT raised NoActiveSqlTransaction (500) and broke 5 of 11 Sprint03 scan/get-image scenarios. Fix loop 1 added a _ensure_in_transaction(conn, cur) guard (issues "begin" only when conn.info.transaction_status == TRANSACTION_STATUS_IDLE) immediately before the SAVEPOINT, plus a trailing conn.rollback() at the end of scan_staging to return the pooled connection clean after the idempotency probes. Per-file SAVEPOINT/RELEASE/commit and ROLLBACK-TO-SAVEPOINT boundary from internal_flow step 10(f) is unchanged; no batch commit introduced.
evidence: "backend/import_images.py:262 cur.execute('savepoint import_one') -> psycopg2.errors.NoActiveSqlTransaction: SAVEPOINT can only be used in transaction blocks (50_test_report.md Failure Analysis 1). Other EssayCards modules (backend/ingest.py:101, backend/routers/examinations.py:96, backend/routers/flashcards.py:177) only ever call conn.commit()/conn.rollback() and never issue SAVEPOINT as the first statement, so none of them exposed this gap."
likely_root_cause: spec_ambiguity
candidate_response: none
severity: major
recurrence_hint: "First observed — specific to a module whose first DB statement in a unit of work is SAVEPOINT rather than DML; other EssayCards routers are not affected"
linked_immediate_artifact: 03_Application/EssayCards/Sprint03_Images/50_test_report.md
---

---
entry_id: EVD-2026-08-30-005
date: 2026-08-30
source_agent: direct_implementer
run_type: implementer_note
component: EssayCards
sprint: Sprint04_ImageUpload
pattern_name: bytes_first_core_drops_declared_extension_cross_check
short_description: Refactoring the Sprint03 per-file import into the bytes-first core process_image_bytes(conn, *, source_filename, raw, images_dir, save_original_dir=None) removed the staging path's declared-extension-vs-sniffed-format cross-check for VALID raster files. _process_image now takes ext as optional (None on the upload path, since a paste has no trusted extension); scan_staging keeps a filename-extension ACCEPT_EXTS pre-gate (so a .txt is still 'not-an-image' with no decode) but a staged file whose extension is in the accept list yet disagrees with a still-decodable format (e.g. photo.png containing JPEG bytes) is now imported as its real format instead of skipped 'format-mismatch'. No Sprint03 test covers that case (the collision test uses two real PNGs); all 11 Sprint03 scenarios pass unchanged. The 'format-mismatch' reason is still emitted by the upload endpoint for a detected SVG.
evidence: "backend/import_images.py _process_image: 'if ext is not None and fmt not in _EXT_TO_FORMATS.get(ext, set()): return \"format-mismatch\"'. scan_staging now calls process_image_bytes(..., save_original_dir=None) per file after an ACCEPT_EXTS suffix pre-gate; the draft (00_draft.md 'backend/import_images.py — refactor the per-file core to take bytes') specifies exactly this signature and 'ext from the sniffed format, not the filename'. docker exec atlas-essaycards-test pytest tests/test_images.py -v -> 18 passed (11 Sprint03 + 7 new)."
likely_root_cause: spec_ambiguity
candidate_response: none
severity: major
recurrence_hint: "First observed — inherent to moving from a filename-trusting staging importer to a sniff-only bytes core; acceptable because the sniffed format is authoritative and the mismatch branch guarded an untested corner"
linked_immediate_artifact: 03_Application/EssayCards/Sprint04_ImageUpload/00_draft.md
---

---
entry_id: EVD-2026-08-30-006
date: 2026-08-30
source_agent: direct_implementer
run_type: execution_issue
component: EssayCards
sprint: Sprint04_ImageUpload
pattern_name: preexisting_time_dependent_examinations_test_fails_on_current_date
short_description: Full-suite run (pytest tests/ -q) shows 1 failure unrelated to Sprint04 — test_examinations.py::test_import_stores_new_result_without_overwriting_history. The test posts an examination with hardcoded examined_at '2026-08-28T14:30:00Z' and asserts it sorts newest-first, but fixtures.sql inserts a section_examinations row at 'now() - interval 2 days'; on the current date (2026-08-30) that fixture row resolves to ~2026-08-28T15:27Z, i.e. newer than the hardcoded payload, so rows[0].score is 4 not 5. No Sprint04 code path touches examinations. tests/test_images.py is 18/18 green.
evidence: "pytest tests/ -q -> '1 failed, 80 passed'; failure at tests/test_examinations.py:103 'assert 4 == 5  # most recent first'. Fixture: tests/fixtures.sql se-origins-2 examined_at = now() - interval '2 days'. Payload: tests/test_examinations.py examined_at '2026-08-28T14:30:00Z'."
likely_root_cause: definition_quality
candidate_response: none
severity: major
recurrence_hint: "First observed by this agent; will recur whenever the wall clock is within ~2 days of the 2026-08-28 hardcoded timestamp — a TaskTracker/EssayCards fixture-vs-hardcoded-date smell"
linked_immediate_artifact: 03_Application/EssayCards/tests/test_examinations.py
---

---
entry_id: EVD-2026-09-21-001
date: 2026-09-21
source_agent: sprint_design_reviewer
run_type: design_review
component: EssayCards
sprint: Sprint09_Nuggets
pattern_name: client_derived_titlemap_incomplete_for_non_local_reference_source
short_description: The design derives a Markdown-reference title map client-side from a data source (per-section nugget associations) that does not cover all validly-accepted reference sites (main_spine_markdown), so a subset of valid references render as broken.
evidence: "10_architecture.json contracts.invariants: 'The essay's main_spine_markdown reuses the UNION of every section's nuggets field for its own titleMap (main_spine_markdown may reference a nugget introduced in any section)' — but essaycards.section_nuggets is resynced only from each section's own body_markdown (internal_flow step 4), never from main_spine_markdown, while ingest-time validation (internal_flow step 2) accepts references in main_spine_markdown independently of section co-reference."
likely_root_cause: spec_ambiguity
candidate_response: design_template
severity: critical
recurrence_hint: "First observed — general pattern: when a reference-resolution mechanism validates against a broader input set than the association/lookup mechanism populates from, references valid in the gap silently render as unresolved."
linked_immediate_artifact: 03_Application/EssayCards/Sprint09_Nuggets/11_design_review.md
---

---
entry_id: EVD-2026-09-21-002
date: 2026-09-21
source_agent: sprint_design_reviewer
run_type: design_review
component: EssayCards
sprint: Sprint09_Nuggets
pattern_name: backend_tristate_field_without_matching_ui_round_trip
short_description: POST /flashcards/upsert's nugget_id omit/null/value semantics are fully specified and implemented on the backend (R-CON-AL-04 compliant), but no UI affordance this sprint sends the null (clear) case or lets a user set nugget_id on a pre-existing card, and this gap was not declared as an explicit non-goal.
evidence: "10_scaffolding.json ui_implementer deferrals list every new UI addition for this sprint; none adds a nugget_id field/control to QuestionOverviewView's existing card-edit form. The only client caller that sets nugget_id is the one-way 'Generate flashcards from a nugget' create flow (always a value, never omitted/null)."
likely_root_cause: spec_ambiguity
candidate_response: design_template
severity: major
recurrence_hint: "First observed — general pattern: R-CON-AL-04's backend tri-state discipline is well internalized by this codebase (also seen correctly done in Sprint07/08), but R-CON-AL-05's UI-half of the round trip is not always checked against the same rigor."
linked_immediate_artifact: 03_Application/EssayCards/Sprint09_Nuggets/11_design_review.md
---

---
entry_id: EVD-2026-09-21-003
date: 2026-09-21
source_agent: sprint_design_reviewer
run_type: design_review
component: EssayCards
sprint: Sprint09_Nuggets
pattern_name: parallel_regex_character_class_drift
short_description: Two regexes governing the same identifier (author-time validation vs. reference-time extraction) were specified with different character classes, making a permitted identifier form permanently unreferenceable.
evidence: "10_architecture.json contracts.invariants item 4: 'the extraction regex's key character class is lowercase-only ([a-z0-9_-]+), while SLUG_LIKE_RE ... permits mixed case. A nugget_key containing an uppercase letter can therefore never be resolved by a [[nugget:key]] reference in any section/main-spine Markdown.' Self-surfaced in risks per R-OPS-BP-01 but left unfixed as a documented limitation rather than corrected."
likely_root_cause: spec_ambiguity
candidate_response: design_template
severity: major
recurrence_hint: "First observed — general pattern: when the same identifier is validated by one regex and matched/extracted by a second regex elsewhere in the same feature, character-class parity between them should be checked explicitly rather than assumed."
linked_immediate_artifact: 03_Application/EssayCards/Sprint09_Nuggets/11_design_review.md
---

---
entry_id: EVD-2026-09-23-001
date: 2026-09-23
source_agent: sprint_design_reviewer
run_type: design_review
component: EssayCards
sprint: Sprint10_DualSchedulerAB
pattern_name: derived_flag_defeated_by_unchanged_upstream_eligibility_invariant
short_description: A new per-review flag (was_due) was defined to separate rapid-retry reviews from genuine retention evidence, but the flag's truth condition is guaranteed true by an unrelated, correctly-preserved upstream eligibility invariant, so it can never actually evaluate false in production.
evidence: "10_architecture.json contracts.invariants: 'review_events.was_due is computed as (the card's next_due_at BEFORE this review) <= (the single now() read for this review) ... the field the experiment dashboard uses to separate ordinary due-review recall from non-ordinary reviews (mission §7)' — but GET /flashcards/due's unchanged base eligibility (frs.next_due_at <= now(), applies to both Review and Focus sessions per CLAUDE.md) means every card POST /review is ever called on, including RECENT-category rapid-retry resurfacing, already satisfies next_due_at <= now() at review time by construction."
likely_root_cause: spec_ambiguity
candidate_response: design_template
severity: major
recurrence_hint: "First observed — general pattern: a newly-introduced derived flag intended to distinguish two cases should be checked against every other invariant already governing when the underlying action (here, a review) can occur, not just against the flag's own local definition."
linked_immediate_artifact: 03_Application/EssayCards/Sprint10_DualSchedulerAB/11_design_review.md
---

---
entry_id: EVD-2026-09-23-002
date: 2026-09-23
source_agent: sprint_implement
run_type: implementer_note
component: EssayCards
sprint: Sprint10_DualSchedulerAB
pattern_name: test_client_fixture_retriggers_guarded_once_only_migration_per_test
short_description: "tests/conftest.py's function-scoped `client` fixture enters a fresh TestClient(app) context per test, which re-fires FastAPI's startup handler (and therefore backend/database.py::init_schema()) on every single test — turning a migration backfill designed to run once, ever, in production into something that reruns dozens of times per test session against whatever fixtures.sql just (re)inserted. Implementer fix: tests/fixtures.sql now ends its pre-Sprint10 fixture block with an explicit UPDATE pinning every row to scheduler='classic' with a non-null scheduler_assigned_at (legacy_retained_classic / migrated_never_reviewed_random as appropriate, deliberately overriding the hash outcome for test determinism), so the migration's WHERE scheduler_assigned_at IS NULL clause never matches these rows again regardless of rerun count; every new Sprint10-specific fixture row likewise sets its own scheduler_assigned_at explicitly at INSERT time."
evidence: "Sprint10_DualSchedulerAB/10_scaffolding.json's tests/fixtures.sql role text asserted 'Existing fixture rows ... will pick up scheduler=classic via the migration backfill's legacy_retained_classic / migrated_never_reviewed_random paths automatically at test schema init' — implying the backfill runs once, deterministically, against a stable fixture world. In fact conftest.py's `client` fixture (function-scoped, `with TestClient(app) as c:`) triggers backend/main.py's `@app.on_event('startup')` handler, which calls init_schema(), on every test — and since the never-reviewed migration branch uses a 50/50 hashtext(flashcard_id::text) hash (not a fixed 'classic' outcome), a pre-existing never-reviewed fixture card (e.g. fc000001/FC_ORIGINS_1) could deterministically hash to 'fsrs', silently breaking every pre-Sprint10 Classic-formula regression test that hardcodes that id — reproduced directly: `pytest tests/test_flashcards.py -k test_review_again_schedules_five_seconds` failed with a 60s FSRS learning-step interval instead of Classic's flat 5s, traced to fc000001 landing on scheduler='fsrs' via exactly this mechanism."
likely_root_cause: definition_quality
candidate_response: design_template
severity: major
recurrence_hint: "First observed — general pattern: a design that assumes a schema-migration backfill runs exactly once per test session should verify that assumption against the actual conftest.py fixture lifecycle (which apps in this repo trigger FastAPI's startup handler per-test vs. per-session) before relying on it for test determinism."
linked_immediate_artifact: 03_Application/EssayCards/Sprint10_DualSchedulerAB/99_sprint_log.md
---

---
entry_id: EVD-2026-09-23-003
date: 2026-09-23
source_agent: sprint_implement
run_type: implementer_note
component: EssayCards
sprint: Sprint10_DualSchedulerAB
pattern_name: new_fixture_rows_shift_preexisting_unscoped_exact_count_assertion
short_description: "Adding new flashcard fixtures (required by the test spec's FSRS/mix-scheduler scenarios) unavoidably changed the total row count GET /flashcards/stats (system-wide, unscoped, no opt-out) reports, breaking a pre-existing test's exact-count assertion. Implementer fix (not a design change, and not a test the sprint's scaffolding listed as new/changed): updated test_stats_system_wide_partitions_all_bands's expected due_now/within_1_day/sum values to the new, verified-against-a-fresh-fixture-load totals (19/5/29), with an inline comment explaining the Sprint10 Essay H contribution. Every new Essay H card was otherwise deliberately kept out of the stricter unscoped /due REVIEW query's own exact-match assertion by construction; only /stats, which has no scope-based opt-out at all, required updating an existing assertion."
evidence: "tests/test_flashcards.py::test_stats_system_wide_partitions_all_bands asserted an exact system-wide bucket-count dict (due_now: 15, within_1_day: 2, sum 22) with no scope parameter. GET /flashcards/stats has no per-card opt-out — every flashcard_review_state row in the database is counted when no scope is given. The test spec (10_test_spec.md) and scaffolding (10_scaffolding.json) both directed extending tests/fixtures.sql with new FSRS-cohort/classic-cohort/mix cards for the due-queue-agnostic and dashboard scenarios; several of those new cards are unavoidably due (next_due_at <= now()) to exercise RECENT/BACKLOG ordering, so they necessarily added to due_now (+4) and, for the two deliberately-not-due established cards, to within_1_day (+3) once /stats counts them — neither artifact anticipated or flagged this interaction."
likely_root_cause: spec_ambiguity
candidate_response: none
severity: major
recurrence_hint: "First observed — general pattern: when a test spec directs adding new fixture rows for scoped-query scenarios, any pre-existing UNSCOPED exact-count/exact-sum assertion elsewhere in the suite is a hidden coupling point that should be checked, since an unscoped aggregate has no way to exclude new fixture data by construction."
linked_immediate_artifact: 03_Application/EssayCards/Sprint10_DualSchedulerAB/99_sprint_log.md
---

---
entry_id: EVD-2026-09-24-001
date: 2026-09-24
source_agent: sprint_design_reviewer
run_type: design_review
component: StoryReader
sprint: Sprint01_Core
pattern_name: shell_registration_wiring_edit_omitted_from_design
short_description: Design scaffolds a new application's shellConfig.ts/AppRegistry.register() call correctly but never instructs the implementer to add the required side-effect import line to Atlas Shell's main.tsx, without which the app is never registered at all.
evidence: "10_scaffolding.json has an explicit nginx_note flagging the out-of-component nginx.conf edit, but no equivalent note for main.tsx; main.tsx:13-29 header comment states 'Add a side-effect import below' as step 2 of 'HOW TO ADD AN APPLICATION'; main.tsx:40-49 shows every currently-registered app requires this line; neither 10_architecture.json §deferrals.application_implementer nor §deferrals.ui_implementer mentions it."
likely_root_cause: agent_gap
candidate_response: agent_instruction
severity: major
recurrence_hint: "Related to EVD-2026-04-09-010 (exception records citing a stale main.tsx mechanism name) but a distinct pattern: here the actual current mechanism is correctly understood elsewhere in the repo, yet a new-application design still omits instructing the implementer to perform the required edit, despite correctly flagging the structurally identical nginx.conf edit in the same document."
linked_immediate_artifact: 03_Application/StoryReader/Sprint01_Core/11_design_review.md
---

---
entry_id: EVD-2026-09-24-002
date: 2026-09-24
source_agent: sprint_design_reviewer
run_type: design_review
component: StoryReader
sprint: Sprint01_Core
pattern_name: dataset_row_missing_required_id_field
short_description: A single-row Dataset-returning endpoint's declared row_shape omits the id field required by the platform Row type, while every other Dataset endpoint in the same design correctly includes it.
evidence: "10_architecture.json §interfaces.exposed_surfaces GET /api/storyreader/stories/{story_id}/versions/{version} row_shape: '{ story_id, version, title, paragraphs: [...], created_at }' — no id field; UI_Data_Contract.md §2: 'Every row must have an id field (string) | WarningPlaceholder if missing'; contrast with the same document's GET /stories, GET /stories/{story_id}, and GET .../annotations row_shapes, which all include id."
likely_root_cause: agent_gap
candidate_response: agent_instruction
severity: major
recurrence_hint: "First observed — general pattern: a single-row Dataset endpoint built around a natural composite key (story_id+version here) is more likely to drop the generic id field than a list endpoint, where id's necessity for row identity is more obviously visible."
linked_immediate_artifact: 03_Application/StoryReader/Sprint01_Core/11_design_review.md
---

---
entry_id: EVD-2026-09-24-003
date: 2026-09-24
source_agent: application_implementer
run_type: implementer_note
component: StoryReader
sprint: Sprint01_Core
pattern_name: test_spec_fixture_narrative_implies_incompatible_starting_states
short_description: 10_test_spec.md refers to "the fixture story 'lighthouse'" across scenarios that need mutually incompatible starting states — some require it to already have two versions and multiple annotations, others require a single-version story that ingestion then mutates — so one shared fixture row cannot literally satisfy all of them at once.
evidence: "10_test_spec.md 'Story list — marked-passage count' requires lighthouse to already have versions 1+2 with 2 annotations on v2 / 1 on v1; 'Ingestion — unchanged content is a no-op' requires 'the fixture story lighthouse' to have exactly one version whose body byte-matches a content file, unchanged by two ingestion runs; 'Publishing a new version never touches existing annotations' requires ingestion to create version 2 fresh (implying only version 1 exists beforehand) — these cannot all be true of one persistent fixture row loaded before every test."
likely_root_cause: spec_ambiguity
candidate_response: none
severity: major
recurrence_hint: "First observed — resolved locally by splitting into two fixture stories (tests/fixtures.sql): 'lighthouse' (slug 'lighthouse', 2 versions, pre-seeded annotations) serves every read-endpoint scenario; a second single-version story (slug 'tidepool', body byte-matching tests/fixtures_md/tidepool.md) serves the ingestion round-trip scenarios that mutate state via upsert_story(). Ingestion tests needing a different body/title for the same slug write a fresh temp <slug>.md via pytest's tmp_path fixture rather than a second static file with a mismatched filename, since backend/ingest.py's filename-must-equal-slug check would otherwise reject them. No architecture change was needed — this is a test-authoring resolution, recorded so a future test_spec.md avoids narrating one fixture name across scenarios with contradictory starting states."
linked_immediate_artifact: 03_Application/StoryReader/Sprint01_Core/10_test_spec.md
---

---
entry_id: EVD-2026-09-24-004
date: 2026-09-24
source_agent: interactive_session
run_type: execution_issue
component: StoryReader
sprint: Sprint03_ScrollAndResume
pattern_name: destructive_ab_experiment_against_live_target_during_user_testing
short_description: To isolate which code change fixed a bug, the agent built a deliberately-broken revert and docker cp'd it onto the LIVE atlas-shell container while the human was actively testing that same app — so a user-reported "still broken" could have been measuring the agent's own intentionally-broken build rather than the real fix.
evidence: "Session sequence: (1) fixed build deployed to atlas-shell; (2) slow-network Playwright test passes (scrollTop 2696); (3) agent reverted only the `loading` dependency, rebuilt, and ran `docker cp dist/. atlas-shell:/usr/share/nginx/html/` with the log line 'deployed-reverted-version-for-test'; (4) test fails (scrollTop 0) — A/B conclusive; (5) human's next message: 'still not'. The human was never told the live app had been intentionally broken, and step 5 may have been tested against step 3's build."
likely_root_cause: agent_gap
candidate_response: agent_instruction
severity: major
recurrence_hint: "First observed. The A/B itself was sound methodology and produced the decisive evidence (it is what proved the loading-dependency root cause over an earlier incorrect fonts.ready theory) — the failure is purely the choice of target. atlas-shell is the single shared serving container for EVERY Atlas app's frontend, so breaking it is never local to the app under test. Safer options: run the comparison against a throwaway copy of the container/directory, serve the reverted bundle under a distinct path, or (minimum) warn the human not to test for the duration and restore immediately after. Generalises to any deliberate break-it-to-confirm experiment on shared infrastructure a human is concurrently using."
linked_immediate_artifact: 03_Application/StoryReader/Sprint03_ScrollAndResume/99_sprint_log.md
---

---
entry_id: EVD-2026-09-26-001
date: 2026-09-26
source_agent: application_implementer
run_type: implementer_note
component: EssayCards
sprint: Sprint11_ReviewStats
pattern_name: new_review_events_fixture_rows_perturb_unrelated_endpoints_global_aggregation
short_description: 10_scaffolding.json's fixture guidance for GET /review-stats/summary ("add essaycards.review_events rows spanning ... at least one row with a short prior_review_interval") did not flag that any NEW flashcard/review-state row added to satisfy it would silently break two OTHER endpoints' pre-existing exact-count fixture assertions, because /review-stats/summary and /experiment/summary both aggregate essaycards.review_events with no essay/scope filter, and GET /flashcards/stats aggregates flashcard_review_state the same way.
evidence: "First attempt added a new essay/section/6 flashcards (fc000030-035) with dedicated review_events rows: tests/test_experiment.py::test_experiment_summary_reports_assigned_reviewed_completed_and_recall_with_sample_size failed ('assert 7 == 3' on completed_reviews) and test_experiment_summary_excludes_non_due_reviews_from_recall_sample failed ('assert 6 == 2' on ordinary_due_reviews) — because experiment.py's real query (`select scheduler, count(*) ... from essaycards.review_events group by scheduler`, no frs join) counts every row regardless of flashcard, while that test's own ground-truth query joins through flashcard_review_state, silently excluding orphan rows and diverging from reality once new flashcards without an frs row exist. Adding an frs row per new flashcard to fix that would in turn have broken tests/test_flashcards.py::test_stats_system_wide_partitions_all_bands's hardcoded exact system-wide horizon-band total (sum==29), which the Sprint10_DualSchedulerAB fixture comment already documents having to carefully dodge by construction."
likely_root_cause: spec_ambiguity
candidate_response: design_template
severity: major
recurrence_hint: "First observed. Resolved by attaching every new Sprint11 review_events row to the two PRE-EXISTING established cards (fc000025 classic / fc000023 fsrs) that already carry a flashcard_review_state row, and keeping every new row's prior_review_interval < 24h so it can never enter /experiment/summary's ordinary_due_reviews filter — zero new flashcards/frs rows introduced, so neither hardcoded assertion moved. Generalises to any future sprint adding review_events (or flashcard_review_state) fixture rows: check every OTHER unscoped-aggregation endpoint's existing tests for hardcoded exact totals over that same table before picking fixture ids, not just the new endpoint's own scenarios. A design/test-spec candidate_response would be a standing note in CLAUDE.md's '## Pattern references' or a fixtures.sql header enumerating which endpoints aggregate review_events/flashcard_review_state globally, so this is checked by construction rather than discovered by a failing run."
linked_immediate_artifact: 03_Application/EssayCards/Sprint11_ReviewStats/99_sprint_log.md
---

---
entry_id: EVD-2026-10-01-001
date: 2026-10-01
source_agent: sprint_design_reviewer
run_type: design_review
component: EssayCards
sprint: Sprint12_FSRSAndUXOverhaul
pattern_name: self_contradictory_function_signature_across_artifacts
short_description: A pure helper function's declared signature is stated inconsistently four times across 10_architecture.json and 10_scaffolding.json — three occurrences omit an input (last_reviewed_at) that the invariant text's own output field requires.
evidence: "10_architecture.json §contracts.invariants and §deferrals.application_implementer both write estimate_initial_fsrs_state(review_interval, desired_retention), as does 10_scaffolding.json's migrate_fsrs_state.py role text — yet the same invariant's field (e) 'last_review_at — the card's existing last_reviewed_at, used as-is' requires that input. Only 10_scaffolding.json's backend/scheduling.py public_objects entry declares the correct 3-arg form (review_interval, last_reviewed_at, desired_retention)."
likely_root_cause: agent_gap
candidate_response: agent_instruction
severity: major
recurrence_hint: "First observed"
linked_immediate_artifact: 03_Application/EssayCards/Sprint12_FSRSAndUXOverhaul/11_design_review.md
---

---
entry_id: EVD-2026-10-01-002
date: 2026-10-01
source_agent: sprint_design_reviewer
run_type: design_review
component: EssayCards
sprint: Sprint12_FSRSAndUXOverhaul
pattern_name: load_bearing_content_left_in_ephemeral_scratchpad
short_description: 10_architecture.json's deferred reviewer instruction depends on a "Phase A investigation" button/nav inventory that was deliberately written only to a session-scoped /tmp scratchpad, not the sprint folder, making the instruction unexecutable by any agent outside that one session.
evidence: "10_architecture.json §deferrals.reviewer: 'Confirm every button/action in the Phase A investigation A4 inventory is reachable somewhere post-consolidation'; 99_sprint_log.md: 'Phase A investigation findings live in the session scratchpad (/tmp/.../scratchpad/sprint12_phaseA_investigation.md), not as a sprint-folder artifact' — same pattern used uncritically in Sprint10_DualSchedulerAB (not flagged there)."
likely_root_cause: rule_gap
candidate_response: rule
severity: major
recurrence_hint: "Also present in Sprint10_DualSchedulerAB's design process (same scratchpad-only Phase A investigation convention), not previously flagged — now recurring across two sprints."
linked_immediate_artifact: 03_Application/EssayCards/Sprint12_FSRSAndUXOverhaul/11_design_review.md
---

---
entry_id: EVD-2026-10-01-003
date: 2026-10-01
source_agent: sprint_design_reviewer
run_type: design_review
component: EssayCards
sprint: Sprint12_FSRSAndUXOverhaul
pattern_name: component_reuse_claimed_without_checking_prop_contract
short_description: Design claims reuse of an existing component (ReviewStatsPanel's FORECAST_COLUMNS rendering) at a new call site whose available data does not satisfy that component's actual required props, with no refactor scoped to reconcile the two.
evidence: "10_architecture.json §internal_flow step 13 claims ReviewStatsView 'reuses ReviewStatsPanel's existing FORECAST_COLUMNS rendering' but ReviewStatsPanel (src/ShellEntry.tsx:2285-2328) requires session-only props (reviewed, backlog, newRemaining, sessionForecast, topic/essayId/sectionId) that have no equivalent on the scoped-free stats page; 10_scaffolding.json's ShellEntry.tsx private_objects diff does not list ReviewStatsPanel or FORECAST_COLUMNS as changed."
likely_root_cause: agent_gap
candidate_response: agent_instruction
severity: major
recurrence_hint: "First observed"
linked_immediate_artifact: 03_Application/EssayCards/Sprint12_FSRSAndUXOverhaul/11_design_review.md
---

---
entry_id: EVD-2026-10-01-004
date: 2026-10-01
source_agent: sprint_design_reviewer
run_type: design_review
component: HabitTracker
sprint: Sprint01_Core
pattern_name: dataset_sibling_field_mechanism_unspecified
short_description: Design declares a Dataset response with an additive top-level sibling field (period_summary) outside meta/schema/rows but never specifies the technical serialization mechanism, even though the canonical platform_contracts.Dataset pydantic model silently drops unrecognized constructor kwargs (no extra="allow"), and a working precedent for this exact pattern already exists unreferenced elsewhere in the codebase.
evidence: "10_architecture.json §interfaces.exposed_surfaces 'GET /api/habittracker/reports': 'ui_contract: Dataset | ApiError, PLUS one additive top-level sibling field outside the meta/schema/rows triad (period_summary ...)'; §internal_flow step 11: 'return as the additive Dataset response' (no mechanism named); platform_contracts/contracts.py:32-37 Dataset(BaseModel) has no extra='allow' in model_config; EssayCards backend/routers/review_stats.py:123-150 already solves this via response_model=None + dataset.model_dump() + manual JSONResponse, not cited anywhere in HabitTracker's design"
likely_root_cause: spec_ambiguity
candidate_response: design_template
severity: major
recurrence_hint: "First observed — general pattern: a designer correctly flags a Dataset-envelope deviation as a risk/open_question (good R-OPS-BP-01 practice) but stops short of specifying the concrete serialization mechanism required to make the deviation actually work against the canonical pydantic Dataset model, leaving a self-containment gap (R-CON-BP-08) even though a working precedent exists elsewhere in the codebase."
linked_immediate_artifact: 03_Application/HabitTracker/Sprint01_Core/11_design_review.md
---

---
entry_id: EVD-2026-10-01-005
date: 2026-10-01
source_agent: sprint_design_reviewer
run_type: design_review
component: HabitTracker
sprint: Sprint01_Core
pattern_name: non_pydantic_sibling_field_bypasses_json_serialization
short_description: The design correction that named the response_model=None + dataset.model_dump() + JSONResponse mechanism for attaching a non-Dataset sibling field specified the attachment structurally but did not account for the fact that values merged into the dict after model_dump() no longer pass through pydantic's JSON-mode serializer, so raw datetime.date fields in the sibling object will raise TypeError in Starlette's default json.dumps-based JSONResponse.
evidence: "10_architecture.json §internal_flow step 11: content[\"period_summary\"] = {period, anchor_date, period_start, period_end, dates, confirmed_days, elapsed_days} built from step 10's typed output (period_start: date, period_end: date — deliberately real date objects, used as SQL bind params in the same step's habit_rows query) and merged into content AFTER content = dataset.model_dump(by_alias=True, mode=\"json\") has already run; Starlette JSONResponse.render() uses stdlib json.dumps with no custom encoder."
likely_root_cause: spec_ambiguity
candidate_response: design_template
severity: critical
recurrence_hint: "Directly follows EVD-2026-10-01-004 (same sprint, same endpoint) — general pattern: once a correction specifies a response_model=None + manual JSONResponse escape hatch to attach a non-Dataset sibling field, every value merged into that dict after model_dump() must be independently re-verified for JSON-native types, since it no longer benefits from pydantic's mode=\"json\" serialization; likely to recur anywhere this attachment pattern is reused with a date/datetime/UUID/Decimal-bearing sibling field."
linked_immediate_artifact: 03_Application/HabitTracker/Sprint01_Core/13_design_review.md
---

---
entry_id: EVD-2026-10-01-006
date: 2026-10-01
source_agent: sprint_design_reviewer
run_type: design_review
component: HabitTracker
sprint: Sprint01_Core
pattern_name: non_pydantic_sibling_field_bypasses_json_serialization
short_description: The correction that fixed period_start/period_end's raw-date serialization bug in the same manually-built JSONResponse dict did not audit the one other value (anchor_date) undergoing the identical str-to-date type transition in the same function, leaving the predicted recurrence (EVD-2026-10-01-005) only partially closed.
evidence: "10_architecture.json §internal_flow step 10: resolve_report_period args 'period: str, anchor_date: date'; step 11 (compute_report) declared input 'anchor_date: str' with no named conversion pre-step; the corrected ui_contract Mechanism clause applies .isoformat() to period_start/period_end but not to anchor_date in the same content[\"period_summary\"] = {period, anchor_date, period_start: period_start.isoformat(), period_end: period_end.isoformat(), ...} dict literal."
likely_root_cause: spec_ambiguity
candidate_response: design_template
severity: major
recurrence_hint: "Also seen in EVD-2026-10-01-005 (same sprint, same endpoint, same correction round) — the predicted recurrence ('every value merged into that dict after model_dump() must be independently re-verified') materialized a second time, within the very fix meant to close the first instance. Strengthens the case for a design_template/checklist response: whenever a response_model=None + manual JSONResponse pattern is used to attach a sibling field, every field in that sibling dict must be enumerated and individually checked for JSON-native type, not just the field(s) already known to be problematic."
linked_immediate_artifact: 03_Application/HabitTracker/Sprint01_Core/15_design_review.md
---

---
entry_id: EVD-2026-10-01-007
date: 2026-10-01
source_agent: application_implementer
run_type: implementer_note
component: HabitTracker
sprint: Sprint01_Core
pattern_name: fixtures_sql_cannot_represent_both_populated_and_empty_table_preconditions
short_description: 10_test_spec.md's "starter seed present on first run" scenario requires a genuinely empty habittracker.habits table at GET-time, which conflicts with every other scenario needing fix-habit-* fixtures already loaded by the same shared tests/fixtures.sql, and with the conftest convention of never deleting/truncating inside a test body.
evidence: "10_test_spec.md: 'Given: a freshly started HabitTracker instance with no prior habits. When: GET /api/habittracker/habits is called. Then: exactly five habits are returned...' — this precondition (zero rows) cannot coexist with fixtures.sql populating the fix-habit-worked-out/no-sweets/no-vaping/bp/essaycards/archived rows that ~20 other scenarios in the same spec reference by name, since tests/conftest.py's autouse clean_tables fixture always truncates-then-reloads fixtures.sql identically before every test."
likely_root_cause: spec_ambiguity
candidate_response: none
severity: major
recurrence_hint: "First observed. Likely to recur for any component whose test spec includes both a 'fresh/empty state' scenario and many named-fixture scenarios sharing one global fixtures.sql — worth a design_template note if it recurs a second time."
linked_immediate_artifact: 03_Application/HabitTracker/Sprint01_Core/99_sprint_log.md

Resolution (not a design or rule change, a test-implementation choice): tests/fixtures.sql populates the six named habit fixtures needed by nearly every scenario (habittracker.habits is never left empty by the shared fixture load). The one scenario requiring true table-emptiness (`test_habit_list_starter_seed_on_first_run` in tests/test_habits.py) is the single, deliberate, explicitly-commented exception to "no truncate/delete in the test body": it truncates habittracker.daily_reviews/habits locally, within that one test only, then calls backend.database.seed_starter_habits() directly to exercise the real seeding code path. No other test performs a delete or truncate. The companion idempotency scenario ("seeding is a one-time, table-emptiness check") needed no such exception — it re-invokes seed_starter_habits() against the already-non-empty fixture state and asserts a no-op, which is what the scenario actually tests.
---

---
entry_id: EVD-2026-10-05-001
date: 2026-10-05
source_agent: sprint_design_reviewer
run_type: design_review
component: EssayCards
sprint: Sprint13_ReviewStatsSentenceFeedback
pattern_name: dual_purpose_state_variable_partial_removal_unaddressed
short_description: Design instructs removing one consumer of a dual-purpose frontend state variable (the Review page's old "Session" metric) without noting the variable's second, unrelated consumer (the completion-screen message) that must survive, unlike the adjacent sessionForecast removal in the same sprint which explicitly names its sole consumer and asks for a grep-confirmation before deletion.
evidence: "10_architecture.json internal_flow step 3/4 and 10_scaffolding.json ReviewStatsPanel/ReviewSessionView entries describe removing the Session/Backlog/New trio and the sessionForecast family (with an explicit 'confirm via grep that nothing else... references them before deleting' instruction) but say nothing about reviewedCount, which src/ShellEntry.tsx:2830 passes into ReviewStatsPanel as the now-obsolete 'Session' value AND src/ShellEntry.tsx:2858 independently uses for the completion-screen message, unaffected by this sprint."
likely_root_cause: definition_quality
candidate_response: agent_instruction
severity: major
recurrence_hint: "Related to EVD-2026-04-09-008 (incomplete call-site enumeration) — here the gap is not a missed call site but a missed SECOND PURPOSE of a variable whose first purpose is being removed, within a design that otherwise sets a good precedent (sessionForecast) for exactly this kind of check."
linked_immediate_artifact: 03_Application/EssayCards/Sprint13_ReviewStatsSentenceFeedback/11_design_review.md
---

---
entry_id: EVD-2026-10-05-002
date: 2026-10-05
source_agent: sprint_design_reviewer
run_type: design_review
component: EssayCards
sprint: Sprint13_ReviewStatsSentenceFeedback
pattern_name: nested_interactive_element_tap_precedence_unspecified
short_description: Design requires a tappable parent unit (sentence span, opens a feedback popover) to contain independently-tappable child elements (nugget/external links, preserved verbatim per an explicit requirement) with no stated click-event precedence or stopPropagation rule between the two.
evidence: "10_architecture.json internal_flow step 8 requires each sentence to be both a tap target opening SentenceFeedbackPopover and a ReactMarkdown render preserving 'nugget-ref clicks, links, images, bold per sentence fragment' with the identical remarkPlugins/urlTransform/components props as the whole-section render it replaces, but neither this step nor 10_scaffolding.json's SectionSentences/SentenceFeedbackPopover entries state which handler wins when a tap lands on the nested link."
likely_root_cause: spec_ambiguity
candidate_response: design_template
severity: major
recurrence_hint: "First observed — general pattern: a design that explicitly reuses an existing interaction pattern (whole-unit-tap-opens-popover) while also requiring preservation of independently-interactive content nested inside that same unit should state event-propagation precedence between the two, not just each behavior individually."
linked_immediate_artifact: 03_Application/EssayCards/Sprint13_ReviewStatsSentenceFeedback/11_design_review.md
---
