---
name: project_essaycards_sprint13
description: EssayCards Sprint13 (Review/Stats rework + sentence feedback) — reached DESIGN_APPROVED after one correction cycle; stopped there for human implementation gate
metadata:
  type: project
---

Sprint13_ReviewStatsSentenceFeedback (EssayCards, 03_Application) ran the full
normal chain DRAFT_READY → DESIGN_CREATED → DESIGN_REVIEWED_CHANGES_REQUIRED →
DESIGN_CREATED → DESIGN_APPROVED, one correction cycle, no blockers. Orchestrator
stopped at DESIGN_APPROVED (not auto-launching sprint_implement) because this is a
multi-area sprint (Review page + Stats page + new sentence-feedback feature/schema)
with real persistence implications — matches the "stop at a natural human checkpoint"
guidance for DESIGN_APPROVED, not just a mechanical default.

**Why:** User framed this sprint explicitly as multi-area, schema-bearing, >5 files —
i.e. deliberately NOT fast-path eligible. A design with a new table
(`essaycards.sentence_feedback`) and a reshaped existing endpoint
(`GET /review-stats/activity`, a breaking change reworked same-sprint) warrants a
human look at the approved design before code gets written, even though nothing
blocked the pipeline.

**How to apply:** For EssayCards (and similarly-scoped) sprints that add new
persisted state or reshape an existing endpoint contract, default to stopping at
DESIGN_APPROVED and reporting back rather than auto-chaining into
`sprint_implement`, even when the review loop ran clean. Pure single-area,
no-schema-change sprints (see [[feedback_skip_specs_stage]] and prior single-cycle
patterns like EssayCards Sprint11) are more reasonable to auto-continue through
IMPLEMENTATION_IN_PROGRESS.

**Review-cycle content worth remembering for EssayCards specifically:**
- `sprint_design_application` correctly grounded the StoryReader-reuse instruction
  by reading StoryReader's actual `annotations` model (user-selected char-span,
  single-select 4-value enum) and correctly did NOT reuse that data model — only
  StoryReader's tap→popover interaction pattern — because EssayCards needed
  server-computed sentence units over rich markdown with two independent boolean
  flags. Good precedent: "reuse X's pattern" instructions should be read as
  interaction-pattern reuse, not blind data-model copying, and the designer should
  show the comparison explicitly.
- Two Major review findings in round 1, both spec_ambiguity not architecture
  violations: (1) a dead-code removal inventory missed that a variable
  (`reviewedCount`) is dual-purpose — feeds both a metric being removed AND an
  unrelated completion message — so a "remove the old X family" instruction must
  explicitly check every consumer of each variable in that family, not just the
  one being targeted; (2) a new tap-target sentence wrapper nested around existing
  clickable elements (links/NuggetLink) needs an explicit click-precedence
  (stopPropagation) contract — this is a recurring category any time a new
  whole-row/whole-span tap handler is layered over content that already contains
  its own interactive children.
- `platform-ui`'s `BarChart` component has no per-bar label slot — confirmed by
  the designer reading its actual source — so a draft requirement to show a label
  (recall-rate %) above each stacked bar required a new EssayCards-local
  CSS/flexbox chart component rather than extending the shared Platform component
  mid-sprint. Surfaced as an open_question for a possible future Platform sprint
  rather than silently expanding Platform's component.
