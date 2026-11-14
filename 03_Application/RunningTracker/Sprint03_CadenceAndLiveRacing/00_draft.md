# RunningTracker Sprint 03 – Cadence, Metronome & Live Racing (Ghost Runner Roadmap Sprint 2)

Product definition: `03_Application/RunningTracker/GhostRunner_Roadmap.md` §Sprint 2 (authoritative for scope and acceptance criteria). This draft maps it onto the existing code. Roadmap Sprints 3-4 (ghost identity/league, standalone) are **out of scope** and must not be pre-built.

## 1. Cross-layer note (R-OPS-BP-01)

Spans two layers, as Sprint01/02 did:
- `03_Application/RunningTracker` – schema (additive), cadence metrics, ghost cadence, native API, web history.
- `01_System/AtlasPhone` – step capture, metronome audio, race-screen chart. Native API doc `01_System/AtlasPhone/Sprint02_RunningScreen/RunningScreen_API.md` (update).

Numbering: RunningTracker Sprint03 = roadmap Sprint 2. No domain logic enters `02_Platform`. No new network exposure (transport stays Tailscale). Security (R-OPS-BP-02): one new runtime permission (`ACTIVITY_RECOGNITION`), requested at first use only; no new ports, no new endpoints beyond additive fields.

## 2. Findings from inspection (current state)

- No step/cadence code exists anywhere (phone or backend). Sample streams are `location` and `heart_rate` (schema check constraint, `models.py` Literal, `verification.py`, `fit_import.py`).
- Much of roadmap §3 already exists from the ghost-race redesign (66b6656): `GapTrend` (gaining/losing arrow), rolling pace, `paceSeries`, `hrSeries`, `ghostHrSeries` aligned by route position (`hrByProgress`, 20 m buckets, `LiveInsights.kt`/`LiveHistory.kt`/`GhostRaceScreen.kt`). **The implementer must audit these against §3 and build only the delta** (expected: 1-2 min gap-history graph, explicit 20 s rolling pace, ghost section pace, left/right layout).
- Foreground service type is `location|connectedDevice`; recorder + GPS + HR already survive screen-off. Step listening and audio can live in the same service.
- Ghost HR-by-position is computed server-side in `ghost.py` from moving-time-mapped samples; cadence-by-position can reuse that mapping.
- Server recomputes metrics from stored samples (`ALGO_VERSION`, finish-replay), so cadence derived data is recalculable.

## 3. Design decisions

**D1 – Raw steps are a new sample stream `step`.** One sample per detected step: `{timestamp, sequence}` (+ optional sensor event time). Source: Android `TYPE_STEP_DETECTOR` (per-step events, hardware-batched, works with screen off); no sensor / permission denied ⇒ no step stream, run unaffected. Additive: schema check constraint extended, `Literal` extended, verification/upload counts include `step`, old clients/runs unaffected (no `step` rows ⇒ no cadence). Steps outside RECORDING (paused, recovery) are not recorded. Raw events are never modified by processing.

**D2 – Cadence estimator is one pure function** `CadenceEstimator` (phone + server share the spec; shared golden fixture `tests/fixtures/cadence_golden.json`, as for pace/recovery; server authoritative). Input: step timestamps (+ optional pause intervals). Output: cadence series at ~1 Hz `(t, spm, confidence)` and run average.
- Robust interval estimate: median of the last N valid intervals (N≈8); plausible range 100-230 spm for running intervals.
- Missed-step rule (conservative): an interval within ±15% of 2× the running median, whose neighbours are normal, counts as 2 steps (cadence unchanged, confidence reduced). Never for 3+× multiples.
- No invention: intervals > ~2.5× median or > 2 s are a stop/walk/irregular gap ⇒ cadence null for that span (gap, never 0); no steps are synthesised in raw storage, correction affects only the processed series.
- Confidence 0..1 from interval variance and fraction of corrected intervals.
- Algorithm version stored with the result; recalculation = rerun on raw steps.

**D3 – Server side (additive).** `run_metrics.cadence jsonb null` (`{avg_spm, series:[{t,spm,conf}], algo}`), computed in `compute_metrics` from `step` rows (running phase only, ≤ `run_finished_at`); `ALGO_VERSION` bump so old runs recompute harmlessly (no steps ⇒ null). Ghost payload gains nullable `cadence_by_progress` (20 m buckets) next to the HR one. Old ghosts / no steps ⇒ null, **never derived from speed**. Time authority: phone-reported UTC domain time (as Sprint01).

**D4 – Metronome (native, in the existing foreground service).** Streaming `AudioTrack` with a pre-rendered short, very quiet click; beat scheduling by **sample count** (fractional accumulation), not timers, so timing is independent of UI refresh and Doze. Target spm handed to the audio thread as an atomic value.
- Modes: `OFF | MATCH_GHOST | ATTACK_102`. Target = ghost cadence at the user's current route position (×1.02 for attack).
- Smooth targets: ghost cadence low-pass/slew-limited (≤ ~1 spm/s change) so a rhythm change in the ghost never jumps the click.
- No ghost cadence (old ghost / no steps): UI states "no cadence recorded for this ghost" and offers a manual fixed cadence (default last used, adjustable, persisted locally). No fallback from speed.
- Audio coexistence: no audio-focus request (mixes with music/podcast, never pauses them); low gain default with a volume setting; stops on Finish Run (or at recovery start).
- Quick toggle: one-tap mode cycle on the race screen **and** a notification action (screen off / TWA in background).

**D5 – Live racing chart.** Keep map + portrait layout. Lower area split left/right per roadmap §3: left = time gap (current, gaining/losing, 1-2 min history graph) + rolling 20 s pace + ghost section pace, **gap and pace never share an axis**; right = HR (5 s smoothed via existing `HrSmoothing`) with ghost HR by route position, user/ghost visually distinct. Display only; derived from data the engine already has.

**D6 – Web history (minimal).** Run detail shows avg cadence and a cadence series via the existing `Dataset` contract (additive; R-CON-BP-04). No new pages.

**D7 – Reliability guard.** Step listener, metronome and chart updates must not delay GPS/HR recording: sensor callbacks only enqueue to the capture buffer; audio runs on its own thread; chart recompute stays off the recording path. Add a simple guard: a drop in chart refresh must not affect click timing.

## 4. Data model changes (all additive, nullable)

| Where | Change |
|---|---|
| `schema.sql` | `step` allowed in the samples stream check; `run_metrics.cadence jsonb` (idempotent `alter ... add column if not exists`) |
| Native API | sample stream `step`; ghost payload `cadence_by_progress` |
| `RunMeta` / capture | step stream persisted like HR; no new state |
| Settings (phone, local) | metronome mode, manual cadence, click volume |
| Manifest | `ACTIVITY_RECOGNITION` |

Existing runs/ghosts remain valid and show "no cadence recorded".

## 5. Implementation plan (each step independently testable)

1. Pure logic + tests (no Android): `CadenceEstimator` + golden fixture (normal, missed step, stop, walk, irregular, sparse), ghost-cadence lookup + smoothing/slew function, target-mode function.
2. Server: schema, `step` stream ingest/verification, `compute_metrics.cadence`, ghost `cadence_by_progress`, tests; deploy with env files.
3. Phone capture: step sensor + permission flow, `step` stream in `CaptureStore`/upload.
4. Metronome engine (AudioTrack, sample-accurate) + service wiring + notification action.
5. Race screen: audit existing chart, build delta, mode toggle, no-cadence fallback UI.
6. Web history additions.
7. Device test: real run with headphones, screen off, music playing, ghost with/without cadence, permission denied, no-H10 run, GPS/HR continuity.

## 6. Tests

- Unit (phone + server) against the shared cadence golden: missed-step correction, no invention across stops/walks, gaps null not 0, recalculation determinism, old runs without steps.
- Unit: target smoothing never jumps > slew limit; attack = 1.02× ghost; no-ghost-cadence ⇒ manual fallback, never speed-derived.
- Server: `step` ingest/verification counts, clipped at `run_finished_at`, additive compatibility with old clients.
- Web: Playwright run detail with and without cadence (stubbed API).
- Device (manual, reported as untested until run): click accuracy vs. phone's own step cadence, screen-off, music mixing, headphone route change, permission denial.
- Proportionate per `feedback_risk_tolerance_testing`: no exhaustive matrix.

## 7. Proposed defaults (change before design if you disagree)

- **O1** Raw step stream = one sample per step (simple, ~10k/h; revisit batching only if upload size hurts).
- **O2** No audio-focus request (mixes with music; accepts that a navigation/voice prompt may overlap the click).
- **O3** Slew limit ~1 spm/s; default click gain very low; manual fallback cadence default 170 spm until the user changes it.
- **O4** Metronome stops at Finish Run (not during recovery).
- **O5** Notification action included for mode toggle.

## 8. Out of scope

Ghost names/colors/league, virtual pacers, standalone packaging, workout integration, voice announcements, any AI processing, backfilling cadence for old runs.

## 9. Deliverable at close

Short completion report: implemented features, tests, limitations (esp. untested device items), deferred work. Stop at `TESTS_PASSING`.
