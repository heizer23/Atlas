# Test Spec — EssayCards — Sprint14_SectionProgressionAndRevalidation

## Scope
Backend behavior of oral pass grading, section/essay state, flashcard unlocking, the failure cascade, Revalidation, the schema backfill, and the changed overview/reader/review/import UI; excludes FSRS math, due-queue ordering (unchanged), review-stats endpoints (unchanged), and the external examiner conversation itself.

Fixture naming: all fixture ids are `fix-` prefixed. New fixtures needed (see 10_scaffolding.json tests/fixtures.sql): `fix-essay-locked` (section never examined, cards new), `fix-essay-yellow` (guided passed, cards mixed), `fix-essay-green` (guided passed, every card interval >= 24h), `fix-essay-blue` (all sections unguided passed), `fix-essay-violet` (essay unguided passed; some reviewed cards, some never-reviewed), `fix-essay-learned` (every card interval >= 30d). Every pre-existing fixture section keeps working via a grandfathered guided-passed state row.

## Scenarios

### Oral import and pass rule

#### Score 5 of 6 passes the 70% rule
- **Given:** a section in `fix-essay-locked`
- **When:** a guided section result with score 5 is imported
- **Then:** the response marks it passed with score_percent 83.3 and the attempt appears in the section's history with passed true

#### Score 4 of 6 fails the 70% rule
- **Given:** a section in `fix-essay-locked`
- **When:** a guided section result with score 4 is imported
- **Then:** the response marks it not passed (66.7%), the attempt is stored in history, and the section remains grey with its cards still locked

#### Same threshold for all four oral kinds
- **Given:** a section and its essay
- **When:** score 4 and score 5 are imported for each of guided-section, unguided-section, guided-essay, unguided-essay
- **Then:** score 4 is not passed and score 5 is passed in every one of the four kinds

#### Section-scope result requires section_anchor_slug
- **Given:** an import result with scope "section" and no section_anchor_slug
- **When:** it is imported
- **Then:** VALIDATION_ERROR and nothing is written

#### Essay-scope result with a non-null section_anchor_slug is rejected
- **Given:** an import result with scope "essay" and section_anchor_slug "intro"
- **When:** it is imported
- **Then:** VALIDATION_ERROR and nothing is written

#### Essay-scope result accepts omitted and null section_anchor_slug equivalently
- **Given:** two essay-scope results, one omitting section_anchor_slug and one with it set to null
- **When:** each is imported
- **Then:** both are stored as essay attempts with identical outcome

#### Missing or invalid scope is rejected
- **Given:** a result with no scope, and another with scope "chapter"
- **When:** each is imported
- **Then:** each returns VALIDATION_ERROR naming scope

#### Batch import is all-or-nothing
- **Given:** a batch of three results where the third names a section that does not exist
- **When:** the batch is imported
- **Then:** NOT_FOUND, and none of the three attempts, state changes or cascades are persisted

#### Examination package scope=section contains only that section
- **Given:** an essay with three sections
- **When:** the package is requested with exam_type guided, scope section, and the second section's id
- **Then:** the package lists exactly that one section and echoes scope and a scoring block (score_max 6, pass_threshold_percent 70, min_passing_score 5)

#### Examination package scope=essay contains all sections and last essay result
- **Given:** `fix-essay-yellow` with a prior guided essay attempt
- **When:** the package is requested with exam_type guided and scope essay
- **Then:** every section is listed and last_essay_examination holds the prior attempt; for exam_type unguided it is null

#### Examination package rejects invalid parameter combinations
- **Given:** an essay
- **When:** the package is requested with scope section and no section_id; with scope essay plus a section_id; with no scope; with a section_id that belongs to another essay
- **Then:** the first three return VALIDATION_ERROR and the last returns NOT_FOUND

### Section state and unlocking

#### Passing the guided section oral unlocks that section's cards
- **Given:** a locked section whose cards are due-eligible by date but absent from the focus queue
- **When:** a passing guided section result is imported
- **Then:** the section turns yellow and its cards appear in the essay's focus due queue; the response effects name the unlock

#### Locked section cards are excluded from focus and review queues
- **Given:** `fix-essay-locked`
- **When:** the due queue is fetched scoped to that essay, to its section, to its topic, and with no scope
- **Then:** none of its cards appear in any of them

#### Locked cards are not counted in the queue forecast
- **Given:** `fix-essay-locked`
- **When:** the queue stats are fetched scoped to that essay
- **Then:** all seven bands are zero

#### Failing a guided attempt after passing does not relock
- **Given:** a section with guided passed
- **When:** a failing guided result is imported
- **Then:** the section stays yellow, cards stay unlocked, and the section's latest guided score reflects the failing attempt

#### A card added to an already-unlocked section is unlocked
- **Given:** a yellow section
- **When:** a new card is upserted into it
- **Then:** the card appears in the section's focus queue without any further oral

#### Reviewing a locked card is rejected
- **Given:** a card in a locked section
- **When:** a review with grade good is posted for it
- **Then:** VALIDATION_ERROR and the card's schedule and review history are unchanged

#### Section is green only when every card is established
- **Given:** `fix-essay-yellow` where all but one card have interval >= 24h
- **When:** section progress is fetched
- **Then:** the section is yellow; after that last card reaches interval >= 24h it is green

#### Section with guided passed but zero cards is yellow, never green
- **Given:** a guided-passed section with no cards
- **When:** section progress is fetched
- **Then:** state is yellow

#### Passing the unguided section oral makes the section blue
- **Given:** a green section
- **When:** a passing unguided section result is imported
- **Then:** the section is blue and next_step is null

#### Unguided pass on a section that never passed guided is blue
- **Given:** a grey section
- **When:** a passing unguided section result is imported
- **Then:** the section is blue (blue needs only the unguided pass)

#### Failing an unguided section oral does not revoke blue
- **Given:** a blue section
- **When:** a failing unguided section result is imported
- **Then:** the section is still blue and the failing attempt is in history

#### Section progress lists every section in essay then section order
- **Given:** several essays across categories with multiple sections
- **When:** section progress is fetched with no filter, then with one essay_id, then with an unknown essay_id
- **Then:** rows follow the essay overview order then section order; the filtered call returns only that essay's sections; the unknown id returns an empty Dataset, not an error

### Card maturity

#### Learned starts at 30 days
- **Given:** cards with intervals of 23h59m, 24h, 29d, and 30d
- **When:** the question overview rows are fetched
- **Then:** card_state is learning, established, established, learned respectively

#### New and locked states
- **Given:** a never-reviewed card in a locked section and one in an unlocked section
- **When:** the question overview rows are fetched
- **Then:** card_state is locked for the first and new for the second, and is_locked is true only for the first

### Essay state

#### Essay is grey with no oral and not all cards learned
- **Given:** `fix-essay-locked`
- **When:** the essay list is fetched
- **Then:** essay_state is grey

#### Essay is yellow only from a passed guided ESSAY oral
- **Given:** an essay whose every section has passed its guided section oral but no essay-scope oral
- **When:** the essay list is fetched
- **Then:** essay_state is grey; after a passing guided essay result is imported it is yellow

#### Essay is green when every card is learned
- **Given:** `fix-essay-learned` where one card is at 29d
- **When:** the essay list is fetched
- **Then:** essay_state is not green; after that card reaches 30d it is green

#### Essay with zero cards is never green
- **Given:** an essay with no cards
- **When:** the essay list is fetched
- **Then:** essay_state is not green

#### Essay is blue when every section has passed unguided
- **Given:** an essay with three sections, two unguided-passed
- **When:** the third passes unguided
- **Then:** essay_state becomes blue (and was not blue before)

#### Essay is violet after a passing unguided essay oral
- **Given:** `fix-essay-blue`
- **When:** a passing unguided essay result is imported
- **Then:** essay_state is violet and essay_unguided_passed_at equals the result's examined_at

#### Violet retake that passes keeps violet and updates the date
- **Given:** `fix-essay-violet`
- **When:** a passing unguided essay result with a later examined_at is imported
- **Then:** essay stays violet, the passed date updates, the attempt is in essay history, no card is flagged

#### Highest satisfied state is shown
- **Given:** an essay that is both green (all cards learned) and blue (all sections unguided passed) but not violet
- **When:** the essay list is fetched
- **Then:** essay_state is blue

### Failure cascade and revalidation flagging

#### Failing the unguided essay oral at violet removes violet and blue
- **Given:** `fix-essay-violet`
- **When:** a failing unguided essay result is imported
- **Then:** essay_state is no longer violet or blue and falls to the highest state still supported by evidence

#### Cascade invalidates every section's unguided pass but nothing else
- **Given:** `fix-essay-violet` whose sections are blue and yellow-capable
- **When:** a failing unguided essay result is imported
- **Then:** every section loses blue and falls back to green or yellow from existing evidence; every section's guided state, all examination history rows, and every card's last_reviewed_at, next_due_at, review_interval and FSRS state are unchanged

#### Cascade flags only cards that have been reviewed
- **Given:** `fix-essay-violet` with reviewed cards and never-reviewed cards
- **When:** a failing unguided essay result is imported
- **Then:** the response reports cards_flagged equal to the reviewed-card count, only those cards have needs_revalidation, and never-reviewed cards do not

#### Failing the unguided essay oral when not violet is history only
- **Given:** `fix-essay-blue` (essay not violet)
- **When:** a failing unguided essay result is imported
- **Then:** the attempt is stored, no section loses blue, and no card is flagged

#### Duplicate failing result cascades once
- **Given:** `fix-essay-violet`
- **When:** the same failing unguided essay result is imported twice
- **Then:** the first reports a cascade, the second reports none, and the flagged set is unchanged

#### Re-passing a section unguided after invalidation restores blue
- **Given:** a section invalidated by a cascade
- **When:** a passing unguided section result is imported
- **Then:** the section is blue again and its invalidated marker is cleared

### Revalidation

#### Flagged cards are available regardless of due date
- **Given:** flagged cards whose next_due_at is months in the future
- **When:** the revalidation queue is fetched for their essay
- **Then:** all of them are returned in section order, then level, then creation order

#### Flagged cards are excluded from the normal due queue
- **Given:** a flagged card that is also past its FSRS due date
- **When:** the due queue is fetched scoped to its essay and with no scope
- **Then:** the card is absent from both

#### Revalidation queue scoping
- **Given:** flagged cards in two essays
- **When:** the revalidation queue is fetched with no parameters, with one essay_id, and with an unknown essay_id
- **Then:** all flagged cards, only that essay's, and an empty Dataset respectively

#### Correct revalidation preserves FSRS state exactly
- **Given:** a flagged card with a known stability, difficulty, last_reviewed_at, next_due_at and review_interval
- **When:** a review with grade good is posted for it
- **Then:** the flag is cleared, the response revalidation_outcome is preserved with the unchanged timestamps, and last_reviewed_at, next_due_at, review_interval and fsrs_card_state are identical to before

#### Correct revalidation is not a normal review
- **Given:** a flagged card and the current review-event count and review-stats figures
- **When:** a review with grade good is posted for it
- **Then:** no review event is added and review-stats today/summary/activity figures are unchanged, while one revalidation audit record with outcome preserved exists

#### Hard and easy also count as correct
- **Given:** two flagged cards
- **When:** one is graded hard and one easy
- **Then:** both are preserved with no FSRS change

#### Incorrect revalidation is a genuine FSRS failure
- **Given:** a flagged card with a long interval
- **When:** a review with grade again is posted for it
- **Then:** the flag is cleared, revalidation_outcome is failed, the schedule and FSRS state change exactly as a normal again review would, one review event is added, and one revalidation audit record with outcome failed exists

#### Revalidation completes when the last flagged card is checked
- **Given:** an essay with 5 flagged cards, 4 answered correctly and 1 incorrectly
- **When:** the revalidation queue is fetched afterwards
- **Then:** it is empty for that essay and revalidation_pending_count is 0; only the incorrect card's schedule changed

#### Review of a card flagged mid-session is handled as revalidation
- **Given:** a card that was fetched in the normal queue and then flagged by a cascade
- **When:** the stale client posts a grade for it
- **Then:** it is processed as a revalidation (server-derived), not as a normal review

### Overview data

#### Essay list drops the Sprint12 fields and adds the new ones
- **Given:** the fixture essays
- **When:** the essay list and an essay detail are fetched
- **Then:** neither contains learning_level, the four milestone booleans, cards_seen_count, cards_future_safe_count or the old guided/unguided passed dates; both contain essay_state and the new essay fields with identical values for the same essay

#### Category-level counts are preserved
- **Given:** `fix-essay-yellow`
- **When:** the essay list is fetched
- **Then:** progress_total and progress_established equal the pre-sprint definitions (all cards; interval >= 24h)

#### open_count excludes locked and flagged cards
- **Given:** a locked essay with due-by-date cards and a violet essay with flagged due cards
- **When:** the essay list is fetched
- **Then:** open_count is 0 for the locked essay and excludes the flagged cards for the violet essay

#### Essay oral history lists attempts newest first
- **Given:** an essay with two essay-scope attempts
- **When:** its essay examination history is fetched
- **Then:** both appear most recent first with passed flags; an essay with none returns an empty Dataset; an unknown essay returns NOT_FOUND

### Migration

#### Backfill grandfathers sections with reviewed cards or old passing guided exams
- **Given:** a pre-sprint database where section A has a reviewed card, section B has a guided exam scored 3 and no reviewed cards, section C has neither
- **When:** the schema is applied
- **Then:** A and B are guided-passed with source grandfathered, C has no oral state and is locked

#### Backfill is one-time
- **Given:** the schema already applied and section C later left locked
- **When:** the schema is applied again
- **Then:** no state row is created or changed for C

#### Backfill records stored verdicts under the 70% rule
- **Given:** pre-sprint section_examinations rows with scores 3, 4, 5, 6
- **When:** the schema is applied
- **Then:** passed is false, false, true, true

### [UI] Overview

#### [UI] Essay card shows dots and none of the removed indicators
- **Given:** the overview with `fix-essay-yellow` and `fix-essay-locked`
- **When:** the overview loads
- **Then:** each essay card shows one large dot and one small dot per section in section order, and does not show PLANNED, COMPLETE, a 1/4 style level, a "x / y" card-progress line, or "Open:" text; category headings still show their established/open line

#### [UI] Dot tooltip names the section, state and next requirement
- **Given:** the overview
- **When:** the user hovers, focuses or taps a small dot
- **Then:** the section title, its state name and its next requirement are shown; each dot also has an accessible text label with its state name

#### [UI] Legend lists both ladders
- **Given:** the overview
- **When:** the user opens the legend
- **Then:** the four section states and five essay states are listed with the draft's wording, and the legend is not visible by default on each card

#### [UI] Revalidate entry appears only with pending cards
- **Given:** `fix-essay-violet` after a cascade and another essay with none pending
- **When:** the overview loads
- **Then:** only the first shows "Revalidate (N)" and activating it opens the Revalidation session

### [UI] Reader and oral import

#### [UI] Locked section is visibly locked in the reader
- **Given:** a section whose cards are locked
- **When:** the reader is opened
- **Then:** the section shows a lock hint, "Review this section" is unavailable with an explanation, and a guided-oral action is offered for that section

#### [UI] Section and essay oral actions are distinct
- **Given:** the reader for a complete essay
- **When:** the user opens the section menu and the essay menu
- **Then:** the section menu offers guided and unguided section orals, the essay menu offers guided and unguided full-essay orals, and the copied package for each reflects its scope

#### [UI] Import result shows verdict and cascade notice
- **Given:** a pasted failing unguided essay result for `fix-essay-violet`
- **When:** the user submits it on the import page
- **Then:** the page shows the result as not passed with its percentage, a notice that mastery was invalidated and N cards need revalidation, and a "Start revalidation" action

#### [UI] Locked cards are marked in the question overview
- **Given:** the question overview of `fix-essay-locked`
- **When:** it loads
- **Then:** its cards display a lock marker and no scheduling state, while cards in an unlocked section display their maturity state

### [UI] Revalidation session

#### [UI] Revalidation session shows remaining count and completes
- **Given:** an essay with three flagged cards
- **When:** the user opens the Revalidation session and answers all three using the two grade buttons (two Correct, one Incorrect; Correct sends grade good = preserved, Incorrect sends grade again = failed)
- **Then:** the session offers only the Correct and Incorrect buttons (no four-grade row, no Hard button), is labelled Revalidation, shows the remaining count decreasing, does not show the interval forecast, and ends with a "Revalidation complete" state linking back to the overview

### [UI] Stats

#### [UI] Essay progress zone shows traffic-light buckets
- **Given:** the Stats page with essays in several states
- **When:** it loads
- **Then:** the essay progress zone shows counts per essay state (grey, yellow, green, blue, violet) and no 0/4 to 4/4 buckets
