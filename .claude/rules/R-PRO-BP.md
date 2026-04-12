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
  [10_test_spec.md]            ← required if component exposes an API; omitted otherwise
  11_design_review.md
  [12_design_corrections.md]   ← only if first review required changes
  [13_design_review.md]        ← only if re-review needed
  [14_design_corrections.md]   ← only if second re-review needed
  ...
  [50_test_report.md]          ← produced by test-runner; present after first test run
  99_sprint_log.md
```

### Naming conventions

- Sprint folder: `Sprint<N>_<Title>/` — no file extension, no trailing slash in references
- Draft: always `00_draft.md` — the human-authored input; the only required starting artifact
- Design artifacts: always `10_architecture.json` and `10_scaffolding.json` — no component-prefixed variants, no subfolders
- Schema: `10_schema.sql` if and only if `persistence.owns_persistent_state == true` in architecture.json
- Design review iterations: first review is always `11_design_review.md`. Each correction round increments by one: `12_design_corrections.md`, `13_design_review.md`, `14_design_corrections.md`, etc. The orchestrator determines the next number by counting existing review/correction files.
- Test spec: `10_test_spec.md` — written by the designer; required when the component exposes an API, optional otherwise. If absent, the test-runner stage is skipped entirely. If `10_scaffolding.json` lists any `.tsx` files under `files_changed`, the test spec must include at least one UI scenario (even if execution infrastructure is not yet in place — the scenario documents the expected behavior and serves as the acceptance criterion).
- Test report: always `50_test_report.md` — produced by the test-runner on each run; overwritten on re-runs within the same sprint.
- Sprint log: always `99_sprint_log.md` — single file combining machine-readable state and the transition log

### What is explicitly not present

- No specs folder or specs agent step — `00_draft.md` is the design input directly
- No implementation notes file — implementation decisions go into code; design deviations go to `00_Blueprint/Quality/agent_rule_evidence.md`
- No implementation status file
- No implementation review file — the `/sprint-close` skill is the human gate and closes the sprint

---

## 2. Canonical Sprint States

Use exactly these ten states. No other labels are valid.

| State | Meaning |
|-------|---------|
| `DRAFT_READY` | `00_draft.md` exists; design not yet started |
| `DESIGN_CREATED` | `10_*.json` produced; not yet reviewed |
| `DESIGN_REVIEWED_CHANGES_REQUIRED` | Reviewer returned changes; corrector must run |
| `DESIGN_APPROVED` | Design approved; ready for implementation |
| `IMPLEMENTATION_IN_PROGRESS` | Implementer running or complete; awaiting test run or `/sprint-close` |
| `TESTS_PASSING` | Test-runner ran; all tests passed; ready for `/sprint-close` |
| `TESTS_FAILED_FIXABLE` | Tests failed with fixable implementation issues; implementer fix loop |
| `TESTS_FAILED_DESIGN_ISSUE` | Tests failed due to a design flaw; design corrector required |
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
  → [test-runner]              if 10_test_spec.md is present
  → TESTS_PASSING
  → TESTS_FAILED_FIXABLE
  → TESTS_FAILED_DESIGN_ISSUE

  → [/sprint-close]            if 10_test_spec.md is absent (test stage skipped)
  → SPRINT_COMPLETE

TESTS_PASSING
  → [/sprint-close skill invoked by human]
  → SPRINT_COMPLETE

TESTS_FAILED_FIXABLE
  → [sprint_implement]         fix_iterations must be < 3; otherwise → BLOCKED
  → IMPLEMENTATION_IN_PROGRESS

TESTS_FAILED_DESIGN_ISSUE
  → [sprint_design_corrector]  50_test_report.md serves as corrector input
  → DESIGN_CREATED

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
| `TESTS_PASSING` | All IMPLEMENTATION_IN_PROGRESS artifacts plus `50_test_report.md` (verdict: `TESTS_PASSING`) |
| `TESTS_FAILED_FIXABLE` | All IMPLEMENTATION_IN_PROGRESS artifacts plus `50_test_report.md` (verdict: `TESTS_FAILED_FIXABLE`) |
| `TESTS_FAILED_DESIGN_ISSUE` | All IMPLEMENTATION_IN_PROGRESS artifacts plus `50_test_report.md` (verdict: `TESTS_FAILED_DESIGN_ISSUE`) |
| `SPRINT_COMPLETE` | All prior artifacts; `99_sprint_log.md` records `/sprint-close` invocation |

---

## 5. Reviewer Verdict Vocabulary

All reviewer agents must use exactly these verdict labels. No other labels are valid.

| Verdict | Produced by | Maps to state |
|---------|-------------|---------------|
| `APPROVED` | design-reviewer | `DESIGN_APPROVED` |
| `APPROVED_WITH_CHANGES` | design-reviewer | `DESIGN_REVIEWED_CHANGES_REQUIRED` |
| `CHANGES_REQUIRED` | design-reviewer | `DESIGN_REVIEWED_CHANGES_REQUIRED` |
| `TESTS_PASSING` | test-runner | `TESTS_PASSING` |
| `TESTS_FAILED_FIXABLE` | test-runner | `TESTS_FAILED_FIXABLE` |
| `TESTS_FAILED_DESIGN_ISSUE` | test-runner | `TESTS_FAILED_DESIGN_ISSUE` |
| `BLOCKED` | any reviewer | `BLOCKED` |
| `REJECTED` | any reviewer | `BLOCKED` |

Rules:
- If a reviewer file does not contain an explicit verdict from this list, the orchestrator must mark the sprint `BLOCKED`.
- Do not infer a verdict from prose. The verdict must be explicitly stated.
- `APPROVED_WITH_CHANGES` and `CHANGES_REQUIRED` are equivalent from the design-reviewer — both route to the corrector.
- The test-runner must err toward `TESTS_FAILED_FIXABLE`. Only emit `TESTS_FAILED_DESIGN_ISSUE` when the report can name the specific design artifact that is wrong.

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

Single file. State block at the top, transition log below. Each transition entry is 1–3 lines: a summary line followed by optional `read:` and `wrote:` detail lines.

```markdown
# Sprint Log — <sprint_name>

```json
{
  "sprint_name": "Sprint06_Label_Contract_Fix",
  "component_name": "TaskTracker",
  "layer": "03_Application",
  "log_format": "v2",
  "current_state": "DESIGN_APPROVED",
  "last_agent": "sprint_design_reviewer",
  "next_agent": "sprint_implement",
  "blocking": false,
  "block_reason": null
}
```

## Log

- 2026-04-11T14:05:12Z `DRAFT_READY` → `DESIGN_CREATED` [sprint_design_application@2026-04-11] 138s
  read: Sprint01_Foo/00_draft.md, 00_Blueprint/Atlas_Manifest.md, 02_Platform/packages/platform_contracts/contracts.py
  wrote: Sprint01_Foo/10_architecture.json, Sprint01_Foo/10_scaffolding.json, Sprint01_Foo/10_schema.sql
- 2026-04-11T14:07:44Z `DESIGN_CREATED` → `DESIGN_REVIEWED_CHANGES_REQUIRED` [sprint_design_reviewer@2026-04-11] 96s — missing null semantics on PATCH
  read: Sprint01_Foo/10_architecture.json, Sprint01_Foo/10_scaffolding.json, Sprint01_Foo/00_draft.md
  wrote: Sprint01_Foo/11_design_review.md
- 2026-04-11T14:09:18Z `DESIGN_REVIEWED_CHANGES_REQUIRED` → `DESIGN_CREATED` [sprint_design_corrector@2026-04-11] 74s
  read: Sprint01_Foo/10_architecture.json, Sprint01_Foo/11_design_review.md
  wrote: Sprint01_Foo/10_architecture.json, Sprint01_Foo/12_design_corrections.md
- 2026-04-11T14:10:55Z `DESIGN_CREATED` → `DESIGN_APPROVED` [sprint_design_reviewer@2026-04-11] 61s
  read: Sprint01_Foo/10_architecture.json, Sprint01_Foo/10_scaffolding.json, Sprint01_Foo/12_design_corrections.md
  wrote: Sprint01_Foo/13_design_review.md
- 2026-04-11T14:13:02Z `DESIGN_APPROVED` → `IMPLEMENTATION_IN_PROGRESS` [sprint_implement@2026-04-11] 312s
  read: Sprint01_Foo/10_architecture.json, Sprint01_Foo/10_scaffolding.json, Sprint01_Foo/10_schema.sql
  wrote: backend/routers/foo.py, src/FooEntry.tsx, tests/test_foo.py
- 2026-04-11T14:18:30Z `IMPLEMENTATION_IN_PROGRESS` → `SPRINT_COMPLETE` [/sprint-close]
```

### Log format rules

- Summary line: `- <ISO-8601 timestamp> \`PREV_STATE\` → \`NEXT_STATE\` [agent_name@agent_version] <duration_seconds>s <optional one-line reason>`
- `agent_version` is the `version` field from the agent's frontmatter (format: `YYYY-MM-DD`). Extracted from the Activity Report.
- `read:` line: comma-separated list of files the agent read, relative to the repo root. Omit if the agent reported none.
- `wrote:` line: comma-separated list of files the agent created or modified. Omit if the agent reported none.
- `/sprint-close` entries omit duration, read, wrote, and version — they are human gate events.
- Timestamps are ISO-8601 in UTC (e.g. `2026-04-11T14:05:12Z`). The orchestrator records start time before launching the agent and end time after it returns.

Field rules:
- `log_format` must be `"v2"` for all sprints initiated after 2026-04-11. Older sprint logs without this field are `v1` and are excluded from file-read analysis.
- `layer` must be exactly `02_Platform` or `03_Application`
- `current_state` must be one of the ten canonical states
- `blocking` must be `true` or `false`
- `block_reason` must be `null` unless `blocking` is `true`
- `next_agent` must be `null` when `current_state` is `SPRINT_COMPLETE` or `BLOCKED`
- `fix_iterations` must be present when `current_state` is any `TESTS_FAILED_*` or `IMPLEMENTATION_IN_PROGRESS` after a test failure; records how many fix loops have been run; starts at 0

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
- `fix_iterations` has reached 3 and tests are still failing — human intervention required

When blocking, state: the exact missing artifact or contradiction, the local consequence, and the required human or agent action.

---

## 10. Test Artifact Formats

### `10_test_spec.md`

Written by the designer. Required when the component exposes an API; optional otherwise.

Scenarios should reference fixture objects by name where relevant (e.g. *"Given the fixture item 'milk' which is in low_stock state…"*). This makes the traceability between spec, fixture, and test function explicit.

```markdown
# Test Spec — <ComponentName> — <SprintName>

## Scope
<one sentence: what is being tested and what is explicitly out of scope>

## Scenarios

### <Scenario Name>
- **Given:** <precondition>
- **When:** <action>
- **Then:** <expected outcome>

### <Scenario Name>
...
```

Rules:
- Each scenario must be independently testable.
- Do not include implementation detail (function names, SQL). Scenarios describe observable behavior.
- The implementer maps each scenario to concrete test functions; the scenario names are the traceability link.
- If `10_scaffolding.json` lists any `.tsx` files under `files_changed`, the spec must include at least one UI scenario. Label it with `[UI]` in the scenario name (e.g. `### [UI] List row shows sparkline`). UI scenarios describe what a user sees or does — not React internals. If UI test execution infrastructure is not yet available, mark the scenario `[UI — manual]` and the test report must note it as untested rather than passing.

---

### `50_test_report.md`

Produced by the test-runner. Overwrites any prior version in the same sprint.

```markdown
# Test Report — <ComponentName> — <SprintName>

**Verdict:** TESTS_PASSING | TESTS_FAILED_FIXABLE | TESTS_FAILED_DESIGN_ISSUE
**Date:** YYYY-MM-DD
**Fix iteration:** <N> (0 on first run)

## Results

| Scenario | Test | Status | Failure reason |
|----------|------|--------|----------------|

## Failure Analysis

<If verdict is TESTS_PASSING: "All scenarios passed.">
<If TESTS_FAILED_FIXABLE: describe the implementation errors; do not name design artifacts.>
<If TESTS_FAILED_DESIGN_ISSUE: name the exact design artifact and field that is wrong.>

## Required Action

<one sentence: what must happen next>
```

Rules:
- Verdict `TESTS_FAILED_DESIGN_ISSUE` requires the failure analysis to explicitly name the design artifact (e.g., `10_architecture.json §interfaces.outputs`) that is wrong. If that specificity cannot be reached, use `TESTS_FAILED_FIXABLE`.
- The test-runner runs tests inside the `-test` container: `docker exec atlas-<component>-test pytest tests/ -v`. The test container has `ATLAS_PG_DB=atlas_test` set — no override needed.
- Fixtures are loaded by the conftest before each test. The test runner does not manage fixture loading.

---

### `tests/ui/*.spec.ts`

Written by the implementer for `[UI]` scenarios. Not a sprint artifact (lives in the component, not the sprint folder).

- Lives at `<component_root>/tests/ui/`
- Each file covers one or more `[UI]` scenarios from `10_test_spec.md`
- Tests run against `http://atlas-shell` via the shared `atlas-playwright` container
- Playwright config: `02_Platform/Atlas_Shell/playwright.config.ts`
- `[UI — manual]` scenarios have no `.spec.ts` file — absence is expected and not treated as `MISSING`

---

### `tests/fixtures.sql`

Written by the implementer alongside the test functions. Not a sprint artifact (lives in the component, not the sprint folder) but governs test behavior.

Contains INSERT statements that define the test world. Loaded by `conftest.py` before each test after truncating the component's tables. Rules:
- IDs prefixed with `fix-` for readability
- Covers the happy path, boundary cases, and cross-object relationships needed by the spec scenarios
- Extended by each sprint — do not remove fixtures that prior sprint tests depend on

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
- Sprint orchestrators — when an agent execution fails or requires human intervention due to tooling or environment constraints (run_type: `execution_issue`)

Schema for each entry — append as a YAML block:

```yaml
---
entry_id: EVD-YYYY-MM-DD-NNN
date: YYYY-MM-DD
source_agent: <agent name>
run_type: design_review | audit | implementer_note | execution_issue
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
