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
