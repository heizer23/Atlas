# Device Checklist — Run Finish/Recovery (Sprint02) + Cadence/Metronome (Sprint03)

Covers every `[UI — manual]` scenario from both sprints. Source: `Sprint02_RunFinishAndRecovery/10_test_spec.md`, `Sprint03_CadenceAndLiveRacing/10_test_spec.md`. Record results in the Notes column; failures go back to the sprint as fix items before `/sprint-close`.

**Prep**
- Build + install the APK (`JAVA_HOME=~/toolchain/jdk17 ANDROID_HOME=~/toolchain/android-sdk bash ./gradlew :app:assembleDebug` in `01_System/AtlasPhone`). Server is already deployed.
- Phone paired, Tailscale up, Polar H10 charged, wired/Bluetooth headphones, a music app.
- A ghost recorded **before** Sprint03 (no cadence) and one recorded after step capture works (Run A below creates it).
- Grant `ACTIVITY_RECOGNITION` when prompted (denial is tested separately in Run D).

## Run A — main outdoor run (~25 min run + 3 min recovery) — covers most items
Free-run or ghost race, H10 on, headphones in, music playing, metronome Match Ghost (new ghost) → switch to Attack midway. Screen locked for most of it.

| # | Check | Expected | OK | Notes |
|---|-------|----------|----|-------|
| A1 | Step permission prompt at first use | Prompt appears once; run starts without delay | ☐ | |
| A2 | Click through headphones | Very quiet click; 30 s stopwatch count matches displayed target | ☐ | |
| A3 | Match Ghost follows ghost cadence | No sudden jumps when ghost rhythm changes | ☐ | |
| A4 | Attack +2% | Target and click ≈ 1.02× ghost at same position | ☐ | |
| A5 | Screen off, app backgrounded, music playing, several min | Click keeps tempo; music not paused/ducked; GPS+HR+steps keep arriving | ☐ | |
| A6 | Mode chip taps | Cycles Off → Match → Attack → Manual (free run: no ghost modes) | ☐ | |
| A7 | Notification action, screen off | Mode changes; label follows mode; persists to next run | ☐ | |
| A8 | Race screen layout (≥3 min) | Map unchanged; left = gap + gaining/losing arrow + 1–2 min gap history + 20 s pace vs ghost pace; right = HR + ghost HR; gap never on pace axis; unknown = dash | ☐ | |
| A9 | Smoothing setting Raw / 5 s / 10 s | Live HR, recovery graph, recap HR chart follow it; stored data and HRR unchanged | ☐ | |
| A10 | Finish Run → confirm | Timer/distance/GPS freeze; **click stops immediately**; recovery screen with smoothed HR, time since run end, growing graph | ☐ | |
| A11 | Recovery milestones | HR60 / HR120 tiles fill at ~60 s / ~120 s; guidance text visible; nothing auto-saves | ☐ | |
| A12 | H10 off 30 s then back (during recovery) | Graph gap (no zero); connection state + Reconnect visible; Finish Training still works; missing HRR = dash | ☐ | |
| A13 | Finish Training (after ≥2 min) | Recap: primary (distance, time, pace, n/N, overtaken, rival) larger than secondary (HR profile, avg/max HR, HRR60/120, pace evolution, ghost comparison); no pop-ups/animation; real achievements only | ☐ | |
| A14 | Airplane mode on recap | Content unchanged; sync status + retry shown; sync after reconnect | ☐ | |
| A15 | After sync, in Atlas web | Run has running-only distance/time/pace/avg HR; avg cadence + cadence chart; step samples in sample counts; no location sample after run end; HR continues to training end | ☐ | |
| A16 | Sample health vs. a comparable older run | GPS/HR rates and gaps indistinguishable; click steady while display busy | ☐ | |
| A17 | No steps recorded after Finish Run | Step count stops at run end | ☐ | |

## Run B — headphone route change (2 min, any run)
| # | Check | Expected | OK | Notes |
|---|-------|----------|----|-------|
| B1 | Disconnect then reconnect Bluetooth headphones with metronome on | Observe: click moves to speaker / stops / resumes? **Write result here — recorded as known limitation (no speaker guard)** | ☐ | |

## Run C — old ghost, no cadence (short run)
| # | Check | Expected | OK | Notes |
|---|-------|----------|----|-------|
| C1 | Race pre-Sprint03 ghost, select Match Ghost | Chip says no cadence recorded; nothing clicks | ☐ | |
| C2 | "Use manual cadence" | Manual fixed cadence (default 170, adjustable) clicks; nothing derived from speed | ☐ | |

## Run D — permission denied (short run)
| # | Check | Expected | OK | Notes |
|---|-------|----------|----|-------|
| D1 | Clear app permission, deny `ACTIVITY_RECOGNITION` at prompt | Run starts without delay; GPS + HR record | ☐ | |
| D2 | Home panel | States cadence is not recorded; no re-prompt without an explicit tap | ☐ | |
| D3 | Atlas run detail | Cadence dash, "No cadence recorded." | ☐ | |

## Run E — no H10 (short run)
| # | Check | Expected | OK | Notes |
|---|-------|----------|----|-------|
| E1 | Finish without HR reading | No recovery phase; recap without HR/HRR blocks (omitted, not zero); syncs normally | ☐ | |
| E2 | Metronome after plain Finish and after Discard | Silent | ☐ | |

## Run F — kill during recovery (needs an H10 run; can be Run A's sibling)
| # | Check | Expected | OK | Notes |
|---|-------|----------|----|-------|
| F1 | On recovery screen, kill the app, reopen Running Screen | Offered Recover or Discard; never auto-finalized | ☐ | |
| F2 | Recover | Recovery screen resumes, running result intact, HR reconnecting | ☐ | |

## Open questions to answer while testing
- Do steps and the click survive screen-off in the existing `location|connectedDevice` foreground service (A5)? If not, the service type needs changing.
- Are batched steps delivered if the sensor is unregistered at pause (note any missing steps after a pause)?

## After the checklist
Fix anything that failed, then run `/sprint-close` for Sprint02 and Sprint03.
