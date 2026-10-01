# Sprint12 — FSRS-only scheduling, learning-progress levels, UI consolidation

## Mission

Implement this sprint for EssayCards. Inspect the current implementation
first, reuse existing components, and preserve card identities and review
history.

This is a full development sprint touching scheduling, essay data model,
and significant UI surface. Not eligible for the sprint process's fast path
(schema changes, more than 5 files, removes an existing feature, single
component but broad within it) — use the full `R-PRO-BP-01` pipeline.

---

### 1. Make FSRS the sole scheduler

Use FSRS for all existing and new cards. Reuse the existing integration
where appropriate and use a maintained FSRS library.

**Scheduling boundary:** Change only the mechanism that calculates and
writes a card's next due date after a review, along with the FSRS state
needed for that calculation.

- Keep all existing card selection, filtering, grouping, and ordering logic
  unchanged, including the due queue and focus sessions.
- Different due dates will naturally affect which cards qualify; do not
  change the selection rules themselves.
- Preserve current due dates during migration. Initialize FSRS state from
  compatible review history without bulk rescheduling.
- Calculate the new due date when a card is next reviewed.
- Preserve review history and handle missing or incompatible historical
  data explicitly.
- Back up scheduling data before migration and make migration safe to
  rerun.
- Provide a desired-retention setting, initially 90%.
- Remove experimental assignment, scheduler badges, and comparison
  statistics.
- Verify migration and rating mapping before removing the old scheduler's
  active code paths.

### 2. Replace essay writing maturity with learning progress

Remove the different writing maturity levels. A simple ideas/planned list
may remain.

Track four learning milestones for each essay:

1. All active cards seen.
2. All active cards reviewed and next due more than 24 hours from now.
3. Guided oral exam passed.
4. Unguided oral exam passed.

Requirements:
- Calculate the card milestones from current data; they can become
  incomplete again.
- Essays without active cards must not automatically satisfy the card
  milestones.
- Show counts for partial card progress within the essay.
- Retain passed oral exams with their dates, using existing exam
  functionality.
- Show an essay level from **0–4**, representing the number of completed
  milestones. Do not require completion in a fixed order.
- Make the meaning of that number available through a compact tooltip or
  accessible explanation.

### 3. Simplify essay and section controls

Reduce visible button clutter while preserving available actions.

**At the end of each section:**
- Replace the row of action buttons with one primary button and an
  adjacent dropdown for secondary actions, or an equivalent compact
  control.
- Choose the primary action based on the existing workflow.
- Use consistent controls across sections.

**At the top of an essay:**
- Apply the same primary-button-plus-dropdown pattern.
- Make essay flashcard "Study" and oral exams available within the essay
  itself.
- Keep these actions easy to find without recreating a large row of
  buttons.
- Preserve access to both guided and unguided oral exams.

**On the essay overview page:**
- Remove per-essay action buttons.
- Display the essay's learning-level number instead.
- Make the essay title or row open the essay, where its study and exam
  actions are available.

**For categories such as Philosophy:**
- Add a collapse/expand control to each category heading.
- Collapse the category's contents while keeping its heading visible.
- Remember collapsed state across visits.
- Make controls usable with touch and keyboard, with clear
  expanded/collapsed states.

### 4. Improve statistics and main navigation

Make the statistics page clearer and more attractive using the existing
design language.

Prioritize:
- Study activity over time.
- Review workload and upcoming reviews.
- Actual recall rate, with sample size and observation period.
- Scheduled intervals.
- Essay learning progress.

Clearly distinguish observed recall from FSRS predictions. Remove obsolete
experiment statistics and avoid adding metrics solely to fill space.

Inspect the main navigation and group related functions together. Keep
everyday learning actions easy to reach, and group content management and
statistics sensibly. Apply the same visual conventions across the changed
screens.

---

### Scope and verification

- The habit tracker is out of scope.
- The Descartes essay and its flashcards have already been deleted. Do not
  recreate or modify them.
- Do not change card-selection rules as part of scheduling or GUI work.
- Preserve all existing actions when consolidating buttons.

Verify:
- Migration preserves existing due dates and review history.
- A review updates the due date through FSRS.
- Selection and ordering behave identically for identical card data.
- Milestones and the 0–4 level calculate correctly.
- Study and oral exams work from within an essay.
- Dropdowns and category collapse controls work on mobile and desktop.

Finish with a concise summary of what changed, what was verified, and any
remaining limitations.

---

## Note

Product request supplied by the user verbatim in chat, already fully
scoped and decided by them (unlike Sprint11, this draft carries no
open assumptions for the designer to resolve). Intended to go through
the full `R-PRO-BP-01` pipeline (`sprint_design_application` →
`sprint_design_reviewer` → `sprint_implement` → `sprint_test_runner`),
same as `Sprint09_Nuggets` and `Sprint10_DualSchedulerAB`. Given the
scope and risk (an active scheduler replacement with a data migration,
plus a schema change for essay milestones, plus broad UI surface),
follow the `Sprint10_DualSchedulerAB` precedent: parallel investigation
of the existing scheduling/selection/UI code before design, and an
independent post-test-pass implementation review filed to
`00_Blueprint/Quality/EssayCards/` (non-canonical, additive — does not
gate `TESTS_PASSING`), before the human invokes `/sprint-close`.
