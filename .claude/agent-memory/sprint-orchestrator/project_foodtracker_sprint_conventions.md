---
name: FoodTracker Sprint Conventions
description: FoodTracker sprint family deviates from canonical Atlas sprint structure — no 10_specs layer, designer reads draft.md directly, reviewer-specs-readiness is not invoked
type: project
---

FoodTracker sprints (Sprint01, Sprint02, Sprint03+) skip the `10_specs/` layer entirely. The `reviewer-specs-readiness` agent is not invoked. The `application-designer` reads `00_input/draft.md` directly as the design input.

Sprint folder structure used in this family:
- `00_input/draft.md` — design input
- `20_design/architecture.json`, `scaffolding.json`, `design_review.md`, `design_corrections.md`
- `40_status/implementation_status.md`
- `90_meta/sprint_state.json`, `orchestrator_log.md`

The `10_specs/design_specs.md` artifact does not exist in any FoodTracker sprint. This is a confirmed convention, not a process violation.

**Why:** Established from Sprint01 and continued through Sprint02. The draft.md files are detailed enough to serve as direct design input without a separate spec-readiness review step.

**How to apply:** When orchestrating FoodTracker sprints, transition directly from DRAFT_READY to application-designer without routing through reviewer-specs-readiness. Do not flag missing 10_specs as a blocker.
