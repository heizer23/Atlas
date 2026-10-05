# Design Review — EssayCards (Sprint13_ReviewStatsSentenceFeedback)

## Verdict
- Status: APPROVED
- Summary: Both Major findings from `11_design_review.md` are fixed correctly and completely. The `reviewedCount` dual-purpose-variable fix was independently verified against the live source (`src/ShellEntry.tsx:2705/2751/2804/2830/2858`) and matches exactly. The sentence-tap-vs-nested-link click-precedence rule is now explicit, consistent across `10_architecture.json`/`10_scaffolding.json`, and implementable against the existing `NuggetLink`/anchor-rendering code without contradiction. No new inconsistency was introduced, and `12_design_corrections.md`'s self-report matches the artifacts and the sprint log's recorded file-write list.

## Confirmed Problems
None identified.

## Recommended Improvements
1. **CLAUDE.md's "## Review screen" section still goes stale** (carried over from `11_design_review.md` Recommended Improvement #1, not addressed — this was never part of the Minimal Change Set)
   - Location: `10_scaffolding.json` CLAUDE.md entry; `03_Application/EssayCards/CLAUDE.md` "## Review screen" section
   - Improvement: Extend the scaffolding's CLAUDE.md change role to also update "## Review screen" (Session/Backlog/New trio, "Current"/"Upcoming" gutter labels) to match the new five-metric row and trimmed forecast grid.
   - Why: internal_flow steps 1/3/4 substantially rewrite exactly the behavior that section documents; the scaffolding's CLAUDE.md role still only names the new sentence-feedback/review-stats documentation additions.

## Scaffold-Only Observations
1. **Essay-existence check for the two new sentence endpoints is still implicit** (carried over from `11_design_review.md`, unaddressed — this was never part of the Minimal Change Set)
   - Location: `10_scaffolding.json` `sentence_feedback.py` — `list_essay_sentences`, `list_essay_sentence_feedback`
   - Observation: Both handlers still only state "404 NOT_FOUND if essay_id does not exist" without naming the explicit existence lookup needed to distinguish that from "essay exists with zero sections" (zero rows either way).
   - Impact on implementation: Trivial to add, but still worth stating explicitly so it isn't silently skipped.

## Hard Rule Violations
None identified.

## Open Uncertainties
1. **No explicit test scenario for the new click-precedence rule**
   - Location: `10_test_spec.md` — "[UI] Essay reader — tapping a sentence opens a two-button feedback popover" and the two adjacent sentence-feedback `[UI]` scenarios
   - Uncertainty: The test spec was correctly left untouched by this correction round (out of the Minimal Change Set), so it still has no scenario asserting that tapping a nugget-ref/link inside a sentence opens `NuggetPanel`/navigates rather than `SentenceFeedbackPopover` — the exact behavior newly specified in `10_architecture.json` internal_flow step 8's CLICK PRECEDENCE rule.
   - Why it matters: This is the one piece of newly-added binding behavior from this correction round with no corresponding acceptance criterion; an implementer could satisfy every existing `[UI]` scenario while still getting the precedence wrong in an edge case (e.g. a link at the very start/end of a sentence span).
   - Suggested owner: Implementer (cover in `tests/ui/sentence_feedback.spec.ts`, which `10_scaffolding.json` already scopes to this sprint's new sentence-feedback interactions).

## Minimal Change Set
None — design is approved as corrected.

## Approval Condition
None — approved as-is.
