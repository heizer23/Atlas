# Design Review — EssayCards (Sprint14_SectionProgressionAndRevalidation) — Re-review

**Verdict:** APPROVED
**Date:** 2026-10-05
**Reviewer:** sprint_design_reviewer

## Verdict
- Status: APPROVED
- Summary: All eight corrections in `12_design_corrections.md` landed as stated, and each is reflected consistently across `10_architecture.json`, `10_scaffolding.json`, `10_schema.sql` and `10_test_spec.md`. The Major finding from `11_design_review.md` is resolved. The revalidation grade control is pinned to Correct -> `good` (preserved) and Incorrect -> `again` (failed) in all four artifacts, with no remaining contradiction. I found no new problems. Both JSON files parse by careful reading (balanced structure, no trailing commas, no unescaped inner double quotes in the edited strings); I did not execute a parser.

## Confirmed Problems
None identified.

## Recommended Improvements
1. **Pin tap precedence on section dots (carried from review 11, not applied, non-blocking)**
   - Location: `10_scaffolding.json` src/ShellEntry.tsx `SectionProgressDots`
   - Improvement: State `stopPropagation` as `EssayProgressDot` does, since the dots sit inside the same navigable row.
   - Why: Otherwise tap precedence is left to the implementer.
2. **Align the `CLAUDE.md` Queue stats sentence with the new stats purpose (non-blocking)**
   - Location: `10_scaffolding.json` CLAUDE.md role; `10_architecture.json` internal_flow step 18
   - Improvement: The existing `CLAUDE.md` "## Queue stats" text says the forecast "matches the focus session it accompanies". Step 18 lists the `CLAUDE.md` edits but not this sentence. Add it to that list, because the stats purpose now says due_now can exceed the focus queue.
   - Why: Avoids reintroducing the self-contradiction in the docs.

## Scaffold-Only Observations
None identified.

## Hard Rule Violations
None identified.

Correction verification (each checked against the artifacts):
- Grade control: `10_architecture.json` step 16, `10_scaffolding.json` `ReviewSessionView`, and `10_test_spec.md` "[UI] Revalidation session" all name exactly two buttons, Correct -> `good` and Incorrect -> `again`. All three also say no four-grade row and no Hard button. The server rule is unchanged (`REVALIDATION_FAIL_GRADES = ('again',)`), and the test "Hard and easy also count as correct" remains valid at API level. No contradiction.
- Schema header: lines 20-27 now match the backfill (literal 420, lines 46-48), the grandfathering rule (`pass_legacy` score >= 3), and the test "Backfill records stored verdicts under the 70% rule". R-CON-BP-09 satisfied.
- Stats purpose: matches `boundary_construction` ("needs_revalidation cards remain counted"). R-CON-BP-08 satisfied.
- Fixtures: step 18, the scaffold's `tests/fixtures.sql` entry, and the `10_schema.sql` comment all require explicit `passed` on the three existing inserts, and the column has no default.
- Transactions: `10_schema.sql` has no `begin;`/`commit;`. Step 1 and the scaffold's `schema.sql` role both say it folds into the single existing transaction. The `do $$` block is unaffected.
- `ESSAY_EXAMINATION_SCHEMA` now includes `id`, matching the architecture row_shape.
- `next_step`: step 7 separates the section ladder (null at blue) from the essay ladder (null at violet, `unguided_essay_oral` at Blue). No test scenario conflicts ("Passing the unguided section oral makes the section blue" expects next_step null for a section).
- Concurrency guard: step 6 and the scaffold's `apply_essay_attempt` both name insert-if-absent (`ON CONFLICT DO NOTHING`) followed by `SELECT ... FOR UPDATE`.

## Open Uncertainties
Product-owned items already documented in `10_architecture.json` open_questions[0-6] and in `11_design_review.md` remain open. They are not re-litigated and do not block. They cover the 5/6 pass bar, the Violet-only cascade, flagging only reviewed cards, grandfathering, the `open_count` change, whether a failed unguided section oral revokes Blue, and the `status === 'complete'` gating of oral buttons.
1. **Zero-card guided-passed section never turns green**
   - Location: `10_architecture.json` internal_flow step 7
   - Uncertainty: Such a section reports `flashcards_established` indefinitely. The designer deliberately left this unchanged (behavior, not wording), and the test "Section with guided passed but zero cards is yellow, never green" covers it.
   - Why it matters: Only a misleading tooltip in an edge case.
   - Suggested owner: Product

## Minimal Change Set
None required.

## Approval Condition
- None — approved as-is.
