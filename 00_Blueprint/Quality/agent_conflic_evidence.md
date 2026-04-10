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