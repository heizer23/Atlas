# Design Corrections — notifications

## Applied Changes

1. **cancel() idempotent behavior for already-cancelled records**
   - Review Source: `design_review.md` Minimal Change Set item 1 and item 2 (Confirmed Problem 1, Major)
   - Files Updated: `20_design/architecture.json`
   - Change: Two locations updated.
     - `interfaces.provides` exposed_surfaces DELETE /api/notifications/{id} `description` (internal_flow step 3): added "If status=cancelled, returns 200 with no state change (idempotent — cancel is a no-op for all terminal states)" alongside the existing dispatched no-op branch.
     - `interfaces.provides` python_api NotificationService.cancel `purpose`: added "no-op (return success) for already-cancelled — cancel is idempotent for all terminal states" alongside the existing dispatched no-op clause.

2. **Timing contract worst-case stated explicitly in contracts.provides**
   - Review Source: `design_review.md` Minimal Change Set item 3 (Confirmed Problem 2, Minor)
   - Files Updated: `20_design/architecture.json`
   - Change: `contracts.provides` fourth item amended from "Maximum expected dispatch latency of ~5 seconds from fire_at under normal load (polling interval is 5 seconds; average latency is ~2.5 seconds)" to "Maximum expected dispatch latency of ~5 seconds from fire_at (one full polling interval); average ~2.5 seconds. The draft acceptance criterion of 2 seconds is expected-case, not worst-case." The claim is now self-contained and does not require the reader to cross-reference the risks section.

## Unchanged by Design

All sections of `architecture.json` and `scaffolding.json` not listed above were preserved verbatim. `scaffolding.json` and `20_Data/schema.sql` (absent pre-implementation) were not modified — neither was referenced by the Minimal Change Set.

## Review Alignment Check

- Minimal Change Set Applied: Yes
- Approval Condition Satisfied: Yes — `architecture.json` now declares explicit behavior for `cancel()` on an already-cancelled record (idempotent no-op returning success).
- Notes: The Minimal Change Set listed three items. Items 1 and 2 both address the same cancel() gap (python_api purpose and internal_flow step description respectively) — both were applied. Item 3 is the timing claim correction. No Recommended Improvements beyond the Minimal Change Set were applied. The Scaffold-Only Observations and Open Uncertainties from the review were not modified; they require no artifact change.
