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
