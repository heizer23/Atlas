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
