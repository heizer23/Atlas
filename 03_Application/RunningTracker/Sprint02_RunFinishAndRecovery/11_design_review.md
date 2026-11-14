# Design Review — RunningTracker — Sprint02_RunFinishAndRecovery

**Verdict:** APPROVED_WITH_CHANGES
**Date:** 2026-11-13
**Reviewer:** sprint_design_reviewer

Review basis: delta-only artifacts (no `00_architecture` baseline, as intended). Cross-layer with `01_System/AtlasPhone` was checked against the actual code. Verified present and matching the design: `FinishRequest` `extra="forbid"` (`backend/models.py`), the `finish()` flow in `backend/routers/native.py`, `compute_metrics`/`recompute_and_store` in `backend/metrics.py`, `ALGO_VERSION` usages (`tests/test_metrics.py:91`, `tests/test_native_sync.py:225`), the runtime `schema.sql` (matches the `10_schema.sql` seed), `RunLifecycle.kt`, `RunController.finish/recover/interruptedRuns`, `FieldRanking.ranks`, `GhostComparison.progressNow/compare`, `GhostConfig.BACK_TOLERANCE_M`, `A1.LIVE_HR_STALE_MS`, `LocationTracker.stop()`, `HeartRateMonitor.reconnect()`, and `AtlasClient.finish(runId, meta, ...)`, which already receives `RunMeta`.

JSON check: no shell was available to the reviewer, so no JSON parser was run. A structural lint was done instead with multiline grep over both `10_*.json` files. It found no trailing commas, no missing commas between adjacent lines, and no tabs or non-ASCII characters, and a full read found balanced brackets and no unescaped quotes. Both files are very likely valid. Run `python3 -m json.tool` on each before implementation to confirm.

## Blocking Issues

_(None)_

## Non-Blocking Issues

Items marked **(required)** are non-behavioral wording or cross-reference fixes that must be applied by the corrector (see Approval Condition). The rest are observations.

| # | Location | Observation |
|---|----------|-------------|
| 1 **(required)** | `10_test_spec.md` scenario "[Phone JVM] Final standing and achievements from real data only" vs `10_architecture.json` invariant ST1 | The spec says personal record is true only when the run is "strictly fastest", and lists a "tie with a ghost" case. ST1 says "ties favor the runner" (position counts only strictly faster ghosts) and `personalRecord = routeCompleted && fieldSize >= 1 && position == 1`, so a tie gives PR = true. Fix the spec wording to follow ST1, which is authoritative (R-CON-BP-09). Durations are doubles, so a tie is practically unreachable. |
| 2 **(required)** | `10_architecture.json` internal_flow steps 12, 14 and 15 | Step 14 takes `standing` "from GhostSession.finalStanding" and is also called at Finish Training. Step 15 (Recover after process death) rebuilds no `GhostSession`, and step 12 does not list `RunMeta.recap.standing` as an input. Read literally, a killed-and-recovered run would lose its standing at Finish Training. ST1 ("persisted in RunMeta.recap.standing") and the "[UI — manual] Kill during recovery" scenario ("running result intact") make the intended reading clear. State in steps 12 and 14 that Finish Training and the recovered path carry `standing` over from the persisted `RunMeta.recap.standing` and never call `finalStanding`. Also remove `startedAtMillis` from step 14's inputs; the authoritative `RecapBuilder.build` signature in `10_scaffolding.json` does not take it. |
| 3 **(required)** | `10_architecture.json` internal_flow step 17 | "apply RS2 clipping, then compute_recovery(heart_rates, ...)" can be read as passing the clipped HR list, which would make every recovery value null. HRR1 and `backend/recovery.py` in the scaffold are unambiguous: `compute_recovery` receives all unclipped HR samples. Word step 17 to say the recovery input is the unclipped list. |
| 4 | `10_test_spec.md` scenario "Run without heart rate has an empty recovery" | The title says "empty" but the body (correctly, per the architecture `/recovery` query) expects one row with null HR/HRR values and a recovery duration. Rename the scenario so it is not read as the empty-Dataset case. |
| 5 | `10_architecture.json` ST1 and `FinishStanding` | `previousRunRank` is persisted, but no rule says when an "improved rank" achievement is shown (roadmap §4 and draft D9 mention it). `position` is among N+1 while `previousRunRank` is among N, so the implementer will have to invent the comparison. Also `rivalBeaten` for the incomplete route uses `leadM > 0`, but `leadM` is nullable and the null case is undefined. `myT` is the last matched fix, so lingering near the finish before pressing Finish Run inflates `myT`. This stays conservative (never a false PR), consistent with OQ1. Resolve in the implementer notes or a later sprint. |
| 6 | `10_architecture.json` L1 vs `10_scaffolding.json` `RecoveryScreen` | L1 says RECOVERY ends via FINISH_TRAINING "or an explicit Discard", but RecoveryScreen has no Discard control. Discard is reachable only from the interrupted-run banner after a kill and Recover. Intended or not, this is a UX gap rather than a contract error. |
| 7 | `10_scaffolding.json` `RecoveryTracker`, HR1 | The tracker is seeded only from `t0 - 3 s`, so the live HR1 spike check lacks the previous neighbor at the seed edge, and the newest live sample is never treated as a spike. Live tiles can differ slightly from the value recomputed from all samples at Finish Training. The persisted value is authoritative, so no change is needed. |
| 8 | `10_architecture.json` risks (RunMeta.recap size) | "tens of KB per hour" is low for 1 s buckets (about 3.6k points per hour, plus recovery). `run_meta` is also rewritten whenever `RunMeta` changes, including the upload cursor. Still bounded and acceptable; correct the figure when convenient. |
| 9 | Layering / dev ref (R-OPS-BP-01) | Domain logic (HRR, ST1, recap) lands in `01_System/AtlasPhone`. The draft §1 surfaces this and it follows the Sprint01 precedent; nothing domain-specific enters `02_Platform`. `.claude/supportDocs/atlas_dev_ref.md` has no RunningTracker or AtlasPhone entry (OQ4), so dependency checks were made against the repository code, as the design did. No new network exposure. New read endpoints are Dataset-based and match the existing public read pattern. The native tailnet route is unchanged. The `.tsx` change has `[UI]` scenarios. |

## Approval Condition

The corrector applies the three required non-behavioral wording changes (items 1, 2 and 3 above) to `10_test_spec.md` and `10_architecture.json`, and `12_design_corrections.md` confirms each was applied without altering any signature, schema field, or persisted shape.
