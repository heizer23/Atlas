# EssayCards Sprint13_ReviewStatsSentenceFeedback — design review notes

## Verdict
APPROVED_WITH_CHANGES (first review, `11_design_review.md`). Two Major findings, no
Critical, no Hard Rule Violations. Both findings are "the design specified behavior A and
behavior B correctly in isolation but never checked them against each other" — not
layer misplacement, not missing contracts, not rule violations.

## New recurring-pattern candidate: dual-purpose state variable, partial removal
When a sprint removes ONE of several UI behaviors driven by a single shared frontend
state variable, check every other read site of that variable before trusting the
design's own dead-code enumeration — even a design that does this well for one variable
(this sprint's `sessionForecast` family, complete with an explicit "confirm via grep
before deleting" instruction) can still miss it for a second, less obviously dual-purpose
variable (`reviewedCount`, which fed both the removed "Session" metric AND an unrelated,
untouched completion-screen message). The tell: grep every state variable whose single
listed consumer is being removed for OTHER call sites in the same file before accepting
the design's removal list as complete, rather than trusting the single most prominent
usage. See EVD-2026-10-05-001.

## New recurring-pattern candidate: nested-interactive-element tap precedence
When a design makes a container element tappable (opens a popover/modal) AND requires
preserving an existing child element's own independent tap/click behavior (links, nugget
refs, buttons) inside that same container, check explicitly for a stated click-event
precedence rule (stopPropagation or equivalent) between the two. StoryReader's
ReactionPopover precedent (which this sprint explicitly reuses) operates over PLAIN TEXT
with no nested interactive elements, so the precedent itself never had to solve this —
adapting it to markdown-rendered content introduces the conflict without carrying
forward a template answer. See EVD-2026-10-05-002. Worth checking again if a future
EssayCards/StoryReader sprint nests tap-to-open-popover inside richly-rendered markdown.

## Re-review (iteration 2, `13_design_review.md`) — APPROVED
Both Major findings were fixed correctly on the first correction pass (no 3rd
round needed). Verification approach: re-grepped the exact cited line numbers
in `src/ShellEntry.tsx` (2705/2751/2804/2830/2858) independently rather than
trusting `12_design_corrections.md`'s claim that they were "confirmed via
grep" — they matched exactly. Also read the live `NuggetLink` component
(`src/ShellEntry.tsx:1124`) to confirm the new CLICK PRECEDENCE rule
(`stopPropagation()` in the anchor's `onClick`) is actually implementable
against the existing three-branch `NuggetLink` (resolved nugget link /
unresolved nugget span / plain `<a>`) without contradicting any of its
existing behavior — it is: the unresolved-nugget branch renders a `<span>`,
not an `<a>`, so it correctly falls outside the "nested interactive element"
rule and is unaffected. Useful general check for this precedent: when a
design correction says "call stopPropagation in the anchor renderer," verify
the component actually *is* a single anchor-renderer function the fix can be
applied to, not multiple divergent branches where the rule might not apply
uniformly.

## Verification technique that worked well this sprint
For a sprint whose architecture.json makes many falsifiable factual claims about
*existing* code (e.g. "BarChart has no per-bar label slot", "the existing scopeCaption is
a small 12px caption, not a large heading", "StoryReader's reaction field is a 4-value
single-select enum over character-range spans"), grep/read the actual referenced source
files directly rather than taking the claims on faith — in this sprint every such claim
checked out as accurate, which is itself useful signal (this designer's self-reported
"found CLAUDE.md's no-page-header claim already accurate on inspection" and "caught one
stale `/review-stats/intervals` exposed_surfaces entry before this review" were both
independently verifiable and correct). Don't skip this verification step just because a
design self-reports having already fact-checked itself.
