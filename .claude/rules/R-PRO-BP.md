# R-PRO-BP — Process Blueprint Rules

TYPE: PROCESS
SCOPE: BLUEPRINT
CANONICAL_SOURCE: .claude/rules/R-PRO-BP.md

---

# R-PRO-BP-01 — Sprint Process Contract

This document is the canonical definition of the Atlas sprint process.

When agent instructions, skill instructions, or older local sprint conventions conflict with this document, this document wins. The agent must follow this document and record the conflict in 00_Blueprint/Quality/agent_rule_conflicts.md.

**Prospective application** (`00_Blueprint/Rule_System.md §6`): This rule applies to sprints initiated after 2026-04-09. Sprint folders produced before this date are not required to conform and must not be flagged as violations.

---

## 1. Canonical Sprint Folder Structure

Every sprint is a flat folder containing numbered files. No subfolders.

```
Sprint<N>_<Title>/
  00_draft.md
  10_architecture.json
  10_scaffolding.json
  [10_schema.sql]              ← only if the component owns persistent state
  11_design_review.md
  [12_design_corrections.md]   ← only if first review required changes
  [13_design_review.md]        ← only if re-review needed
  [14_design_corrections.md]   ← only if second re-review needed
  ...
  99_sprint_log.md
```

### Naming conventions

- Sprint folder: `Sprint<N>_<Title>/` — no file extension, no trailing slash in references
- Draft: always `00_draft.md` — the human-authored input; the only required starting artifact
- Design artifacts: always `10_architecture.json` and `10_scaffolding.json` — no component-prefixed variants, no subfolders
- Schema: `10_schema.sql` if and only if `persistence.owns_persistent_state == true` in architecture.json
- Design review iterations: first review is always `11_design_review.md`. Each correction round increments by one: `12_design_corrections.md`, `13_design_review.md`, `14_design_corrections.md`, etc. The orchestrator determines the next number by counting existing review/correction files.
- Sprint log: always `99_sprint_log.md` — single file combining machine-readable state and the transition log

### What is explicitly not present

- No specs folder or specs agent step — `00_draft.md` is the design input directly
- No implementation notes file — implementation decisions go into code; design deviations go to `00_Blueprint/Quality/agent_rule_evidence.md`
- No implementation status file
- No implementation review file — the `/sprint-close` skill is the human gate and closes the sprint

---

## 2. Canonical Sprint States

Use exactly these seven states. No other labels are valid.

| State | Meaning |
|-------|---------|
| `DRAFT_READY` | `00_draft.md` exists; design not yet started |
| `DESIGN_CREATED` | `10_*.json` produced; not yet reviewed |
| `DESIGN_REVIEWED_CHANGES_REQUIRED` | Reviewer returned changes; corrector must run |
| `DESIGN_APPROVED` | Design approved; ready for implementation |
| `IMPLEMENTATION_IN_PROGRESS` | Implementer running or complete; awaiting `/sprint-close` |
| `SPRINT_COMPLETE` | `/sprint-close` skill invoked; sprint closed |
| `BLOCKED` | Required artifact missing, invalid verdict, or illegal transition |

---

## 3. Allowed State Transitions

```
DRAFT_READY
  → [application-designer | platform-designer]
  → DESIGN_CREATED

DESIGN_CREATED
  → [design-reviewer]
  → DESIGN_REVIEWED_CHANGES_REQUIRED  (verdict: CHANGES_REQUIRED or APPROVED_WITH_CHANGES)
  → DESIGN_APPROVED                   (verdict: APPROVED)

DESIGN_REVIEWED_CHANGES_REQUIRED
  → [design-corrector]
  → DESIGN_CREATED

DESIGN_APPROVED
  → [application-implementer | platform-implementer]
  → IMPLEMENTATION_IN_PROGRESS

IMPLEMENTATION_IN_PROGRESS
  → [/sprint-close skill invoked by human]
  → SPRINT_COMPLETE

Any missing required artifact, invalid verdict, or illegal stage skip
  → BLOCKED
```

Do not skip stages. Do not infer transitions from prose. Use explicit artifact evidence only.

---

## 4. Required Artifacts By State

| State | Required artifacts |
|-------|--------------------|
| `DRAFT_READY` | `00_draft.md` |
| `DESIGN_CREATED` | `00_draft.md`, `10_architecture.json`, `10_scaffolding.json` |
| `DESIGN_REVIEWED_*` or `DESIGN_APPROVED` | All DESIGN_CREATED artifacts plus the latest `1N_design_review.md` |
| `IMPLEMENTATION_IN_PROGRESS` | All DESIGN_APPROVED artifacts; implementation code present in the component |
| `SPRINT_COMPLETE` | All prior artifacts; `99_sprint_log.md` records `/sprint-close` invocation |

---

## 5. Reviewer Verdict Vocabulary

All reviewer agents must use exactly these verdict labels. No other labels are valid.

| Verdict | Produced by | Maps to state |
|---------|-------------|---------------|
| `APPROVED` | design-reviewer | `DESIGN_APPROVED` |
| `APPROVED_WITH_CHANGES` | design-reviewer | `DESIGN_REVIEWED_CHANGES_REQUIRED` |
| `CHANGES_REQUIRED` | design-reviewer | `DESIGN_REVIEWED_CHANGES_REQUIRED` |
| `BLOCKED` | any reviewer | `BLOCKED` |
| `REJECTED` | any reviewer | `BLOCKED` |

Rules:
- If a reviewer file does not contain an explicit verdict from this list, the orchestrator must mark the sprint `BLOCKED`.
- Do not infer a verdict from prose. The verdict must be explicitly stated.
- `APPROVED_WITH_CHANGES` and `CHANGES_REQUIRED` are equivalent from the design-reviewer — both route to the corrector.

---

## 6. Human Gate — `/sprint-close`

The human gate is the invocation of the `/sprint-close` skill. No other gate exists.

The `/sprint-close` skill:
- Records the close in `99_sprint_log.md` with a timestamp
- Sets `current_state` to `SPRINT_COMPLETE`
- Performs any required post-implementation cleanup (system map update, CurrentArchitecture update, etc.)

Do not wait for an implementation reviewer. Do not require an explicit approval note in any other file. The skill invocation is the record.

---

## 7. File Ownership

The sprint-orchestrator may create or update only `99_sprint_log.md`.

The orchestrator may recommend creation or correction of other sprint files but must not edit them directly.

---

## 8. `99_sprint_log.md` Format

Single file. State block at the top, transition log below. Keep the log to one line per transition.

```markdown
# Sprint Log — <sprint_name>

```json
{
  "sprint_name": "Sprint06_Label_Contract_Fix",
  "component_name": "TaskTracker",
  "layer": "03_Application",
  "current_state": "DESIGN_APPROVED",
  "last_agent": "sprint_design_reviewer",
  "next_agent": "sprint_implement",
  "blocking": false,
  "block_reason": null
}
```

## Log

- YYYY-MM-DD `DRAFT_READY` → `DESIGN_CREATED` [sprint_design_application]
- YYYY-MM-DD `DESIGN_CREATED` → `DESIGN_REVIEWED_CHANGES_REQUIRED` [sprint_design_reviewer] <one-line reason>
- YYYY-MM-DD `DESIGN_REVIEWED_CHANGES_REQUIRED` → `DESIGN_CREATED` [sprint_design_corrector]
- YYYY-MM-DD `DESIGN_CREATED` → `DESIGN_APPROVED` [sprint_design_reviewer]
- YYYY-MM-DD `DESIGN_APPROVED` → `IMPLEMENTATION_IN_PROGRESS` [sprint_implement]
- YYYY-MM-DD `IMPLEMENTATION_IN_PROGRESS` → `SPRINT_COMPLETE` [/sprint-close]
```

Field rules:
- `layer` must be exactly `02_Platform` or `03_Application`
- `current_state` must be one of the seven canonical states
- `blocking` must be `true` or `false`
- `block_reason` must be `null` unless `blocking` is `true`
- `next_agent` must be `null` when `current_state` is `SPRINT_COMPLETE` or `BLOCKED`

---

## 9. Blocker Conditions

Mark a sprint `BLOCKED` if any of the following apply:

- `00_draft.md` is absent when design is requested
- `10_architecture.json` or `10_scaffolding.json` is absent when review is requested
- A reviewer file contains no explicit valid verdict
- A design review requires changes but implementation is requested next
- Agent selection conflicts with the detected layer
- Artifact names or paths are ambiguous enough to prevent deterministic routing
- Two state-bearing artifacts contradict each other and no newer authoritative verdict resolves it

When blocking, state: the exact missing artifact or contradiction, the local consequence, and the required human or agent action.

---

## R-PRO-BP-02 — Review and Audit Artifact Structure

STATUS: ACTIVE
RELATES_TO: R-CON-BP-01, R-CON-BP-03, R-OPS-BP-01

Every review or audit run produces two artifacts with distinct purposes:

**Immediate artifact** — answers "what must change now." Sprint-local, optimized for the next actor, kept short and action-driving.

**Evidence entries** — answers "what does this teach us about the system." Appended to the cumulative store at `00_Blueprint/Quality/agent_rule_evidence.md`. Durable and observational.

### Immediate artifact

Applies to: `1N_design_review.md`, `audit_report.md`, and equivalent.

Strong convention — agents should follow this structure:

```
# [Review Type] — [Component] — [Sprint]

**Verdict:** APPROVED | APPROVED_WITH_CHANGES | CHANGES_REQUIRED | BLOCKED | REJECTED
**Date:** YYYY-MM-DD
**Reviewer:** [agent name]

## Blocking Issues

| # | Location | Rule / Contract Violated | Required Change |
|---|----------|--------------------------|-----------------|

_(None)_ if empty.

## Non-Blocking Issues

| # | Location | Observation |
|---|----------|-------------|

_(None)_ if empty.

## Approval Condition

What must be true for this review to resolve.
Write "None — approved as-is." if verdict is APPROVED.
```

This document is authoritative for the current run. It must not become a theory paper.

### Evidence entries

The evidence store is observational. Entries do not block the current run and do not mutate governance. Only audits and explicit human decisions may promote recurring evidence into rules, agent instructions, or skills.

Who may append:
- Any reviewer or auditor agent — after producing the immediate artifact (Major/Critical findings only)
- Implementers — when they compensated for a design gap or made a non-trivial deviation (run_type: `implementer_note`)

Schema for each entry — append as a YAML block:

```yaml
---
entry_id: EVD-YYYY-MM-DD-NNN
date: YYYY-MM-DD
source_agent: <agent name>
run_type: design_review | audit | implementer_note
component: <component name>
sprint: <sprint name or "n/a">
pattern_name: <short label — reuse across entries for the same pattern>
short_description: <one sentence>
evidence: "<exact quote or file:line reference>"
likely_root_cause: rule_gap | agent_gap | definition_quality | spec_ambiguity | none
candidate_response: rule | agent_instruction | skill | design_template | none
severity: critical | major
recurrence_hint: "<'First observed' or 'Also seen in EVD-...'>"
linked_immediate_artifact: <path to immediate artifact>
---
```

`candidate_response: none` and `likely_root_cause: none` are valid values — they preserve signal without implying a governance change is needed.
