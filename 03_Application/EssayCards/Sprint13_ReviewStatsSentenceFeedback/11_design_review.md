# Design Review — EssayCards (Sprint13_ReviewStatsSentenceFeedback)

## Verdict
- Status: APPROVED_WITH_CHANGES
- Summary: The design is well-grounded — the day/week/month time-basis split, the FIRST-EVER REVIEW definition, the StoryReader-adaptation rationale, and the breadcrumb/BarChart deviations are all verified accurate against the actual source and properly surfaced per R-OPS-BP-01. Two concrete implementability gaps were found in how the Review-page metric replacement and the sentence-tap interaction interleave with existing/adjacent behavior; both are narrow and fixable without redesign.

## Confirmed Problems

1. **`reviewed`/`reviewedCount` dead-code scope is incomplete**
   - Severity: Major
   - Location: `10_architecture.json` internal_flow step 3 and step 4; `10_scaffolding.json` `ReviewStatsPanel`/`ReviewSessionView` entries
   - Why it is a problem: `ReviewSessionView`'s `reviewedCount` state (`src/ShellEntry.tsx:2705`) feeds two unrelated call sites: the `reviewed` prop into `ReviewStatsPanel` (`:2830`, backing the old "Session" metric this sprint removes) and the completion-screen message at `:2858` (`reviewedCount === 0 ? 'Nothing due right now.' : 'Session complete...'`), which this sprint does not touch. The design's dead-code enumeration (internal_flow step 4 / deferrals.application_implementer) is explicit and grep-verified for the `sessionForecast` family, but says nothing about the symmetric case: `reviewed`/`reviewedCount` becomes a partially-dead reference once the five-metric row replaces the Session/Backlog/New trio — the prop is dropped from what's rendered, but the underlying state must survive for the completion message.
   - Impact: An implementer following the explicit "grep before deleting" discipline applied to `sessionForecast` has no equivalent instruction here, and no mention that `reviewed`/`reviewedCount` is a dual-purpose variable. The likely failure mode is deleting `reviewedCount` entirely (breaking the "Session complete" / "Nothing due" message) under the reasonable but wrong assumption it belongs to the same dead-code family as `sessionForecast`.
   - Likely Cause (Design Phase): Incomplete Contract Thinking — the design meticulously scoped one removal (forecast/session-tally family) but did not trace the second, less obvious consumer of the same state variable introduced by the same metric-row replacement.

2. **Sentence-tap-to-popover vs. nested link/nugget-tap precedence is undefined**
   - Severity: Major
   - Location: `10_architecture.json` internal_flow step 8; `10_scaffolding.json` `SectionSentences`/`SentenceFeedbackPopover` entries
   - Why it is a problem: Step 8 requires each sentence to be both (a) a tappable unit that opens `SentenceFeedbackPopover` on tap, and (b) rendered through a `ReactMarkdown` instance with the identical `remarkPlugins`/`urlTransform`/`components` props as the whole-section render it replaces — explicitly to preserve "nugget-ref clicks, links, images, bold per sentence fragment." A sentence containing a `NuggetLink` or external link now has two independently-specified tap behaviors (parent span opens the feedback popover; the inner `<a>` opens `NuggetPanel` or navigates) with no stated precedence, and no mention of `stopPropagation` or equivalent. CLAUDE.md documents `NuggetLink`'s click behavior as load-bearing ("never a route navigation, so reading position / review-session state survive opening and closing it").
   - Impact: Without resolving event-bubbling order, a tap on a nugget/link inside a sentence will also fire the sentence-span's tap handler (click events bubble), unless the implementer independently invents a `stopPropagation` fix — which the design neither specifies nor flags as a decision point. Depending on which handler wins, either nugget/link taps become unreliable or the feedback popover opens unexpectedly alongside every link interaction.
   - Likely Cause (Design Phase): Incomplete Contract Thinking — the two interaction requirements (whole-sentence tappability, inner-link tappability) were each individually well-specified but never checked against each other for the DOM nesting they both imply.

## Recommended Improvements

1. **CLAUDE.md's "## Review screen" section goes stale**
   - Location: `10_scaffolding.json` CLAUDE.md entry; `03_Application/EssayCards/CLAUDE.md` "## Review screen" section
   - Improvement: Extend the scaffolding's CLAUDE.md change role to also update "## Review screen" (the CURRENT/UPCOMING gutter description, the Session/Backlog/New trio, the "Session" forecast row) to match the new five-metric row and trimmed forecast grid.
   - Why: The scaffolding's CLAUDE.md role only mentions adding sentence-feedback and review-stats documentation; it is silent on this section even though internal_flow steps 1/3/4 substantially rewrite the exact behavior that section documents, leaving the app's canonical convention doc inconsistent with the shipped UI.

2. **Unscoped FIRST-EVER REVIEW CTE runs identically in three endpoints per request**
   - Location: `10_architecture.json` contracts.invariants "FIRST-EVER REVIEW"; `10_scaffolding.json` `_FIRST_EVER_CTE_SQL`
   - Improvement: Note in deferrals (or as a follow-up) that this full, unscoped `group by flashcard_id` scan over `essaycards.review_events` is recomputed on every call to `/today`, `/activity`, and `/summary`, with no window bound — worth a cheap sanity check (e.g., `EXPLAIN`) once real data volume grows, even though correctness is already assured by construction.
   - Why: Not a correctness defect, but the one clear scalability-shaped assumption in an otherwise well-bounded design; flagging it now avoids rediscovering it only after review_events grows large.

## Scaffold-Only Observations

1. **Essay-existence check for the two new sentence endpoints is implicit**
   - Location: `10_scaffolding.json` `sentence_feedback.py` — `list_essay_sentences`, `list_essay_sentence_feedback`
   - Observation: Both handlers state "404 NOT_FOUND if essay_id does not exist" but the query shape described (select sections for essay_id, zero rows is valid for a sectionless essay) cannot by itself distinguish "no such essay" from "essay exists with zero sections" — an explicit existence lookup is needed and isn't named.
   - Impact on implementation: Trivial to add (one extra `select 1 from essays where id = %s`), but worth stating so it isn't silently skipped, which would turn a 404 case into an empty-200 case.

## Hard Rule Violations

None identified.

## Open Uncertainties

1. **Scalability of the repeated unscoped FIRST-EVER REVIEW scan**
   - Location: `10_architecture.json` contracts.invariants "FIRST-EVER REVIEW"
   - Uncertainty: Whether the current `review_events` volume (and its expected growth) makes a full unscoped `group by flashcard_id` scan, repeated 3x per relevant page load, a practical concern this sprint or only much later.
   - Why it matters: Not a correctness risk, but could become a latency issue invisibly, since nothing in this sprint benchmarks it.
   - Suggested owner: Implementer

## Minimal Change Set
1. In `10_architecture.json` step 4 / `10_scaffolding.json`'s `ReviewSessionView` entry, explicitly state that `reviewedCount` state is RETAINED (feeds the completion-screen message, untouched by this sprint) while only the `reviewed` prop wiring into `ReviewStatsPanel` is dropped — add this to the same "confirm via grep" instruction already given for the `sessionForecast` family.
2. In `10_architecture.json` step 8 / `10_scaffolding.json`'s `SectionSentences`/`SentenceFeedbackPopover` entries, add an explicit rule for click precedence between the sentence-span tap (opens feedback popover) and an inner nugget-link/external-link tap (opens `NuggetPanel`/navigates) — e.g., the inner link's click handler calls `stopPropagation()` so link/nugget behavior always wins over the popover.

## Approval Condition
Both items in the Minimal Change Set are addressed in `10_architecture.json`/`10_scaffolding.json` (or a `12_design_corrections.md`) before implementation begins.
