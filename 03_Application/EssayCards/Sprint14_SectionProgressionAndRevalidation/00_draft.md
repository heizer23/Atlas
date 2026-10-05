# Sprint: Section Progression, Essay Mastery & Revalidation

## Goal

Redesign the essay overview around **section-level learning progression** instead of raw flashcard counts, while introducing a clearer mastery ladder for sections and full essays.

The new model should combine:

- guided oral learning
- flashcard progression
- unguided oral mastery
- essay-level mastery
- revalidation when mastery is lost

The aim is to make progress more motivating while keeping the learning model meaningful.

---

## 1. Essay Overview — Replace Current Progress Indicators

Remove the following from each essay card:

- `PLANNED`
- `COMPLETE`
- `1/4`, `2/4`, etc.
- flashcard progress counts such as `29 / 46`
- `Open: X`

The current planned/completed state is no longer needed because planned essays will be tracked outside EssayCards.

The numeric essay level is also replaced by the new traffic-light progression.

---

## 2. Keep Category-Level Flashcard Information

Do **not** remove the current category-level flashcard statistics yet.

For example:

- established cards
- open/non-established cards

These are still useful because review of non-established flashcards may continue to be started from the category level.

This can be revisited later.

---

# SECTION PROGRESSION

## 3. Section Traffic Lights

Each essay should display one small progress indicator for every section.

Section names do not need to be shown permanently.

The dots should appear in the same order as the sections within the essay.

Optional:

- hovering/tapping a dot can show the section title in a tooltip

### Section states

Use four states:

### Grey — Not Started

The section has not yet entered the learning process.

Flashcards belonging to the section remain locked.

---

### Yellow — Guided Oral Passed

The user has successfully completed the **guided section oral exam**.

This unlocks all flashcards belonging to the section.

The guided oral is therefore the entry point into learning a section.

---

### Green — Flashcards Established

All active flashcards belonging to the section meet the **Established** requirement:

- every active card has been seen
- no active card currently has an interval below 24 hours

This represents stable short-term retention of the section content.

---

### Blue — Unguided Oral Passed

The user has successfully completed the **unguided section oral exam**.

This represents independent reconstruction of the section without guided prompts.

---

## 4. Section Progression Order

The normal section progression is:

`Grey → Yellow → Green → Blue`

Conceptually:

`Guided understanding → Flashcard consolidation → Independent reconstruction`

The system should visually encourage this order.

---

# FLASHCARD UNLOCKING

## 5. Flashcards Locked Until Guided Section Oral

Flashcards should only enter normal study/review once their section's guided oral has been passed.

Before that:

- cards remain stored
- cards are not included in normal Review queues
- cards are not counted as available New cards
- cards should visibly appear as locked when viewed from the section

After the guided section oral is passed:

- all active flashcards in that section become unlocked
- they enter the normal New-card/review system

This creates a deliberate sequence:

`Understand first → memorize second`

---

# ORAL EXAM PASSING

## 6. Add a Passing Grade

Completing an oral exam should not automatically count as success.

Every oral attempt should receive a score.

Initial passing threshold:

**70%**

### Behaviour

If score <70%:

- attempt is stored in oral history
- progression state does not advance
- nothing is unlocked

If score ≥70%:

- oral is marked passed
- relevant traffic-light progression occurs

Use the same threshold initially for:

- guided section oral
- unguided section oral
- guided full-essay oral
- unguided full-essay oral

The exams themselves already differ in difficulty, so separate thresholds are not required initially.

The threshold should ideally be configurable later.

---

# FLASHCARD MATURITY

## 7. Keep Existing Flashcard States

Maintain:

### New
Never reviewed.

### Learning
Reviewed but current interval is below 24 hours.

### Established
Current interval is at least 24 hours.

---

## 8. Add New Flashcard State: Learned

Add a stricter level above Established.

### Learned

Initial rule:

**current interval ≥30 days**

This represents longer-term retention rather than merely escaping the short-term learning phase.

The exact threshold should ideally be configurable later.

Hierarchy:

`New → Learning → Established → Learned`

---

# ESSAY PROGRESSION

## 9. Essay-Level Traffic Light

Each essay receives one larger overall progress indicator.

This should represent **essay-level mastery**, not simply mirror the section states.

Use five states:

### Grey — Essay Not Started

No meaningful essay-level progress yet.

---

### Yellow — Guided Full-Essay Oral Passed

The user has successfully completed the **guided oral exam for the full essay**.

This demonstrates understanding of the essay's overall structure with support.

Section guided-orals do not determine this state.

---

### Green — All Flashcards Learned

Every active flashcard across all sections of the essay has reached:

**Learned = interval ≥30 days**

This is intentionally stricter than the section-level Green state.

Section Green only requires Established.

Essay Green therefore represents longer-term retention of the whole essay's component knowledge.

---

### Blue — All Section Unguided Orals Passed

Every section in the essay has reached Section Blue.

This means each individual section can be reconstructed independently.

---

### Violet — Unguided Full-Essay Oral Passed

The user has successfully passed the **unguided oral exam for the complete essay**.

This is the highest mastery state.

It represents the ability to reconstruct and explain the essay as an integrated whole without guidance.

---

## 10. Essay Progression

Normal essay progression:

`Grey → Yellow → Green → Blue → Violet`

Conceptually:

`Guided whole → Long-term retention → Independent sections → Independent whole`

Only the highest current state needs to be displayed.

---

# MASTERY DECAY

## 11. Violet Is a Current Mastery State

Violet should not mean:

> "This essay was completed once."

It should mean:

> "The user has currently demonstrated unguided whole-essay mastery."

A violet essay can therefore be tested again later.

---

## 12. Retaking the Unguided Essay Oral

For an essay currently at Violet:

### If the user passes

- essay remains Violet
- latest pass date is updated
- score is stored in oral history

### If the user fails

The integrated mastery evidence is no longer valid.

Immediately:

- remove Essay Violet
- remove Essay Blue
- invalidate all Section Blue states

Do **not** remove:

- Section Yellow
- Section Green
- Guided oral history
- flashcard scheduling history

The user therefore falls back to the highest level still supported by valid evidence.

---

# REVALIDATION

## 13. Failed Full-Essay Oral Starts Revalidation

When an unguided full-essay oral is failed, initiate a **Revalidation** cycle for all active flashcards belonging to that essay.

This should not directly reset FSRS scheduling.

Instead, every card receives a temporary:

`needs_revalidation = true`

state.

---

## 14. Revalidation Review Queue

Revalidation cards become immediately available for review regardless of their normal FSRS due date.

They should be presented as a dedicated review mode:

**Revalidation**

Do not simply overwrite their FSRS due dates.

---

## 15. Correct Revalidation Answer

If a revalidation card is answered correctly:

- remove `needs_revalidation`
- retain the existing FSRS state
- retain stability
- retain difficulty
- retain normal due date

The diagnostic review should ideally **not count as a normal successful FSRS review**, because the scheduler did not request it.

This avoids artificially extending already-long intervals.

---

## 16. Incorrect Revalidation Answer

If the card is answered incorrectly:

- remove `needs_revalidation`
- treat the response as a genuine FSRS failure
- feed the failure into FSRS
- allow FSRS to update stability, difficulty and next due date normally

This returns genuinely forgotten knowledge to active rotation.

---

## 17. Revalidation Completion

Revalidation is complete when every flagged card in the essay has been checked.

Example:

Essay contains 60 cards.

After failed oral:

`60 cards require revalidation`

Results:

- 56 answered correctly → existing FSRS state preserved
- 4 answered incorrectly → returned to active FSRS learning/review

Only the knowledge actually shown to be weak is reset.

---

# OVERVIEW UI

## 18. Essay Card Layout

Each essay card should become substantially simpler.

Example concept:

**● Empiricism and the Limits of Experience**

`● ● ● ● ●`

Where:

- large dot = essay state
- smaller dots = section states
- smaller dots follow section order

Permanent section names are not necessary.

Tooltip/tap may reveal:

- section name
- current state
- next requirement

---

## 19. Traffic-Light Legend

The UI should provide a small legend somewhere accessible.

### Section

- Grey — Not started
- Yellow — Guided oral passed / flashcards unlocked
- Green — Flashcards established
- Blue — Unguided oral passed

### Essay

- Grey — Not started
- Yellow — Guided essay oral passed
- Green — All cards learned
- Blue — All sections independently mastered
- Violet — Unguided essay oral passed

This does not need to remain permanently visible on every card.

---

# DATA / BACKEND

## 20. Section Oral State

Persist separately for each section:

- guided oral attempts
- guided oral pass state
- guided oral latest score
- unguided oral attempts
- unguided oral pass state
- unguided oral latest score
- latest passed-at timestamps

Do not derive historical oral completion solely from current traffic-light color.

---

## 21. Essay Oral State

Persist separately:

- guided essay oral attempts
- guided essay oral pass state
- unguided essay oral attempts
- unguided essay oral current pass state
- scores
- timestamps

This is necessary because unguided mastery may later be invalidated.

---

## 22. Derived Progress States

Traffic-light colors should preferably be derived from underlying learning state rather than manually stored.

For example:

### Section Green

Derived from:

- section guided oral passed
- all active section cards seen
- all active section cards interval ≥24h

### Essay Green

Derived from:

- all active essay cards interval ≥30d

This prevents UI progress becoming inconsistent with flashcard scheduling.

---

# ACCEPTANCE CRITERIA

The sprint is complete when:

- essay cards no longer show Planned/Complete
- essay cards no longer show the old numeric progression level
- every section has a visible progress dot
- every essay has a visible overall progress dot
- section names are not required in the default overview
- section flashcards remain locked before the guided section oral
- passing the guided section oral unlocks its flashcards
- oral attempts below 70% do not advance progression
- oral attempts at or above 70% advance progression
- Established remains defined as interval ≥24h
- Learned is added and initially defined as interval ≥30d
- Section Green requires all section cards to be Established
- Essay Green requires all essay cards to be Learned
- Section Blue requires a passed unguided section oral
- Essay Yellow requires a passed guided full-essay oral
- Essay Blue requires all sections to have passed their unguided oral
- Essay Violet requires a passed unguided full-essay oral
- violet essays can retake the unguided full-essay oral
- failing that oral removes essay Violet and Blue
- failing that oral invalidates Section Blue across the essay
- failing that oral starts Revalidation for all active essay cards
- Revalidation does not overwrite FSRS due dates
- successful revalidation preserves existing FSRS state
- failed revalidation is processed as a genuine FSRS failure
- category-level flashcard statistics remain unchanged for now
- existing normal review scheduling remains unchanged outside the new unlock/revalidation logic
