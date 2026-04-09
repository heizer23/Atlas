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
