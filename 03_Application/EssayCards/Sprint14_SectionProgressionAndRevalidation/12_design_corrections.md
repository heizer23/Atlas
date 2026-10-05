# Design Corrections — essaycards (Sprint14_SectionProgressionAndRevalidation)

## Applied Changes
1. **Pinned revalidation grade control**
   - Review Source: `11_design_review.md` Confirmed Problem 1 / Minimal Change Set 1 / Approval Condition
   - Files Updated: `10_architecture.json` (internal_flow step 16), `10_scaffolding.json` (ReviewSessionView), `10_test_spec.md` ([UI] Revalidation session)
   - Change: Revalidation mode shows exactly two buttons, Correct (sends `good`, correct, preserved) and Incorrect (sends `again`, incorrect, failed). No four-grade row and no Hard button, so no ambiguous Hard outcome. The server rule (hard/easy also correct for non-UI clients) is unchanged. The [UI] scenario now names this control and mapping.
2. **Schema header vs backfill wording**
   - Review Source: Confirmed Problem 2, Recommended Improvement 2, Hard Rule Violation R-CON-BP-09
   - Files Updated: `10_schema.sql`
   - Change: Header says the one-time backfill re-grades history under the 70% rule (literal 420) and that new rows carry the write-time verdict. It also notes that grandfathering (guided >= 3) is separate.
3. **/flashcards/stats purpose**
   - Review Source: Confirmed Problem 3, Recommended Improvement 1, Hard Rule Violation R-CON-BP-08
   - Files Updated: `10_architecture.json`
   - Change: The purpose now states that locked cards are excluded and flagged cards stay counted in their FSRS bands, so due_now can exceed the focus queue. The first of the two options offered in the review was chosen, so there is no mechanism change.
4. **fixtures.sql vs `passed NOT NULL`**
   - Review Source: Scaffold-Only Observation 1
   - Files Updated: `10_architecture.json` (step 18), `10_scaffolding.json` (tests/fixtures.sql), `10_schema.sql` (comment)
   - Change: Chose explicit fixture updates over a column default. The three existing `section_examinations` INSERTs must supply `passed` (score >= 5). The schema stays without a default.
5. **Nested begin/commit**
   - Review Source: Scaffold-Only Observation 2
   - Files Updated: `10_schema.sql`, `10_architecture.json` (step 1), `10_scaffolding.json` (schema.sql)
   - Change: Removed the file's own `begin;` and `commit;`. The fold-in is documented as running inside schema.sql's single transaction.
6. **ESSAY_EXAMINATION_SCHEMA missing `id`**
   - Review Source: Scaffold-Only Observation 3
   - Files Updated: `10_scaffolding.json`
   - Change: Added `id` to the column list, matching the architecture row_shape.
7. **next_step null rule**
   - Review Source: Scaffold-Only Observation 4
   - Files Updated: `10_architecture.json` (step 7)
   - Change: The two ladders are now separate. Section next_step is null at blue. essay_next_step is null at violet, and an essay at Blue reports `unguided_essay_oral`.
8. **Concurrency guard**
   - Review Source: Open Uncertainty 6, which the user asked to resolve
   - Files Updated: `10_architecture.json` (step 6), `10_scaffolding.json` (apply_essay_attempt)
   - Change: Pinned to insert-if-absent (`ON CONFLICT DO NOTHING`) followed by `SELECT ... FOR UPDATE`.

## Unchanged by Design
- All other sections of the three design artifacts and the test spec were preserved verbatim, including the pass rule, cascade, queue rules, state ladders, backfill SQL and every other scenario.
- Recommended Improvement 3 (stopPropagation on SectionProgressDots) was not applied. It is not in the Minimal Change Set and was not requested.
- The zero-card guided-passed section reporting `flashcards_established` was not changed. It is a behavior change, not a wording fix.

## Review Alignment Check
- Minimal Change Set Applied: Yes
- Approval Condition Satisfied: Yes
- Notes: I could not run a JSON parser in this environment. The edits only replaced string content, used no double quotes inside strings, and left the structure untouched. Run a parser before the re-review. Open Uncertainties 1-5 are product decisions and are untouched.
