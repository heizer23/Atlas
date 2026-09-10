---
conflict_id: CNF-EXAMPLE
date: 2026-04-10
source_agent: sprint_orchestrator
component: TaskTracker
sprint: Sprint07_Something
higher_authority: R-PRO-BP-01
lower_authority: .claude/agents/sprint_orchestrator.md
conflict_type: instruction_vs_rule
short_description: Agent instruction implied waiting for implementation review, but sprint process contract defines /sprint-close as the only human gate.
detected_conflict: "Agent prompt referenced implementation review as closure step; R-PRO-BP-01 §6 says '/sprint-close' is the only gate."
resolution_taken: "Followed R-PRO-BP-01 and did not require implementation review."
impact: prompt_drift
follow_up_candidate: agent_instruction
linked_artifact: 03_Application/TaskTracker/Sprint07_X/99_sprint_log.md

---

conflict_id: CNF-2026-09-09-001
date: 2026-09-09
source_agent: claude (interactive session — user-directed plan-mode implementation, not the sprint_orchestrator pipeline)
component: ClaudeConsole
sprint: Sprint01_Core
higher_authority: R-PRO-BP-01
lower_authority: none — this is a user-directed deviation, not an agent instruction contradicting the rule
conflict_type: user_directed_process_deviation
short_description: User explicitly chose to skip the sprint design/review pipeline for a new component and use Claude Code's built-in plan mode plus direct implementation instead.
detected_conflict: "R-PRO-BP-01 §4 requires 10_architecture.json, 10_scaffolding.json, and a design review artifact before IMPLEMENTATION_IN_PROGRESS. ClaudeConsole/Sprint01_Core has none of these — implementation proceeded directly from 00_draft.md plus a plan-mode plan (saved at ~/.claude/plans/, outside the sprint folder) after the user asked to bypass sprint_design_application -> sprint_design_reviewer for this solo-dev component."
resolution_taken: "Followed the user's explicit instruction. No 10_architecture.json/10_scaffolding.json/11_design_review.md/99_sprint_log.md were produced. The plan-mode plan resolved the draft's two open design questions (both Dataset-shape decisions) via a research pass equivalent in depth to a design review, and is referenced from ClaudeConsole/CLAUDE.md, but it is not a sprint-folder artifact and was never reviewed by sprint_design_reviewer. No 99_sprint_log.md was created, since R-PRO-BP-01 SS7 reserves that file for the sprint-orchestrator and none ran."
impact: "process_deviation — ClaudeConsole/Sprint01_Core does not conform to R-PRO-BP-01's required-artifact table for IMPLEMENTATION_IN_PROGRESS. A future sprint_orchestrator invocation against this folder should treat it as out-of-band / BLOCKED rather than inferring a state from missing artifacts, not as evidence of a broken or abandoned sprint."
follow_up_candidate: "none for this instance — a deliberate, informed one-off choice. If plan-mode-plus-direct-implementation becomes a recurring pattern for solo low-ceremony components, consider adding it as a recognized alternate path in R-PRO-BP-01 rather than leaving every instance as a one-off logged conflict."
linked_artifact: 03_Application/ClaudeConsole/Sprint01_Core/00_draft.md

---
