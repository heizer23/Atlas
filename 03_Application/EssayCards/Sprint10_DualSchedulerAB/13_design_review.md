# Design Review — EssayCards Dual Scheduler A/B (Sprint10_DualSchedulerAB)

## Verdict
- Status: APPROVED
- Summary: The corrector's fix — gating `ordinary_due_reviews`/`recall_rate`/`failures` on `review_events.prior_review_interval >= interval '24 hours'` instead of `was_due` — genuinely resolves the prior Major finding: rapid-retry/immediate-relearning reviews always follow a short (sub-24h, learning-phase) prior interval and are now excluded, while genuine spaced-retrieval reviews (which by construction follow an already-established >=24h prior interval) are still counted, with no new mismatch against `00_draft.md §7`. All four non-blocking items from the first review were also correctly addressed. One low-risk documentation/consistency nit remains (a stale index comment in `10_schema.sql` still describing a `was_due`-based rationale the correction disproved) — Minor, non-blocking.

## Confirmed Problems

1. **Stale `was_due`-based rationale survives in the `review_events` index comment**
   - Severity: Minor
   - Location: `10_schema.sql` lines 161–163 (`ix_review_events_scheduler_was_due` and its preceding comment)
   - Why it is a problem: The correction rewrote the `review_events` table-level comment (lines 130–144) to explicitly state that `was_due` is NOT the dashboard's filter and that `prior_review_interval >= interval '24 hours'` is used instead. Twenty lines later, in the same file, the index comment still reads "Supports the experiment dashboard's GROUP BY scheduler ... FILTER (WHERE was_due) aggregates" — a direct intra-file contradiction of the just-corrected invariant (R-CON-BP-09), and the index itself (`scheduler, was_due`) does not serve the actual corrected aggregate filter (`scheduler`, `prior_review_interval`). Since `10_schema.sql` is folded verbatim into the runtime `schema.sql` (per `10_scaffolding.json`'s file role for `schema.sql`), this stale index ships as-is.
   - Impact: No correctness risk — the aggregate query still executes correctly regardless of which index exists. Impact is limited to a misleading comment and a missed opportunity for a more useful index (`scheduler, prior_review_interval`) on a table with accepted unbounded append-only growth.

## Recommended Improvements
None identified.

## Scaffold-Only Observations
None identified.

## Hard Rule Violations
None identified.

## Open Uncertainties
None identified — the one open uncertainty carried from `11_design_review.md` (`fsrs.Scheduler` module-level concurrency safety) was correctly recorded as an implementer deferral in `10_architecture.json §deferrals.application_implementer`, per the original review's own suggested ownership (Implementer, verify-before-relying). No design change was required for it, and none is outstanding.

## Minimal Change Set
None required for approval. Optional cleanup (non-blocking, may be folded into implementation without a further review cycle): update `10_schema.sql`'s `ix_review_events_scheduler_was_due` comment (and optionally the index's columns, to `scheduler, prior_review_interval`) to match the corrected `prior_review_interval >= interval '24 hours'` filter.

## Approval Condition
None — approved as-is.
