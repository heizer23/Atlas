# Design Review — EssayCards FSRS-Only Scheduling & UX Overhaul (Sprint12_FSRSAndUXOverhaul)

## Verdict
- Status: APPROVED
- Summary: All three issues from `11_design_review.md` are verifiably fixed. `estimate_initial_fsrs_state` is now the consistent three-argument form `(review_interval, last_reviewed_at, desired_retention)` everywhere it appears across `10_architecture.json` and `10_scaffolding.json`, including the one occurrence (`internal_flow` step 4) the corrector caught beyond the review's literal citation list. The new top-level `button_nav_inventory` block in `10_architecture.json` is self-contained (no `/tmp` or scratchpad references remain) and was independently verified against the live `src/ShellEntry.tsx` and `src/shellConfig.ts` — every entry (page-level buttons, per-category/per-essay actions, essay-header row, section-end row, main nav) matches the actual pre-sprint code exactly. The `ForecastGrid` extraction is concretely scaffolded with a props-decoupled shape (`{rows: {label, values}[]}`) that lines up with the already-existing `ForecastRow` component and the `allRow`/`sessionRow` arrays `ReviewStatsPanel` already computes — the reuse plan is now mechanically achievable, not aspirational. No new cross-artifact inconsistency was introduced by the corrections.

## Confirmed Problems
None identified.

## Recommended Improvements
None identified (no change beyond the Minimal Change Set from `11_design_review.md` is required for approval).

## Scaffold-Only Observations
1. **New `ESSAY_OVERVIEW_SCHEMA` fields still lack declared `ColumnSchema` types**
   - Location: `10_scaffolding.json` — `backend/routers/essays.py` entry, `ESSAY_OVERVIEW_SCHEMA` purpose text (unchanged by the corrections)
   - Observation: Carried forward from `11_design_review.md` §Scaffold-Only Observations #1 — correctly left unaddressed since it was not part of the Minimal Change Set. The four `milestone_*` booleans, `learning_level`, the two `*_count` integers, and the two `*_passed_at` dates are still named but not typed.
   - Impact on implementation: Low risk — types are inferable from field names — but still worth stating explicitly for consistency with every other `ColumnSchema` entry in this file.

## Hard Rule Violations
None identified. (`estimate_initial_fsrs_state`'s signature is now consistent across `10_architecture.json` §contracts.invariants, §internal_flow step 4, §deferrals.application_implementer, and `10_scaffolding.json`'s `backend/scheduling.py` `public_objects` entry — all three-argument `(review_interval, last_reviewed_at, desired_retention)` — verified by direct read of every occurrence.)

## Open Uncertainties
1. **Exact placement of `migrate_legacy_fsrs_state()` inside `backend/main.py`'s startup retry loop** — carried forward, unresolved, from `11_design_review.md` §Open Uncertainties #1. Not addressed by the corrections (correctly — it was not part of the Minimal Change Set). Suggested owner: Implementer.
2. **`review_datetime` input to the difficulty-bootstrap `review_card()` call in `estimate_initial_fsrs_state`** — carried forward, unresolved, from `11_design_review.md` §Open Uncertainties #2. Not addressed by the corrections (correctly — it was not part of the Minimal Change Set). Suggested owner: Implementer.

## Minimal Change Set
None — no further changes are required for approval.

## Approval Condition
None — approved as-is.
