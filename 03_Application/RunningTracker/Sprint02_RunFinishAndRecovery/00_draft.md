# RunningTracker Sprint 02 – Run Finish, Recovery & Recap (Ghost Runner Roadmap Sprint 1)

Product definition: `03_Application/RunningTracker/GhostRunner_Roadmap.md` §Sprint 1 (authoritative for scope and acceptance criteria). This draft maps it onto the existing code. Later roadmap sprints (cadence/audio, ghost identity/league, standalone) are **out of scope** and must not be pre-built.

## 1. Cross-layer note (R-OPS-BP-01)

Spans two layers, as RunningTracker Sprint01 did:
- `03_Application/RunningTracker` – schema (additive), metrics, native API, web history.
- `01_System/AtlasPhone` – run lifecycle, recovery screen, recap screen. Native API doc: `01_System/AtlasPhone/Sprint02_RunningScreen/RunningScreen_API.md` (update).

Numbering: RunningTracker Sprint02 = roadmap Sprint 1. No domain logic enters `02_Platform`. No new network exposure (native transport stays Tailscale, per prior decision).

## 2. Findings from inspection (current state)

- `RunLifecycle`: `RECORDING <-> PAUSED -> COMPLETED_LOCAL -> PENDING_UPLOAD -> SYNCED`; a single `FINISH` event. `RunController.finish()` stops everything in one call via `platform.stopAll()` (recorder + GPS + HR) and computes `RunSummary` over all samples.
- Capture buffer (`CaptureStore`) is one stream per run; samples carry timestamps (+ `elapsedRealtimeNanos`). A recovery phase can therefore be **a time boundary inside the same capture**, no second capture needed.
- Server `compute_metrics` takes all HR samples of the run (avg/max/hr_series) – recovery HR would pollute `avg_hr`/`max_hr`. `runs.finished_at` and `/finish` take one end time.
- Interrupted-run recovery (`interruptedRuns`/`recover`) only knows RECORDING/PAUSED.
- Existing runs have no recovery data and must stay valid.

## 3. Design decisions

**D1 – Recovery is a time boundary, not a second capture.** New persisted `runFinishedAtMillis` (end of running) on `RunMeta`; `finishedAtMillis` keeps meaning "training ended" (so old runs: `runFinishedAt == null` ⇒ no recovery, whole run is running). Everything after `runFinishedAt` in the HR stream is the recovery segment. Raw samples are untouched.

**D2 – New lifecycle state `RECOVERY`.** Events: `FINISH_RUN` (RECORDING|PAUSED → RECOVERY), `FINISH_TRAINING` (RECOVERY → COMPLETED_LOCAL). The old `FINISH` stays for a run without H10 (no HR → skip recovery: Finish Run offers "Finish" directly and goes `RECORDING|PAUSED → COMPLETED_LOCAL`), so existing paths and `RunLifecycleTest` keep passing. Open decision O1.

**D3 – Finish Run** (`RunController.finishRun()`): cancel GPS/ghost jobs, close open pause, `location.stop()` (not `stopAll`), keep recorder + HR + foreground service running, compute and persist the **final running `RunSummary`** and ghost ranking snapshot from samples ≤ `runFinishedAt`, persist `state = RECOVERY`. Distance/time/pace are frozen at this instant.

**D4 – Finish Training** (`finishTraining()`): `stopAll()`, compute `RecoverySummary` (§4), set `finishedAtMillis`, `COMPLETED_LOCAL → PENDING_UPLOAD`, enqueue upload (same path as today).

**D5 – Process death during RECOVERY.** `interruptedRuns()` includes `RECOVERY`; "Recover" resumes the recovery screen (HR reconnect best-effort) and "Finish Training" can close it; never auto-finalized (existing principle). Running summary is already persisted, so nothing about the run is lost.

**D6 – HR smoothing is display-only.** One pure function `HrSmoothing.smooth(samples, mode)` with `Raw | Rolling5s | Rolling10s` (default 5 s, user setting persisted locally). Time-windowed (not N-sample) mean of valid samples; windows with no valid sample yield **null (gap), never 0**. Artifact rule: bpm outside 30..230 or a jump > 40 bpm/s vs. neighbors is treated as missing for the *smoothed* series only; raw stays intact. Used by live cockpit/race screen graphs, recovery curve, recap.

**D7 – HRR computation** (pure, `RecoveryMetrics`, phone and server share the spec; server is authoritative like pace metrics). Anchor `t0 = runFinishedAt`. `HR_end` = median of valid HR in `[t0-3s, t0+2s]` (smoothing without delay: centered short window, not trailing). `HR_60`/`HR_120` = median of valid HR in `[t±3s]`. `HRR60 = HR_end − HR_60`, `HRR120 = HR_end − HR_120` (positive = drop). Each value is **null** when its window has <2 valid samples or training ended before t. Curve = smoothed series from t0 to training end. UI copy: HRR is the drop after exercise, not return to resting HR. Guidance text: "Recover the same way every time – standing or walking gently."

**D8 – Server side (additive).**
- `runs.run_finished_at timestamptz null` (+ check `>= started_at`, `<= finished_at`).
- `/runs/{id}/finish` request gains optional `run_finished_at`; absent ⇒ legacy behaviour (null).
- `compute_metrics(...)` gets `run_finished_at`; HR avg/max/`hr_series` and pace use only samples ≤ it; new `run_metrics.recovery jsonb null` (`{hr_end, hr_60, hr_120, hrr60, hrr120, curve}`), `ALGO_VERSION` bump so existing runs recompute on next finish-replay. Old runs: `recovery = null`.
- `runs.elapsed_s/moving_s/distance_m` already mean running totals; they now come from the Finish-Run summary.
- Query-behaviour rules (R-CON-AL-01/-06): time authority for all of the above is **phone-reported UTC domain time** (as in Sprint01); no server-clock use.

**D9 – Recap screen (phone)** replaces the current "Run finished" card. Built from persisted data only (works offline, with/without H10):
- Primary: distance, running time, avg pace, final position among ghosts (`n / N`), ghosts overtaken, selected rival beaten (yes/no + margin). Source: ghost ranking snapshot from D3.
- Secondary: HR profile (smoothed), avg/max HR (running phase only), HRR60/HRR120 when available, pace evolution, comparison to selected ghost.
- Achievements are only derived from real data: PR on this route (fastest trimmed finishing time among library runs), improved rank vs. previous run on the route. If not derivable → not shown. No animations beyond a single static emphasis; no pop-ups.
- Without H10 / no HR: HR and HRR blocks are omitted, not shown as zero.
- Ghost-overtaken count/rival result are computed locally from the cached library (offline), consistent with the existing ghost engine.

**D10 – Web history** (RunningTracker UI): show HRR60/HRR120 and the recovery curve on the run detail via the existing `Dataset` contract (additive columns/series; R-CON-BP-04). Minimal; no new pages.

## 4. Data model changes (all additive, nullable)

| Where | Change |
|---|---|
| `RunMeta` JSON | `runFinishedAtMillis`, `recovery` (nullable summary), `runSummary` semantics = running only; unknown keys already tolerated, missing keys default null |
| `RunState` | + `RECOVERY` |
| Settings (phone, local) | `hrSmoothing` = raw / 5s / 10s |
| `schema.sql` | `runs.run_finished_at`, `run_metrics.recovery` (idempotent `alter … add column if not exists`) |
| Native API | `finish` body: optional `run_finished_at` |

Migration: none destructive. Existing rows/metas read with nulls; their displays fall back to "no recovery recorded".

## 5. Implementation plan (suggested order, each step independently testable)

1. Pure logic + tests (no Android): `RunLifecycle` events, `HrSmoothing`, `RecoveryMetrics` (HRR), ranking-summary helper.
2. `RunMeta` persistence + migration tests (old JSON round-trips).
3. `RunController.finishRun/finishTraining/recover` + `interruptedRuns`; foreground service keeps HR alive; GPS stop.
4. Recovery screen + recap screen + smoothing setting (Compose).
5. Server: schema, `/finish` field, metrics clipping + `recovery`, tests; deploy with env files.
6. Web history additions.
7. Phone device test: run → Finish Run → recovery 2+ min → Finish Training → recap; also no-H10 run, kill during recovery, H10 disconnect during recovery.

## 6. Tests

- Unit (phone): lifecycle transitions incl. illegal ones; smoothing (gaps stay null, artifacts, window edges); HRR (normal, short recovery, sparse samples, no HR); old-`RunMeta` JSON decode; summary excludes recovery samples (avg HR, distance, pace).
- Unit (server): `compute_metrics` clips at `run_finished_at`; `recovery` values; legacy runs (null) unchanged; `/finish` idempotent replay.
- Device: lifecycle above; GPS stopped but HR continuing at recovery (verify no location samples after `runFinishedAt`).
- Proportionate per `feedback_risk_tolerance_testing`: no exhaustive matrix.

## 7. Decisions (resolved by user 2026-11-13, proposed defaults approved)

- **O1 RESOLVED** No-H10 runs skip recovery and finish directly (`FINISH`, RECORDING|PAUSED → COMPLETED_LOCAL).
- **O2 RESOLVED** Recovery ends only via Finish Training; a ~15 min reminder is shown; no auto-save.
- **O3 RESOLVED** Ghost ranking snapshot at Finish Run uses existing `FieldRanking` unchanged.

## 8. Out of scope

Cadence, metronome, live chart rework, ghost names/colors/league, virtual pacers, standalone packaging, workout integration, any AI processing.

## 9. Deliverable at close

Short completion report: implemented features, tests, limitations, deferred work (per roadmap delivery instruction 7). Stop at `TESTS_PASSING`.
