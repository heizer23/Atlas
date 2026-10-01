# Test Spec — EssayCards — Sprint12_FSRSAndUXOverhaul

## Scope
Verifies that FSRS is the sole scheduler (including the legacy-state migration preserving due dates/history and the removal of the Sprint10 experiment), that the 0-4 essay learning-progress level and its four milestones (including the new guided/unguided exam_type split) calculate correctly and independently, that every pre-existing button/action survives the primary+dropdown consolidation and the new category collapse control, and that the reworked stats endpoints/page are zero-filled and correctly labeled. Out of scope: FSRS parameter optimization, re-deriving due-queue selection/ordering from scratch (exercised here only to confirm it is unaffected — see the note below), and any visual design decision not already fixed by existing Material 3 tokens.

**Reading note (binding, carried from Phase A investigation A2):** "identical card data, identical selection/ordering" means identical card data run through the SAME single (FSRS-only) scheduler, not that FSRS's own next_due_at/review_interval output must numerically match historical Classic output for the same card. A formerly-Classic card's BACKLOG position or established/learning classification changing after its first FSRS review is expected, not a regression.

## Scenarios

### FSRS is the only scheduler for a new card
- **Given:** a brand-new flashcard created via essay/section ingest, POST /flashcards/upsert, or the flashcard-exploration import's create_card action
- **When:** its flashcard_review_state row is inspected
- **Then:** it carries no scheduler-related column at all (they no longer exist on the table), and its first review is computed by FSRS regardless of creation path

### A review updates the due date through FSRS
- **Given:** any flashcard, new or previously reviewed
- **When:** it is graded via POST /flashcards/{id}/review
- **Then:** the response and the persisted flashcard_review_state show next_due_at/review_interval set from the FSRS library's calculated due date, and a corresponding fsrs_card_state row is upserted and one review_events row (no scheduler column) is inserted, all in the same transaction

### Due-queue selection and ordering are unaffected by the scheduler change
- **Given:** a fixture set of due flashcards spanning RECENT and BACKLOG categories, some with real pre-FSRS review history and some newly created
- **When:** GET /flashcards/due is called (both review/no-scope and a focus scope)
- **Then:** eligibility, RECENT-before-BACKLOG grouping, RECENT's next_due_at-DESC ordering, BACKLOG's review_interval-DESC ordering, the 24-hour threshold, and Focus-vs-Review eligibility behave exactly as before this sprint — no row carries a scheduler field

### Migration backfill preserves due dates and review history for a legacy-reviewed card
- **Given:** a fixture flashcard with real review history (last_reviewed_at set, review_interval established) and no existing fsrs_card_state row
- **When:** the application starts (schema.sql migration, then the Python legacy FSRS-state backfill)
- **Then:** the card gains an fsrs_card_state row synthesized from its current review_interval, while its next_due_at, review_interval, and last_reviewed_at are byte-for-byte unchanged

### Migration backfill is safe to rerun
- **Given:** a database where the backup table exists and every eligible card already has fsrs_card_state
- **When:** the application restarts again
- **Then:** the backup table is not recreated or repopulated, no fsrs_card_state row is overwritten, and no error occurs

### Migration backfill skips a card that already has native FSRS state
- **Given:** a fixture flashcard that already carries an fsrs_card_state row
- **When:** the legacy backfill runs
- **Then:** that row is left completely untouched

### Scheduling data is backed up before destructive migration
- **Given:** a pre-Sprint12 database with Sprint10 scheduler-assignment data present
- **When:** the application starts and schema.sql's migration runs
- **Then:** essaycards.pre_fsrs_migration_backup_sprint12 contains a snapshot of every flashcard_review_state row's scheduler/scheduler_assigned_at/scheduler_assignment_reason/experiment_version/last_reviewed_at/next_due_at/review_interval as it stood immediately before the columns were dropped

### The dual-scheduler experiment is fully removed
- **Given:** the running application after this sprint
- **When:** GET /api/essaycards/experiment/summary is called
- **Then:** the route does not exist (404, not a scheduler-filtered empty result)

### Essay with zero cards never satisfies the card milestones
- **Given:** an essay with sections but no flashcards
- **When:** GET /essays (or GET /essays/{id}) is read
- **Then:** milestone_all_cards_seen and milestone_all_cards_future_safe are both false, regardless of any exam state, and they do not contribute to learning_level

### All cards seen and future-safe satisfies both card milestones
- **Given:** an essay whose every flashcard has been reviewed and has next_due_at more than 24 hours from now
- **When:** GET /essays is read
- **Then:** milestone_all_cards_seen and milestone_all_cards_future_safe are both true, and cards_seen_count/cards_future_safe_count both equal progress_total

### One unseen card keeps the cards-seen milestone false
- **Given:** an essay where every card but one has been reviewed
- **When:** GET /essays is read
- **Then:** milestone_all_cards_seen is false and cards_seen_count is one less than progress_total

### Guided-passed requires every section to individually meet the threshold
- **Given:** an essay with multiple sections, where every section has a latest guided-type examination scoring 3 or higher except one section scoring below 3
- **When:** GET /essays is read
- **Then:** milestone_guided_passed is false, even though most sections pass — an average above the threshold is not sufficient

### Guided and unguided milestones are independent
- **Given:** an essay where every section's latest guided exam scores >= 3 but no section has ever had an unguided exam
- **When:** GET /essays is read
- **Then:** milestone_guided_passed is true and guided_passed_at is set, while milestone_unguided_passed is false and unguided_passed_at is null

### learning_level sums the four milestones regardless of which ones are true
- **Given:** essays fixture-constructed to hit each of learning_level 0, 1, 2, 3, and 4 via different combinations of the four milestones (not necessarily completed in the 1-2-3-4 order)
- **When:** GET /essays is read
- **Then:** each essay's learning_level equals exactly the count of its true milestones

### Essay detail carries the same learning-progress fields as the list
- **Given:** an essay with a known learning_level and milestone state
- **When:** GET /essays/{id} is called and compared against that essay's row from GET /essays
- **Then:** all nine learning-progress fields match exactly between the two endpoints

### Essay status is unaffected by this sprint
- **Given:** an essay with status='planned'
- **When:** GET /essays or GET /essays/{id} is read
- **Then:** status still reads 'planned', computed and gated exactly as before this sprint

### Examination package requires a valid exam_type
- **Given:** an existing essay
- **When:** GET /essays/{id}/examination-package is called with no exam_type, or with an invalid value
- **Then:** the response is ApiError VALIDATION_ERROR (not FastAPI's default 422 shape)

### Unguided examination package never includes calibration context
- **Given:** an essay whose sections have prior guided-type examination history
- **When:** GET /essays/{id}/examination-package?exam_type=unguided is called
- **Then:** every section's last_examination is null, regardless of the guided history that exists

### Guided examination package uses only guided history for calibration
- **Given:** an essay with both guided- and unguided-type prior examinations for the same section
- **When:** GET /essays/{id}/examination-package?exam_type=guided is called
- **Then:** that section's last_examination reflects only the latest guided-type row, never the unguided one

### Importing examination results requires exam_type on every result
- **Given:** a results payload where one entry omits exam_type
- **When:** POST /examinations/import is called
- **Then:** the whole batch is rejected with VALIDATION_ERROR and nothing is written

### Importing examination results rejects an invalid exam_type value
- **Given:** a results payload where one entry has exam_type outside ('guided','unguided')
- **When:** POST /examinations/import is called
- **Then:** the whole batch is rejected with VALIDATION_ERROR

### Section examination history shows exam_type
- **Given:** a section with both a guided and an unguided examination on record
- **When:** GET /sections/{id}/examinations is called
- **Then:** each row carries its correct exam_type

### Review activity endpoint is zero-filled over a fixed 30-day window
- **Given:** review_events rows scattered across the last 10 days and none before that
- **When:** GET /review-stats/activity is called
- **Then:** exactly 30 rows are returned, oldest UTC calendar day first, with 0 reviews on every day with no recorded review

### Review intervals endpoint sums to the total scheduled card count
- **Given:** a mix of new, learning, and long-established cards
- **When:** GET /review-stats/intervals is called
- **Then:** exactly six zero-filled buckets are returned and their counts sum to the total number of flashcard_review_state rows

### Every pre-existing button/action remains reachable after consolidation
- **Given:** an essay with sections, cards, a complete status, and prior examination history
- **When:** the essay's reader page and overview page are inspected
- **Then:** every action from the Phase A investigation inventory is reachable: at the overview, Images / Import exam results / Import exploration / Due for review (page-level), and per-category Study (unchanged); at the essay header, ← All essays, Question overview, Export essay/Import, + New nugget, Study, Guided oral exam, and Unguided oral exam (the last three newly placed here); at each section end, Review this section, Export section/Import, Insert section after/Import, and the examination history list — none silently dropped

### [UI] Category collapse control hides and restores essay rows, and its state survives a reload
- **Given:** the essay overview page with at least one named category (e.g. Philosophy) containing more than one essay
- **When:** the user taps/clicks the category's collapse toggle, then reloads the page
- **Then:** the category's essay rows are hidden while its heading (title, established/total, open count, Study button) stays visible; after reload, the category remains collapsed, reflecting the persisted state; the control is operable by keyboard (Tab + Enter/Space) with a clear expanded/collapsed indication

### [UI] Essay header action menu exposes Study and both oral exam variants without a cluttered button row
- **Given:** a complete-status essay with flashcards, reached from the overview
- **When:** the user opens the essay and activates its action menu
- **Then:** Study is immediately available as the primary action (or, for an essay with no cards, Question overview is primary instead), and Guided oral exam / Unguided oral exam / Export essay / + New nugget are reachable from the secondary dropdown, with no more than the back button and one primary button visible outside the menu

### [UI] Learning-level badge shows a tooltip naming all four milestones
- **Given:** an essay at a known partial learning_level (e.g. 2 of 4)
- **When:** the user inspects the badge on the overview row or the essay header (hover, focus, or tap depending on input method)
- **Then:** an accessible explanation names all four milestones and shows which are currently true/false, without requiring the user to already know the scoring scheme
