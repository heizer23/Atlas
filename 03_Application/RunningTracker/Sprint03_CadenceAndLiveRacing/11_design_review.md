# Design Review — RunningTracker — Sprint03_CadenceAndLiveRacing

**Verdict:** APPROVED
**Date:** 2026-11-14
**Reviewer:** sprint_design_reviewer

## Blocking Issues

_(None)_

## Non-Blocking Issues

| # | Location | Observation |
|---|----------|-------------|
| 1 | JSON validity (`10_architecture.json`, `10_scaffolding.json`) | No shell or validator was available to this reviewer, so neither file was run through a parser. Both were read in full. Brackets and braces balance, embedded quotes are escaped (e.g. `\"step\": 0`, `\"location.sample\"`, the manifest XML string), and the final array elements carry no trailing comma. A multiline regex search for `,` followed by `]` or `}` found no matches. No syntax defect was found, but this is inspection, not a parse. The implementer should run `python -m json.tool` on both files before starting. |
| 2 | `10_scaffolding.json` files[] (`models.py`, `AtlasClient.kt`, `RunningScreen_API.md` roles) vs `10_architecture.json` invariant C2 | The scaffolding calls the deploy-order rule "C1". The architecture names it C2. The authoritative behavior is the same in both: server first, and omit `expected_counts.step` when 0. Prose cross-reference only. |
| 3 | `10_scaffolding.json` `ClickConfig.DEFAULT_VOLUME` and `MetronomeConfig.DEFAULT_VOLUME` | The same constant is declared in two objects, both 0.2. The architecture's declare-once reviewer item implies one home. The implementer should reference one from the other. |
| 4 | `10_scaffolding.json` `LiveHistory.kt` role vs signature | The role text says `record()` gains optional `racePace` and `ghostProfile` arguments. The signature lists only `ghostProfile`. Race pace arrives through `LiveMetrics.racePaceSPerKm`, so the signature is authoritative and no code ambiguity results. |
| 5 | `10_architecture.json` REL1 / `10_scaffolding.json` `StepDetector.samples` | The overflow policy of the buffered step flow is unspecified. A full buffer silently drops steps, which would only lower cadence confidence and never affect GPS/HR. Acceptable as is. The implementer should use a non-suspending emit and note the choice. |
| 6 | `10_test_spec.md` "Two missed steps in a row are not corrected" | The expected outcome ("absent or keep the previous value according to the golden expectation") is deferred to a golden file that does not exist yet. CAD1 resolves it: an interval of about 3×M exceeds `CAD_GAP_FACTOR`×M, so it is a GAP and the window clears. The implementer should write the golden vector to match CAD1 and make the scenario assert the GAP outcome. |
| 7 | `10_schema.sql` vs `schema.sql:85` | Confirmed that the runtime schema still has the unnamed inline stream check, which Postgres auto-names `run_samples_stream_check`. The drop-then-add-named-constraint block therefore converges on both fresh and existing databases. The first startup scans `run_samples` once, as noted in the risks. |

## Approval Condition

None — approved as-is.
