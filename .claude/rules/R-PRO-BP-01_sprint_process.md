---
RULE_ID: R-PRO-BP-01
TITLE: Sprint Process Contract
TYPE: PROCESS
SCOPE: BLUEPRINT
STATUS: ACTIVE
VERSION: v1.0
CANONICAL_SOURCE: .claude/rules/R-PRO-BP-01_sprint_process.md
RELATES_TO: R-CON-BP-03, R-CON-BP-01
---

This document is the canonical definition of the Atlas sprint process.

All sprint agents (orchestrator, designers, reviewers, implementers) must treat this document as authoritative. When agent instructions conflict with this document, this document wins.

**Prospective application (R-CON-BP-05 §6):** This rule applies to sprints initiated after 2026-03-24. Sprint folders produced before this date are not required to conform and must not be flagged as violations.

---

## 1. Canonical Sprint Folder Structure

Every sprint must follow this layout:

```
00_input/
  draft.md

10_specs/
  design_specs.md

20_design/
  architecture.json
  scaffolding.json
  design_review.md
  design_corrections.md

30_implementation/
  implementation_notes.md
  implementation_review.md

40_status/
  implementation_status.md

90_meta/
  sprint_state.json
  orchestrator_log.md
```

### Naming conventions

- Sprint folder: `Sprint<N>_<Title>/` — no file extension, no trailing slash in references
- Input folder: always `00_input/`, never `01_input/` or any other prefix
- Design artifacts: always `architecture.json` and `scaffolding.json` — no component-prefixed variants
- A per-application `sprint_conventions.md` may declare approved deviations from this layout (see Section 7)

---

## 2. Canonical Sprint States

Use exactly these ten states. No other labels are valid.

| State | Meaning |
|-------|---------|
| `DRAFT_READY` | Input draft exists; specs not yet produced |
| `SPECS_READY` | Spec readiness review passed; ready for design |
| `DESIGN_CREATED` | Design artifacts produced; not yet reviewed |
| `DESIGN_REVIEWED_CHANGES_REQUIRED` | Design reviewed; corrections required before implementation |
| `DESIGN_APPROVED` | Design approved; ready for implementation |
| `IMPLEMENTATION_IN_PROGRESS` | Implementation underway |
| `AWAITING_HUMAN_REVIEW` | Implementation complete; human gate not yet recorded |
| `IMPLEMENTATION_REVIEWED` | Implementation review complete |
| `SPRINT_COMPLETE` | Sprint finished |
| `BLOCKED` | Required artifact missing, verdict invalid, or illegal transition detected |

---

## 3. Allowed State Transitions

```
DRAFT_READY
  -> [reviewer-specs-readiness]
  -> SPECS_READY

SPECS_READY
  -> [application-designer | platform-designer]
  -> DESIGN_CREATED

DESIGN_CREATED
  -> [design-reviewer]
  -> DESIGN_REVIEWED_CHANGES_REQUIRED  (if verdict is CHANGES_REQUIRED or APPROVED_WITH_CHANGES)
  -> DESIGN_APPROVED                   (if verdict is APPROVED)

DESIGN_REVIEWED_CHANGES_REQUIRED
  -> [design-corrector]
  -> DESIGN_CREATED

DESIGN_APPROVED
  -> [application-implementer | platform-implementer]
  -> IMPLEMENTATION_IN_PROGRESS

IMPLEMENTATION_IN_PROGRESS
  -> [human review gate — explicit record required]
  -> AWAITING_HUMAN_REVIEW

AWAITING_HUMAN_REVIEW
  -> [implementation-reviewer]
  -> IMPLEMENTATION_REVIEWED

IMPLEMENTATION_REVIEWED
  -> SPRINT_COMPLETE  (if reviewer verdict is COMPLETE)
  -> BLOCKED          (if reviewer verdict is CHANGES_REQUIRED, unless a correction loop is defined in sprint conventions)

Any missing required artifact, invalid verdict, or illegal stage skip
  -> BLOCKED
```

Do not skip stages. Do not infer transitions from prose. Use explicit artifact evidence only.

---

## 4. Required Input Artifacts By State

| State | Required artifacts |
|-------|--------------------|
| `DRAFT_READY` | `00_input/draft.md` |
| `SPECS_READY` | `10_specs/design_specs.md` |
| `DESIGN_CREATED` | `10_specs/design_specs.md`, `20_design/architecture.json`, `20_design/scaffolding.json` |
| `DESIGN_REVIEWED_*` or `DESIGN_APPROVED` | All DESIGN_CREATED artifacts plus `20_design/design_review.md` |
| `IMPLEMENTATION_IN_PROGRESS` | Approved design artifacts; implementation code present |
| `AWAITING_HUMAN_REVIEW` | Implementation present; human gate explicitly recorded |
| `IMPLEMENTATION_REVIEWED` | Implementation code, `30_implementation/implementation_review.md`, `40_status/implementation_status.md` |

`30_implementation/implementation_notes.md` is preferred but not a hard blocker. Flag its absence as a process weakness, not an automatic BLOCKED.

---

## 5. Reviewer Verdict Vocabulary

All reviewer agents must use exactly these verdict labels. No other labels are valid.

| Verdict | Produced by | Maps to state |
|---------|-------------|---------------|
| `APPROVED` | design-reviewer | `DESIGN_APPROVED` |
| `APPROVED_WITH_CHANGES` | design-reviewer | `DESIGN_REVIEWED_CHANGES_REQUIRED` — routes to design-corrector |
| `CHANGES_REQUIRED` | design-reviewer, implementation-reviewer | `DESIGN_REVIEWED_CHANGES_REQUIRED` or `BLOCKED` |
| `READY` | reviewer-specs-readiness | `SPECS_READY` |
| `BLOCKED` | any reviewer | `BLOCKED` |
| `COMPLETE` | implementation-reviewer | `SPRINT_COMPLETE` |
| `REJECTED` | any reviewer | `BLOCKED` |

Rules:
- If a reviewer file does not contain an explicit verdict from this list, the orchestrator must mark the sprint `BLOCKED`.
- Do not infer a verdict from prose. The verdict must be explicitly stated.
- `APPROVED_WITH_CHANGES` is a valid design review verdict. It is semantically equivalent to "corrections required before implementation" and routes identically to `CHANGES_REQUIRED` from the design-reviewer.

---

## 6. Human Review Gate

After implementation, the sprint must pause for an explicit human review gate before the implementation-reviewer is invoked.

Human approval must be recorded explicitly in one of:
1. `90_meta/sprint_state.json` — a note or field confirming human approval
2. `90_meta/orchestrator_log.md` — a dated entry recording human confirmation
3. A sprint-conventions-declared human note file

Do not assume human approval unless it is explicitly recorded. The gate may not be skipped.

---

## 7. Per-Application Sprint Conventions

A file at `<application_root>/sprint_conventions.md` may declare approved deviations from this contract for that application.

Valid deviations that may be declared:
- Skipping the `10_specs/` stage and `reviewer-specs-readiness` agent (e.g., for mature applications with pre-existing domain context)
- Alternative sprint folder naming within the application
- Additional required artifacts

A sprint conventions file must:
- State explicitly which canonical stages or rules it overrides
- State the rationale
- Be checked by the orchestrator before applying canonical stage requirements to that application

The orchestrator must surface any sprint conventions it applied in its orchestration log.

---

## 8. File Ownership

The sprint-orchestrator may create or update only:
- `90_meta/sprint_state.json`
- `90_meta/orchestrator_log.md`

The orchestrator may recommend creation or correction of other files but must not edit them directly unless explicitly authorized by a sprint conventions file.

---

## 9. sprint_state.json Schema

```json
{
  "sprint_name": "Sprint1_First_Reporting",
  "component_name": "FoodTracker",
  "layer": "03_Application",
  "current_state": "DESIGN_APPROVED",
  "last_completed_step": "design-reviewer",
  "next_recommended_agent": "application-implementer",
  "required_inputs": [
    "10_specs/design_specs.md",
    "20_design/architecture.json",
    "20_design/scaffolding.json",
    "20_design/design_review.md"
  ],
  "blocking": false,
  "block_reason": null,
  "human_gate_required": false,
  "notes": []
}
```

Field rules:
- `layer` must be exactly `02_Platform` or `03_Application`
- `current_state` must be one of the ten canonical states
- `blocking` must be `true` or `false`
- `block_reason` must be `null` unless `blocking` is `true`
- `next_recommended_agent` must be `null` only when `current_state` is `SPRINT_COMPLETE`

---

## 10. Blocker Conditions

Mark a sprint `BLOCKED` if any of the following apply:

- A required input artifact is missing
- A reviewer file contains no explicit valid verdict
- A design review requires changes but implementation is requested next
- An implementation review exists before the human gate is recorded
- Agent selection conflicts with the detected layer
- Artifact names or paths are ambiguous enough to prevent deterministic routing
- Two state-bearing files contradict each other and no newer authoritative verdict resolves it

When blocking, state: the exact missing artifact or contradiction, the local consequence, and the required human or agent action.
