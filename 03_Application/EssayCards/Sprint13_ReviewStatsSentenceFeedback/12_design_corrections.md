# Design Corrections — EssayCards (Sprint13_ReviewStatsSentenceFeedback)

## Applied Changes

1. **`reviewedCount` dead-code scope made explicit**
   - Review Source: `11_design_review.md` — Confirmed Problems #1 (Major); Minimal Change Set #1
   - Files Updated: `10_architecture.json` (internal_flow step 4 description; `deferrals.application_implementer`), `10_scaffolding.json` (`ReviewStatsPanel` and `ReviewSessionView` entries)
   - Change: Added an explicit statement that `ReviewSessionView`'s `reviewedCount` state (`src/ShellEntry.tsx:2705`) is a dual-purpose variable and NOT part of the `sessionForecast` dead-code family. Only the `reviewed` prop fed into `ReviewStatsPanel` (`:2830`, backed the now-removed old Session metric) is dropped; `reviewedCount`, `setReviewedCount` (reset at `:2751`, increment at `:2804`), and the completion-screen message that reads `reviewedCount` (`:2858`, "Nothing due right now." / "Session complete — nothing left in the queue.") must be retained verbatim. Added the same "confirm via grep before deleting" instruction already applied to the `sessionForecast` family, both inline in step 4 and in `deferrals.application_implementer`. `10_scaffolding.json`'s `ReviewStatsPanel` entry now states only the `reviewed` prop is removed from its signature; the `ReviewSessionView` entry now states `reviewedCount`/`setReviewedCount` are retained with their two legitimate call sites named.

2. **Sentence-tap vs. nested-link-tap click precedence defined**
   - Review Source: `11_design_review.md` — Confirmed Problems #2 (Major); Minimal Change Set #2
   - Files Updated: `10_architecture.json` (internal_flow step 8 description; `deferrals.application_implementer`), `10_scaffolding.json` (`SectionSentences` and `SentenceFeedbackPopover` entries)
   - Change: Added a binding CLICK PRECEDENCE rule to step 8: any nested interactive element rendered inside a sentence's `ReactMarkdown` instance (resolved `NuggetLink`, external/markdown links, or any anchor from `components={{a: ...}}`) must call `event.stopPropagation()` in its `onClick` before its own navigation/overlay-open logic runs, so a tap on a link or nugget-ref inside a sentence never also opens `SentenceFeedbackPopover`. The sentence span's own tap handler is defined to fire only when the click target is the span itself or a non-interactive descendant. Reflected in `10_scaffolding.json`'s `SectionSentences` entry (names the anchor renderer's `stopPropagation()` obligation) and noted on `SentenceFeedbackPopover`'s entry for clarity on scope. Also added to `deferrals.application_implementer`'s ReaderView/SectionSentences implementation note.

## Unchanged by Design
All sections not named above — including the Review-page five-metric row (step 3), the sentence-splitting algorithm (step 5), the `sentence_feedback` schema reference (step 6), the sentence-feedback endpoints (step 7), the Stats-page activity/summary reshape (steps 9-10), the daily activity chart and Observed Recall selector (steps 11-12), all `contracts`, `dependencies`, `persistence`, `deferrals.ui_implementer`/`test_writer`/`reviewer`, `deferred_decisions`, `risks`, and `open_questions` in `10_architecture.json`, and every other file entry in `10_scaffolding.json` — are preserved verbatim. No new files were introduced, no interfaces were renamed, and no artifact outside the Minimal Change Set was touched. `10_schema.sql` and `10_test_spec.md` were not modified — the review's Minimal Change Set did not reference them.

## Review Alignment Check
- Minimal Change Set Applied: Yes
- Approval Condition Satisfied: Yes
- Notes: Both corrections were verified against the live source (`src/ShellEntry.tsx:2705/2751/2804/2830/2858` confirmed via grep to match the review's exact claim about `reviewedCount`'s two consumers) before being written into the design artifacts, so the stated line references are accurate as of this correction pass.
