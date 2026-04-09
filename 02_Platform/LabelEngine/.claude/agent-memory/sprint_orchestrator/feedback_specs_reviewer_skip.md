---
name: TaskTracker specs-reviewer skip
description: Mature TaskTracker sprints skip the specs-reviewer stage when the user confirms at orchestration time with a detailed draft
type: feedback
---

When a sprint is declared for a mature application (TaskTracker) with a detailed, well-formed draft.md, the user may explicitly authorize skipping the specs-reviewer stage. This must be confirmed in the orchestration call — it is not assumed by default.

**Why:** TaskTracker has established domain context; requiring a separate spec-readiness review on a targeted fix sprint adds no value.

**How to apply:** Record the skip in sprint_state.json notes and orchestrator_log.md. Route DRAFT_READY directly to sprint_design_application. No sprint_conventions.md is required when the user confirms verbally at orchestration time.
