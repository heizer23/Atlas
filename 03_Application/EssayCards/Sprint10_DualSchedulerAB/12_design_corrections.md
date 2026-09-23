# Design Corrections — EssayCards Dual Scheduler A/B (Sprint10_DualSchedulerAB)

## Applied Changes

1. **Redefine the dashboard's ordinary-due-review filter (Major finding #1 / Minimal Change Set #1)**
   - Review Source: `11_design_review.md` — Confirmed Problems #1, Recommended Improvements #1, Minimal Change Set #1
   - Files Updated: `10_architecture.json` (§contracts.invariants — the `was_due` invariant; §internal_flow step 13 `experiment_summary_query`)
   - Change: `ordinary_due_reviews`/`recall_rate`/`failures` in `GET /experiment/summary` are now filtered on `review_events.prior_review_interval >= interval '24 hours'` (mirroring the app's existing established/learning threshold) instead of `was_due`. The `was_due` invariant text is rewritten to explain *why* it cannot serve as the ordinary-due-review gate (it is true for virtually every reachable review, rapid retries included, because `GET /flashcards/due`'s unchanged base eligibility already requires `next_due_at <= now()` for every session type) and now documents it as an audit/diagnostic field only. No schema change was required — `prior_review_interval` already existed on `review_events` in `10_schema.sql`, confirming the reviewer's note that this is a filter-predicate fix, not a redesign.

2. **Update the affected `10_test_spec.md` scenarios (Minimal Change Set #2)**
   - Review Source: `11_design_review.md` — Minimal Change Set #2
   - Files Updated: `10_test_spec.md`
   - Change: Rewrote "Experiment summary reports real recorded per-scheduler data with exposed sample sizes" to describe the `prior_review_interval >= 24h` filter instead of `was_due=true/false`. The review also named a second scenario, "A non-due (was_due=false) review event is counted in completed_reviews but excluded from ordinary_due_reviews/recall_rate/failures," for update — that exact scenario was not present verbatim in `10_test_spec.md` (only `10_scaffolding.json`'s `test_experiment.py` anticipated a matching test function, `test_experiment_summary_excludes_non_due_reviews_from_recall_sample`, with no corresponding spec scenario). Added it as "A rapid-retry review with a short prior interval is excluded from ordinary due-review evidence," with Given/When/Then corrected to the new semantics (the row's `was_due` may still be `true`; exclusion is driven by a short `prior_review_interval`). See Notes below.
   - Also updated `10_scaffolding.json`'s `_review_counts_by_scheduler` purpose text and the `test_experiment_summary_excludes_non_due_reviews_from_recall_sample` purpose text to match the corrected filter, so the scaffold no longer describes the disproven `was_due`-based semantics as if correct.

3. **Correct `10_schema.sql`'s `was_due` column comment for consistency (R-CON-BP-09)**
   - Review Source: `11_design_review.md` — Confirmed Problems #1 (consistency follow-through, not a separately reviewed item)
   - Files Updated: `10_schema.sql`
   - Change: The comment above `essaycards.review_events` previously asserted the (incorrect) claim that "the dashboard's recall-rate sample is restricted to was_due = true rows." Rewritten to match the corrected architecture invariant, so the schema comment and `10_architecture.json` no longer contradict each other.

4. **Fold in Recommended Improvement #2 — due-row diagnostics regression coverage**
   - Review Source: `11_design_review.md` — Recommended Improvements #2
   - Files Updated: `10_test_spec.md`
   - Change: Extended the existing "Due-queue selection is scheduler-agnostic" scenario's Then-clause to explicitly assert that `is_new`/`is_recent`/`scheduled_interval_seconds` still compute correctly across a scheduler mix, per the review's own suggested approach ("extend the existing... scenario"). Small, low-risk addition to an existing scenario rather than a new file.

5. **Fold in Scaffold-Only Observation #1 — `_SCHEDULER_ASSIGNMENT_REASONS` dead-code risk**
   - Review Source: `11_design_review.md` — Scaffold-Only Observations #1
   - Files Updated: `10_scaffolding.json`
   - Change: Updated `_SCHEDULER_ASSIGNMENT_REASONS`'s purpose text (and `decide_scheduler_assignment`'s) to require wiring it in as a defensive assertion in `decide_scheduler_assignment`'s return path, per the review's own suggested alternative, so it is an active guard rather than dead code.

6. **Fold in Scaffold-Only Observation #2 — `experiment_version` literal duplication**
   - Review Source: `11_design_review.md` — Scaffold-Only Observations #2
   - Files Updated: `10_schema.sql`
   - Change: Added one-line comments at the column `DEFAULT 'sprint10_v1'` and both migration `UPDATE` literals pointing back to `backend.scheduling.EXPERIMENT_VERSION` as the canonical source, per the review's exact suggestion.

7. **Record Open Uncertainty — `fsrs.Scheduler` concurrency safety**
   - Review Source: `11_design_review.md` — Open Uncertainties #1
   - Files Updated: `10_architecture.json` (`deferrals.application_implementer`)
   - Change: Added a deferral instructing the implementer to confirm against the installed `fsrs>=6.3.2` source that `Scheduler.review_card` mutates only the passed-in `Card`, never the shared module-level `Scheduler`, before relying on the singleton — with the review's suggested cheap mitigation (a per-call `Scheduler`) noted if doubt remains. No design change was made to the singleton itself, since the review explicitly assigned this to the Implementer as a verification task, not a design defect.

## Unchanged by Design
- Every other section of `10_architecture.json`, `10_scaffolding.json`, and `10_schema.sql` — including the migration backfill logic, the scheduler dispatch/assignment mechanism, the `fsrs_card_state` table, the due-row `scheduler` field, the badge, and all other test spec scenarios — was preserved verbatim. `review_events.prior_review_interval`/`resulting_review_interval` columns, and the `review_events` write path (`_insert_review_event`), required no change — the data needed for the fix was already being persisted, exactly as the reviewer noted.

## Review Alignment Check
- Minimal Change Set Applied: Yes
- Approval Condition Satisfied: Yes — `GET /experiment/summary`'s `ordinary_due_reviews`/`recall_rate`/`failures` are now demonstrably filtered on `prior_review_interval >= interval '24 hours'`, which excludes rapid-retry/immediate-relearning reviews regardless of `was_due` (which the review showed evaluates true for virtually every reachable review).
- Notes: The review's Minimal Change Set #2 named a `10_test_spec.md` scenario ("A non-due (was_due=false) review event is counted...") that did not exist verbatim in the artifact at review time — only a matching test-function name existed in `10_scaffolding.json`. Resolved by adding the scenario under a name that accurately reflects the corrected semantics (renaming from "non-due" framing, since after the fix the excluded rows are *not* necessarily non-due — they are short-prior-interval) rather than reproducing the old, now-inaccurate title verbatim. Flagging this for human attention in case the reviewer intended a different scenario or a literal title match.
