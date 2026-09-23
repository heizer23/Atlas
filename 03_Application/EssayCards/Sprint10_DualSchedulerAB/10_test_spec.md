# Test Spec — EssayCards — Sprint10_DualSchedulerAB

## Scope
Verifies that FSRS operates correctly as a second, persistently-assigned scheduling algorithm alongside an unmodified Classic algorithm, and that the existing due-queue selection/ordering/forecast mechanism is completely unaffected. Out of scope: FSRS parameter optimization, per-card algorithm switching, per-essay scheduler config, and any change to Focus/Review eligibility, resurfacing, or the seven forecast bands themselves (their behavior is exercised here only to confirm it is unchanged, not to re-derive it from scratch).

## Scenarios

### Classic again grade is flat five seconds via the endpoint
- **Given:** a flashcard, reviewed or never reviewed, on the classic scheduler
- **When:** it is graded "again" via POST /flashcards/{id}/review
- **Then:** the response's next_due_at is approximately 5 seconds after the review time, regardless of any prior review_interval

### Classic hard grade applies floor-or-doubled-elapsed via the endpoint
- **Given:** a never-reviewed classic-scheduler flashcard, and separately a classic-scheduler flashcard last reviewed some time ago
- **When:** each is graded "hard" via POST /flashcards/{id}/review
- **Then:** the never-reviewed card's next_due_at is the 1-minute floor; the previously-reviewed card's next_due_at is max(1 minute, 2 × elapsed since its last review)

### Classic easy grade applies floor-or-doubled-elapsed via the endpoint
- **Given:** a never-reviewed classic-scheduler flashcard, and separately a classic-scheduler flashcard last reviewed some time ago
- **When:** each is graded "easy" via POST /flashcards/{id}/review
- **Then:** the never-reviewed card's next_due_at is the 1-day floor; the previously-reviewed card's next_due_at is max(1 day, 2 × elapsed since its last review)

### Consecutive reviews on the same card chain from persisted state
- **Given:** a classic-scheduler flashcard
- **When:** it is graded twice in sequence via POST /flashcards/{id}/review
- **Then:** the second review's resulting next_due_at is computed from the first review's persisted last_reviewed_at, not from the original pre-review state

### Failure after several successful reviews still resets to flat five seconds
- **Given:** a classic-scheduler flashcard graded "good" or "easy" one or more times, building up a longer review_interval
- **When:** it is then graded "again"
- **Then:** the resulting next_due_at is approximately 5 seconds after the review time, discarding the accumulated interval entirely

### Mature card reviewed again applies doubling at multi-day scale via the endpoint
- **Given:** a classic-scheduler flashcard with review_interval already >= 24 hours (established)
- **When:** it is graded "good" or "easy" via POST /flashcards/{id}/review
- **Then:** the resulting review_interval is max(the grade's floor, 2 × elapsed since last review), correctly computed at a multi-day scale, not just the small-scale cases already covered by existing tests

### Boundary case at the exact floor crossing pins the tie-break
- **Given:** elapsed time such that 2 × elapsed equals a grade's floor exactly, for hard/good/easy
- **When:** compute_next_due_at is called with that exact elapsed value
- **Then:** the result is pinned deterministically (the floor wins on a tie), documenting max()'s tie-break behavior precisely

### Due-queue selection is scheduler-agnostic
- **Given:** a fixture set of due flashcards spanning both RECENT and BACKLOG categories, with a deliberate mix of classic-scheduler and fsrs-scheduler cards interleaved across that set
- **When:** GET /flashcards/due is called (both review/no-scope and a focus scope)
- **Then:** eligibility, RECENT-before-BACKLOG grouping, RECENT's next_due_at-DESC ordering, BACKLOG's review_interval-DESC ordering, the 24-hour threshold, and Focus-vs-Review eligibility are determined purely by next_due_at/last_reviewed_at/review_interval — identical to the pre-sprint ordering rules — with scheduler never appearing as a filter or sort key; the seven forecast bands (GET /flashcards/stats) also remain unaffected by the mix; each row's additive `is_new`/`is_recent`/`scheduled_interval_seconds` diagnostics fields still compute correctly across the scheduler mix, unaffected by which scheduler produced the row

### FSRS resurfacing uses the same RECENT mechanism as Classic
- **Given:** an fsrs-scheduler flashcard graded "again" (or any grade producing a short sub-hour learning-step interval)
- **When:** enough time elapses for that short interval to pass and GET /flashcards/due is called again
- **Then:** the card reappears via the existing RECENT category (last_reviewed_at within the rolling 24-hour window), exactly the same resurfacing mechanism Classic's own 5s/1min/20min floors already rely on — no separate FSRS queue exists

### FSRS rating mapping is correct
- **Given:** an fsrs-scheduler flashcard
- **When:** it is graded "again", "hard", "good", and "easy" in separate reviews
- **Then:** each grade drives the corresponding fsrs.Rating (Again/Hard/Good/Easy by name) into the library's review_card call, observable via the resulting fsrs_card_state's stability/difficulty/fsrs_state changing consistently with that rating's expected direction

### FSRS card state persists and reloads across requests
- **Given:** an fsrs-scheduler flashcard with an existing, previously-persisted fsrs_card_state row (simulating state surviving an application restart, since state is read fresh from the database on every request, never cached in-process)
- **When:** it is reviewed again via POST /flashcards/{id}/review
- **Then:** the review is computed from the reloaded prior stability/difficulty/state (via raw_state), not from a fresh card — the resulting fsrs_card_state reflects genuine continuation of history, not a reset

### FSRS handles a card's first-ever review with no prior state
- **Given:** an fsrs-scheduler flashcard with no fsrs_card_state row yet
- **When:** it is reviewed for the first time via POST /flashcards/{id}/review
- **Then:** a fresh fsrs_card_state row is created (library defaults — Learning state) and no error occurs from the absence of prior state

### FSRS relearning is handled correctly
- **Given:** an fsrs-scheduler flashcard whose fsrs_card_state reflects the Review state (already graduated)
- **When:** it is graded "again"
- **Then:** the resulting fsrs_state reflects Relearning, with a short relearning-step interval, persisted and flowing through next_due_at exactly like any other FSRS result

### FSRS due date flows through the existing fields with no separate queue
- **Given:** an fsrs-scheduler flashcard
- **When:** it is reviewed via POST /flashcards/{id}/review
- **Then:** the response and the persisted flashcard_review_state show next_due_at/review_interval set from the FSRS library's calculated due date — the same fields, same shape, same single writer as a classic-scheduler review

### FSRS datetime handling is timezone-correct
- **Given:** an fsrs-scheduler flashcard and the server's Postgres-sourced `now()` value
- **When:** a review is processed
- **Then:** the datetime passed into the FSRS library is UTC-aware in exactly the form the library requires, and no timezone-related error occurs

### New card creation assigns a scheduler permanently
- **Given:** the experiment kill switch enabled (default)
- **When:** a new flashcard is created (via essay/section ingest, POST /flashcards/upsert, or the flashcard-exploration import's create_card action)
- **Then:** its flashcard_review_state row is seeded with a scheduler ('classic' or 'fsrs'), a scheduler_assigned_at timestamp, scheduler_assignment_reason='new_card_random', and experiment_version='sprint10_v1' — and this assignment never changes afterward

### Editing an existing card never reassigns its scheduler
- **Given:** an existing flashcard with an established scheduler assignment
- **When:** its question, answer, or level is edited via POST /flashcards/upsert, or its essay/section is re-ingested
- **Then:** its scheduler, scheduler_assigned_at, and scheduler_assignment_reason are unchanged

### Kill switch disables new assignment without disturbing existing state
- **Given:** the experiment kill switch (ESSAYCARDS_FSRS_EXPERIMENT_ENABLED) set to false
- **When:** a new flashcard is created
- **Then:** it is assigned scheduler='classic', scheduler_assignment_reason='assignment_disabled_classic' — and no existing card's assignment or FSRS state is altered

### Assignment is approximately balanced across many cards
- **Given:** a set of many distinct new flashcard ids
- **When:** each is assigned via decide_scheduler_assignment
- **Then:** the split between classic and fsrs is approximately 50/50 (not exact, but not lopsided), with the same id always producing the same assignment on repeated calls

### Migration backfill retains previously-reviewed cards on Classic without altering their schedule
- **Given:** a flashcard_review_state row that predates this sprint and already has a non-null last_reviewed_at (real review history)
- **When:** the schema migration backfill runs
- **Then:** it is assigned scheduler='classic', scheduler_assignment_reason='legacy_retained_classic' — and its next_due_at, review_interval, and last_reviewed_at are byte-for-byte unchanged; no fsrs_card_state row is created for it

### Migration backfill assigns never-reviewed existing cards via the balanced mechanism
- **Given:** a flashcard_review_state row that predates this sprint and has never been reviewed (last_reviewed_at is null)
- **When:** the schema migration backfill runs
- **Then:** it receives a scheduler ('classic' or 'fsrs') via the same balanced mechanism as a brand-new card, with scheduler_assignment_reason='migrated_never_reviewed_random', and its next_due_at is unchanged

### Migration backfill is idempotent on rerun
- **Given:** a database where the migration backfill has already run once (every row has a non-null scheduler_assigned_at)
- **When:** schema.sql is executed again (as happens on every application startup)
- **Then:** no row's scheduler, scheduler_assignment_reason, or experiment_version changes, and no new rows are created or removed

### Experiment summary reports real recorded per-scheduler data with exposed sample sizes
- **Given:** a mix of assigned classic and fsrs cards, with recorded review_events spanning both established priors (prior_review_interval >= 24 hours) and learning-phase priors (prior_review_interval < 24 hours), both successful and "again" outcomes
- **When:** GET /experiment/summary is called
- **Then:** it returns exactly two rows ("classic", "fsrs"), each reporting assigned/reviewed/completed counts, a recall_rate restricted to events whose prior_review_interval was >= 24 hours (ordinary due-review evidence, per the corrected filter — NOT was_due, which is true for virtually every reachable review) with its sample size (ordinary_due_reviews) exposed alongside it, and failures counted only among those same events — a scheduler with zero such reviews shows a null recall_rate, not zero

### A rapid-retry review with a short prior interval is excluded from ordinary due-review evidence
- **Given:** a review_events row for a card whose prior_review_interval is short (learning-phase, < 24 hours) — e.g. an immediate relearning re-review following an "again" grade, or any other review of a card that had not yet graduated to established — noting that such a row's was_due is still true, since the card was, by the due-queue's own unchanged eligibility rule, genuinely due when re-reviewed
- **When:** GET /experiment/summary is called
- **Then:** that review is counted in completed_reviews but excluded from ordinary_due_reviews, recall_rate, and failures for its scheduler, because the filter is prior_review_interval >= interval '24 hours', not was_due — this is the concrete behavior that resolves 11_design_review.md's Major finding #1 (was_due cannot separate rapid-retry reviews from genuine retention evidence)

### [UI — manual] Scheduler badge shows the card's persisted algorithm before and after reveal
- **Given:** a due flashcard assigned to either scheduler, shown in the review session
- **When:** the user views the question and then flips to reveal the answer
- **Then:** a small badge in the top corner of the question card reads exactly "Classic" or "FSRS" (matching the card's persisted assignment), visible in both states, without replacing the existing Flip/grade buttons or changing the card's layout
