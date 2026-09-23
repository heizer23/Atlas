# Design Review — EssayCards Dual Scheduler A/B (Sprint10_DualSchedulerAB)

## Verdict
- Status: APPROVED_WITH_CHANGES
- Summary: The design's single hard constraint — that the existing due-queue selection/ordering mechanism is completely untouched — is satisfied with high confidence: `list_due_flashcards`/`flashcard_queue_stats` gain only an additive SELECT column, `compute_next_due_at` is verified byte-for-byte unchanged and wrapped (not altered) at its one call site, migration and new-card assignment are correctly scoped and idempotent, and the review write path is genuinely atomic. One Major issue must be fixed before implementation: the `review_events.was_due` flag, as specified, cannot achieve the mission's explicit "exclude rapid-retry/immediate-relearning reviews from the recall-rate sample" requirement, because every review reachable through the app's existing due-queue flow already satisfies the flag's own truth condition.

## Confirmed Problems

1. **`was_due` cannot separate rapid-retry reviews from genuine retention evidence**
   - Severity: Major
   - Location: `10_architecture.json §contracts.invariants` (the `review_events.was_due` invariant) and `§internal_flow` step 13 (`experiment_summary_query`, which filters `ordinary_due_reviews`/`recall_rate`/`failures` on `was_due`)
   - Why it is a problem: `was_due` is defined as `(the card's next_due_at BEFORE this review) <= (now)`. But `GET /flashcards/due`'s own eligibility clause (`backend/routers/flashcards.py::list_due_flashcards`, base condition `frs.next_due_at <= now()`) is unchanged and applies to *every* session type (Review and Focus alike — confirmed against the live code and `CLAUDE.md`'s "Focus vs review" section, which states Focus also only surfaces `next_due_at <= now()` cards, differing from Review only by the additional 24h interval filter). `POST /flashcards/{id}/review` is only ever invoked by the frontend on a card drawn from that queue (`ReviewSessionView` always grades `queue[0]`). A card that reappears via the RECENT category after an "again"/short-interval grade only reappears once its (short) `next_due_at` has itself elapsed — i.e. it is, by construction, due at the moment it is re-reviewed. Consequently `was_due` will be `true` for essentially every real review the application produces, including the exact "immediate relearning" rapid retries the design's own invariant text names as the case it exists to exclude.
   - Impact: `GET /experiment/summary`'s `recall_rate`/`ordinary_due_reviews`/`failures` will, in practice, include rapid-retry drilling alongside genuine spaced-retrieval reviews — precisely what `00_draft.md §7` prohibits ("Do not count multiple rapid retries as independent evidence of long-term retention"). The dashboard's central comparison metric is compromised from the first day of data collection, and the flaw is not visible from the architecture doc alone (its own invariant text asserts a separation that the surrounding system's already-unchanged eligibility invariant makes unreachable).
   - Likely Cause (Design Phase): Incomplete Contract Thinking — the invariant reused "due" as a proxy for "not a rapid retry" without checking it against the (correctly!) preserved due-queue eligibility invariant elsewhere in the same document, which guarantees the proxy always evaluates true in production use.

## Recommended Improvements

1. **Use an axis that can actually distinguish rapid retries from spaced retrieval**
   - Location: `10_architecture.json §internal_flow` step 13 and step 4 (`review_events` write); `10_schema.sql §essaycards.review_events`
   - Improvement: `review_events` already captures `prior_review_interval` — the redesign should filter `ordinary_due_reviews`/`recall_rate`/`failures` on that (or an equivalent signal, e.g. `prior_review_interval >= interval '24 hours'`, mirroring the app's own established/learning threshold) instead of, or in addition to, `was_due`.
   - Why: The data needed for a correct fix is already being persisted; only the filter predicate used by `experiment_summary_query` needs to change.

2. **Add an explicit due-row diagnostics regression scenario**
   - Location: `10_test_spec.md` (no scenario currently names `is_new`/`is_recent`/`scheduled_interval_seconds`)
   - Improvement: Add (or extend the existing "Due-queue selection is scheduler-agnostic" scenario to explicitly assert) that these three additive due-row fields still compute correctly once rows are a scheduler mix.
   - Why: `00_draft.md §8` separately lists "Recency indicators and diagnostics" among the selection-mechanism items to protect; the fields feed the review screen's bold-frame/diagnostics UI directly and are worth a named assertion even though their underlying SQL expressions are untouched by this sprint.

## Scaffold-Only Observations

1. **`_SCHEDULER_ASSIGNMENT_REASONS` appears to be documentation-only**
   - Location: `10_scaffolding.json` — `backend/scheduling.py` private_objects, `_SCHEDULER_ASSIGNMENT_REASONS`
   - Observation: Its stated purpose is "for validation/reference; the CHECK constraint in schema.sql is the actual enforcement point" — no call site is described anywhere in `internal_flow` that actually validates against it.
   - Impact on implementation: Low risk, but if no code path reads it, it should be a comment rather than a runtime constant, or the implementer should wire it into `decide_scheduler_assignment`'s return value as a defensive assertion so it is not dead code.

2. **`experiment_version` literal is duplicated across Python and SQL with no shared source**
   - Location: `10_scaffolding.json` (`EXPERIMENT_VERSION = 'sprint10_v1'` in `backend/scheduling.py`) vs. `10_schema.sql` (the column's `DEFAULT 'sprint10_v1'` and both migration UPDATEs' literal `'sprint10_v1'`)
   - Observation: Three independent occurrences of the same string literal, unavoidable given the DDL/Python split, but worth a one-line comment in each SQL location pointing back to `backend.scheduling.EXPERIMENT_VERSION` as the string's canonical definition, so a future version bump is less likely to update one location and miss another (R-CON-BP-07 canonical-path spirit).
   - Impact on implementation: Low — cosmetic/documentation only, no functional risk this sprint.

## Hard Rule Violations
None identified.

## Open Uncertainties

1. **Module-level `fsrs.Scheduler` concurrency safety**
   - Location: `10_architecture.json §internal_flow` step 3 (`fsrs_scheduler_review`) and `10_scaffolding.json` (`_FSRS_SCHEDULER`, "Constructed once, module-level ... and reused")
   - Uncertainty: The design assumes `fsrs.Scheduler.review_card(card, rating, review_datetime=...)` mutates only the passed-in `Card`, never the `Scheduler` instance itself, making a single shared module-level instance safe under FastAPI's concurrent request handling. This was not independently confirmed against the py-fsrs source (the library's own docs do not explicitly state this).
   - Why it matters: If `review_card` were ever found to mutate shared scheduler state, concurrent reviews could corrupt each other's results — a correctness issue that would be very hard to reproduce and diagnose after the fact.
   - Suggested owner: Implementer (confirm against the installed `fsrs>=6.3.2` source before relying on the singleton; if any doubt remains, a scheduler-per-call construction is a trivial, cheap mitigation).

## Minimal Change Set
1. Redefine the filter used to populate `ordinary_due_reviews`/`recall_rate`/`failures` in `GET /experiment/summary` (and the corresponding parts of the `review_events` write / `was_due` invariant text) so it actually excludes immediate-relearning/rapid-retry reviews — e.g. by filtering on `prior_review_interval` against the existing 24h learning/established threshold rather than (or in addition to) `was_due`.
2. Update `10_architecture.json §contracts.invariants` (the `was_due` invariant) and `§internal_flow` step 13, and the two affected `10_test_spec.md` scenarios ("Experiment summary reports real recorded per-scheduler data with exposed sample sizes" and "A non-due (was_due=false) review event is counted in completed_reviews but excluded from ordinary_due_reviews/recall_rate/failures"), to reflect the corrected filter semantics.

## Approval Condition
- The recall-rate/sample-size mechanism in `GET /experiment/summary` is redefined so it demonstrably excludes rapid-retry/immediate-relearning reviews from `ordinary_due_reviews`/`recall_rate`/`failures`, given that `was_due` as currently specified evaluates true for virtually every review reachable through the unchanged due-queue eligibility mechanism.
