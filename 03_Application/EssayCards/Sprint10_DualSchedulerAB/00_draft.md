# EssayCards Sprint 10: Dual Scheduler A/B Experiment

## Mission

Implement a complete A/B experiment comparing EssayCards' existing Classic spaced-repetition algorithm with FSRS.

This is a full development sprint. Use the available Claude Code agent capabilities extensively, including parallel research, architecture analysis, implementation, regression testing and independent review.

Do not stop after producing a plan. Complete the implementation, test it and deliver a working feature.

The objective is to compare two scheduling algorithms inside the existing EssayCards learning experience.

The existing review selection mechanism must not be redesigned.

---

## 1. Existing architecture — authoritative context

The current scheduling implementation is located in `backend/scheduling.py`.

Classic uses the following formula:

| Rating | Next interval                                  |
| ------ | ---------------------------------------------- |
| again  | Fixed 5 seconds                                |
| hard   | max(1 minute, 2 × elapsed since last review)   |
| good   | max(20 minutes, 2 × elapsed since last review) |
| easy   | max(1 day, 2 × elapsed since last review)      |

Verify these rules against the actual code and establish regression tests before modifying scheduling.

The application's shared scheduling outputs are:

* `next_due_at`
* `flashcard_review_state.review_interval`

The second represents the scheduled interval between the completed review and the next due date.

These fields are consumed throughout the existing application.

In particular:

* The 24-hour threshold separates learning and established cards.
* `GET /flashcards/due` distinguishes RECENT and BACKLOG.
* RECENT uses the existing last-24-hours logic.
* BACKLOG uses the existing `review_interval` descending order.
* Review sessions surface established cards.
* Focus sessions ignore that threshold.
* `GET /flashcards/stats` uses seven existing forecast bands.
* UI indicators and review diagnostics depend on existing interval semantics.

All of this must be preserved.

### Mandatory architecture decision

Use the minimal-blast-radius implementation.

FSRS is a scheduling engine, not a replacement for EssayCards' existing learning model.

Both Classic and FSRS must calculate scheduling results that are persisted through the existing fields.

FSRS must additionally maintain its own internal state.

FSRS stability and EssayCards `review_interval` are different concepts and must not be confused.

Do not replace the 24-hour threshold with FSRS-native learning states.

Do not change due-queue ordering, selection, prioritization, resurfacing, Review/Focus eligibility, existing forecast bands or UI vocabulary.

The two algorithms will produce different due dates. That is intentional.

Given identical due dates and existing state, the selection mechanism must behave exactly as before the sprint.

---

## 2. Development strategy and agent organization

This is not eligible for the sprint process's fast path.

Use the full sprint workflow.

Create a dedicated Git branch and inspect the repository instructions before beginning.

Organize work into the following phases.

### Phase A — Parallel investigation

Launch specialized agents.

**Agent 1: Scheduling architecture**

Investigate the existing scheduling implementation, review-state persistence, rating semantics, statistics and tests.

Document Classic's exact behaviour and establish a regression baseline.

**Agent 2: Selection mechanism guardian**

Independently map the complete card selection mechanism.

Identify every function involved in:

* Due-card eligibility.
* RECENT and BACKLOG.
* Review and Focus sessions.
* Ordering and prioritization.
* Resurfacing.
* Due-date-dependent statistics and UI behaviour.

Document the relevant existing behaviour and identify what must be protected.

This agent will later verify that the implementation preserves these mechanisms.

**Agent 3: FSRS research**

Research the official Python implementation, Py-FSRS.

References:

https://github.com/open-spaced-repetition/py-fsrs

https://open-spaced-repetition.github.io/py-fsrs/

https://docs.ankiweb.net/deck-options.html#fsrs

Verify the current library API, FSRS version, rating semantics, learning steps, state serialization, history replay and optimization support.

Intended configuration:

* FSRS 6, subject to verification.
* Desired retention of 90%.
* Default model parameters.
* No personalized parameter optimization in Sprint 1.

Investigate how the existing Again/Hard/Good/Easy controls should map to FSRS.

Preserve the existing controls and their user-facing meanings.

**Agent 4: Database and migration**

Inspect the current schema, migrations and available review history.

Determine the safest method for persistent algorithm assignment and FSRS state storage.

Investigate how existing mature cards can enter the experiment without losing their progress.

### Phase B — Architecture consolidation

The lead agent must consolidate the findings before implementation.

Resolve:

* Scheduler interface.
* Rating mapping.
* Database changes.
* Existing-card migration.
* New-card assignment.
* FSRS learning steps.
* Analytics data requirements.
* Feature activation and rollback.

Record the decisions in a brief architecture document.

The choice to preserve EssayCards' existing interval-based model is already final. Do not reopen that decision.

### Phase C — Parallel implementation

Once the architecture is settled, distribute implementation across agents with clear ownership.

Suggested workstreams:

* Scheduler implementation.
* Migration and random assignment.
* Frontend badge.
* Experiment analytics.
* Regression and integration tests.

Use separate worktrees where appropriate to prevent conflicting edits.

### Phase D — Independent review

Assign a separate agent to review the complete implementation.

The review should focus particularly on preservation of the existing selection mechanism and Classic scheduling behaviour.

Resolve critical findings before completing the sprint.

---

## 3. Scheduler implementation

Introduce a minimal abstraction supporting two implementations:

`ClassicScheduler`

`FSRSScheduler`

Use repository naming conventions where appropriate.

Avoid building an unnecessarily complex scheduling framework.

Both algorithms must produce the scheduling information needed by the existing review-state persistence mechanism.

### Classic

Preserve Classic's existing calculation exactly.

Do not alter its doubling behaviour, failure handling, initial intervals or timestamp semantics.

Do not apply FSRS-specific behaviour to Classic cards.

### FSRS

Integrate the verified official library.

Persist all required FSRS memory state.

FSRS calculates the next due date.

EssayCards persists the result through its existing fields.

Do not modify FSRS intervals using Classic's multipliers.

Do not replace EssayCards' `review_interval` with FSRS stability.

Preserve the existing 24-hour learning/established classification.

If FSRS produces short learning or relearning intervals, those intervals must pass through the same existing due-date interface.

Do not create a separate FSRS queue or modify Focus/Review selection.

If the existing session mechanics create a limitation for short-term FSRS reviews, document and test the interaction. Resolve integration problems without redesigning selection.

---

## 4. Experiment assignment

Assign eligible flashcards to either:

`classic`

or

`fsrs`

Target a balanced 50/50 distribution.

Assignment must be persistent.

Never randomly reassign a card when it is reviewed, retrieved, edited or re-imported.

### Balanced randomization

Where practical, balance assignment across:

* Essay-level cards.
* Section-level cards.
* Nugget-level cards.
* Flashcard levels.
* Existing versus newly created cards.
* Existing learning maturity.

Use a simple, reproducible assignment mechanism.

Do not create a large experimentation framework.

Store assignment metadata sufficient to identify when and under which experiment a card was assigned.

### Existing cards

Investigate the available review history.

Initialize FSRS state from actual review records where supported by the library.

Preserve existing next due dates during migration.

Do not fabricate historical reviews or silently reset mature cards.

If reliable FSRS initialization is impossible for a particular card, document the fallback and retain it in Classic or exclude it from the initial FSRS cohort.

Track this transparently in the experiment metadata.

### New cards

Automatically assign new cards when they enter the scheduling system.

Ensure assignment is idempotent.

Editing nuggets, regenerating flashcard text or re-ingesting essays must not unintentionally reset scheduling or experiment assignment.

---

## 5. Database and migration

Prefer additive database changes.

Store, as appropriate:

* Assigned scheduler.
* Experiment cohort and assignment metadata.
* FSRS state.
* Scheduler configuration/version.
* Review-event data needed for analytics.

Reuse existing review logs rather than duplicating them unnecessarily.

Preserve existing:

* Flashcard IDs.
* Card content.
* Essay/section/nugget relationships.
* Review history.
* Discussion history.
* Current due dates.
* Classic scheduling progress.

Perform migration testing against a database copy.

Verify record counts and important relationships before and after migration.

Make the migration recoverable.

Ensure a review cannot save its due date while failing to save its associated scheduler state or review history.

Provide a safe way to disable new experiment assignment without corrupting existing scheduling state.

---

## 6. Frontend

Add a small scheduler badge to the flashcard review interface.

Display:

`Classic`

or

`FSRS`

Place it in the top corner.

It should be visible both before and after the answer is revealed.

Use the existing visual design system.

Do not redesign the card.

Do not introduce a new review workflow.

Do not replace the existing answer buttons.

The badge must reflect the persisted scheduler assignment.

---

## 7. Experiment dashboard — first version

Implement a small experiment comparison view.

It should show real recorded data, not theoretical scheduler predictions.

For each algorithm, include:

* Assigned cards.
* Reviewed cards.
* Completed reviews.
* Recall rate on ordinary scheduled reviews.
* Failures.
* Review workload.
* Review time, if reliably recorded.
* Review interval distribution.
* Learning versus established cards.

Distinguish new and migrated cards where possible.

Preserve existing EssayCards statistics.

The existing seven forecast bands must remain unchanged.

The experiment dashboard is additional functionality.

### Measurement principles

The central question is:

Which scheduling behaviour produces better knowledge retention relative to the required review workload?

Do not compare recall percentages without considering the number of reviews required.

Distinguish ordinary due reviews from immediate relearning and manually initiated study where the data supports this.

Do not count multiple rapid retries as independent evidence of long-term retention.

Expose sample sizes.

Do not implement automatic winner selection or complex statistical inference in this sprint.

A basic dashboard that accurately records the experiment is sufficient.

---

## 8. Regression testing — mandatory

Before modifying the scheduler, establish baseline tests for Classic.

Tests must include:

* Again.
* Hard.
* Good.
* Easy.
* Multiple consecutive reviews.
* Failure after several successful reviews.
* Mature cards.
* Short intervals.
* Date boundaries.

Use controlled timestamps.

### Protect existing card selection

Create integration tests using fixed review-state fixtures and a fixed current time.

Compare selection behaviour before and after the scheduler integration.

Verify:

* Due-card eligibility.
* RECENT membership and ordering.
* BACKLOG membership and ordering.
* The 24-hour threshold.
* Review session behaviour.
* Focus session behaviour.
* Resurfacing.
* The seven forecast bands.
* Recency indicators and diagnostics.

A change to selection behaviour is a regression unless it is solely explained by an intentionally changed due date.

The implementation must not introduce scheduler-type-specific selection rules.

### Test FSRS

Verify:

* Correct library integration.
* Correct rating mapping.
* State persistence.
* Due-date calculation.
* Relearning.
* Repeated reviews.
* Application restart and state reload.
* Timezone correctness.
* Migration from historical reviews.
* Handling of incomplete histories.

### Test assignment

Verify permanent assignment and approximately balanced distribution.

Verify that editing, content regeneration and re-ingestion do not reassign existing cards.

### Test migration

Verify no record loss, unintended due-date changes or scheduling resets.

### End-to-end validation

Complete actual card reviews using both schedulers.

Verify the full flow from answer submission through backend scheduling, persistence, subsequent selection and frontend badge.

---

## 9. Scope restrictions

Do not implement the following in Sprint 1:

* FSRS parameter optimization.
* Switching individual cards between algorithms.
* Per-essay scheduler configuration.
* Redesigned review selection.
* Redesigned Directed Study.
* New card prioritization rules.
* FSRS-native learning/established vocabulary.
* Major changes to the flashcard UI.
* Advanced statistical analysis.
* Unrelated architectural refactoring.

Document useful follow-up ideas for Sprint 2.

---

## 10. Definition of done

Sprint 1 is complete when:

1. Classic and FSRS operate together.
2. Assignment is persistent and balanced.
3. Existing cards have been safely handled.
4. New cards receive automatic assignment.
5. Both schedulers persist their next due dates through the existing interface.
6. FSRS state survives application restarts.
7. The scheduler badge works.
8. Experiment results are being recorded and displayed.
9. Classic produces its original scheduling results.
10. The existing card selection and resurfacing mechanisms are preserved.
11. Migration and integration tests pass.
12. An independent agent has reviewed the implementation.

Deliver a final sprint report covering:

* Changes made.
* Architecture decisions.
* Migration results.
* Tests performed.
* Any deviations from the initial design.
* Known limitations.
* Recommended Sprint 2 improvements.

Do not claim completion while critical acceptance criteria are failing.

The objective is a fully functional experiment that can begin collecting meaningful data immediately.

**Preserve EssayCards' learning experience. Compare only the scheduling algorithms.**
