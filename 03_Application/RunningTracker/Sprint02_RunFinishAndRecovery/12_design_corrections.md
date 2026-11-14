# Design Corrections — RunningTracker — Sprint02_RunFinishAndRecovery

## Applied Changes
1. **Test spec PR wording follows ST1 (Non-Blocking item 1)**
   - Review Source: `11_design_review.md` Non-Blocking Issues #1, Approval Condition
   - Files Updated: `10_test_spec.md`
   - Change: In scenario "[Phone JVM] Final standing and achievements from real data only", "personal record is true only when the completed run is strictly fastest of a non-empty field" now reads: true only when the run is completed, the field is non-empty and the position is 1 (ties favor the runner, so a tie with the fastest ghost still gives a personal record, per ST1).
2. **Standing carried over from persisted RunMeta.recap.standing (item 2)**
   - Review Source: `11_design_review.md` Non-Blocking Issues #2, Approval Condition
   - Files Updated: `10_architecture.json` (internal_flow steps 12 and 14)
   - Change: Step 12 description and step 14 description now state that Finish Training and the recovered path carry standing over from the persisted `RunMeta.recap.standing` and never call `GhostSession.finalStanding`. `RunMeta.recap.standing` added to step 12 inputs. `startedAtMillis` removed from step 14 inputs.
3. **Step 17 recovery input is the unclipped HR list (item 3)**
   - Review Source: `11_design_review.md` Non-Blocking Issues #3, Approval Condition
   - Files Updated: `10_architecture.json` (internal_flow step 17)
   - Change: Wording now says RS2 clipping applies to the stored run HR values, and `compute_recovery` receives the unclipped list of all HR samples, never the clipped list.

## Unchanged by Design
- All other sections of `10_architecture.json`, `10_test_spec.md`, `10_scaffolding.json` and `10_schema.sql` were preserved verbatim. No signature, schema field, or persisted shape was altered. Non-required items 4 to 9 were not applied.

## Review Alignment Check
- Required Changes Applied: Yes
- Approval Condition Satisfied: Yes
- Review Verdict: APPROVED_WITH_CHANGES
- Every listed item confirmed applied: Yes
- Notes: `10_scaffolding.json` needed no edit; the `RecapBuilder.build` signature there already omits `startedAtMillis`. JSON validity was not machine-checked (no shell); edits were string-only within existing values, and the review recommends `python3 -m json.tool` before implementation.
