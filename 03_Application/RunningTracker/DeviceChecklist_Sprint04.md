# Device Checklist — Ghost Coach V1 (Sprint04)

Covers the three `[UI — manual]` scenarios in `Sprint04_GhostCoach/10_test_spec.md` plus the 13 phone JVM tests the runner could not execute. Record results in Notes; failures go back to the sprint as fix items.

**Prep**
- JVM tests first (no device): `cd 01_System/AtlasPhone && JAVA_HOME=~/toolchain/jdk17 ANDROID_HOME=~/toolchain/android-sdk bash ./gradlew :app:testDebugUnitTest` — expect all green (implementer reported 167). Record the count here: ______
- Build + install APK: `... bash ./gradlew :app:assembleDebug`. Server and web are already deployed.
- Phone paired, Tailscale up, Polar H10 charged, headphones, a music app.
- Real provider (needed for Run 3 only): put `RUNNINGTRACKER_COACH_API_KEY` in `01_System/secrets.env` and `RUNNINGTRACKER_COACH_MODEL` in `config.env` by hand, then recreate the container with `--env-file 01_System/secrets.env --env-file 01_System/config.env`. Never add the key to the test container. Only `api.anthropic.com` is allowed.
- At least 2–3 finished runs with HR in history (the profile needs data; the analysis is cautious with few runs).

## Part 1 — Plan on the phone, online/offline (≈5 min, no run)
Accept a plan on the web Coach page first (needs a plan; use a recommendation from an earlier analysis, or run Part 3 steps 1–4 first).

| # | Check | Expected | OK | Notes |
|---|-------|----------|----|-------|
| 1.1 | Open Run home panel online | Coach card shows plan title, duration, targets, "Saved on this phone…" | ☐ | |
| 1.2 | Airplane mode, force-close app, reopen | Card still shows the cached plan with the offline note | ☐ | |
| 1.3 | Online again; disregard the plan on the web; tap Refresh plan | Card shows "No plan accepted…" | ☐ | |
| 1.4 | Accept a plan again, Refresh | Plan returns | ☐ | |
| 1.5 | Frequency Low / Normal / High | Selection persists after app restart | ☐ | |
| 1.6 | "Coach this run" toggle | Persists after restart | ☐ | |

## Part 2 — Coached session (≈20–30 min outdoor run, ghost run optional)
Plan with HR range + cadence target (ideally a few segments: warm-up, steady/work, recovery, cool-down). Headphones in, music playing, H10 on, "Coach this run" on, Frequency Normal. Screen locked most of the run.

| # | Check | Expected | OK | Notes |
|---|-------|----------|----|-------|
| 2.1 | Start run | Coach strip appears showing current segment; race UI/map unchanged; start not delayed | ☐ | |
| 2.2 | First instructions | Spoken through headphones; music briefly ducks then returns (not paused) | ☐ | |
| 2.3 | Wording & spacing | Understandable, not nagging; never two conflicting instructions; no bursts (Normal) | ☐ | |
| 2.4 | Run too fast / HR above target on purpose | Pace / HR instruction after tolerance + cooldown, not instantly; not repeated every few seconds | ☐ | |
| 2.5 | Hold target | "Maintain" style message at most occasionally | ☐ | |
| 2.6 | Segment change (e.g. recovery) | Advance notice ahead of the boundary, then the boundary announcement; strip segment updates | ☐ | |
| 2.7 | Metronome | Mode chip offers Off / Coach / Manual (no ghost modes); Coach clicks at plan cadence; target follows segment changes | ☐ | |
| 2.8 | Ghost running (if raced) | Coaching takes priority; no ghost-gap speech | ☐ | |
| 2.9 | Mute / Unmute on strip | Speech stops immediately, text may continue; unmute resumes without a backlog of stale messages | ☐ | |
| 2.10 | Frequency High vs Low (switch before next run or mid-run) | Noticeably more / fewer instructions | ☐ | |
| 2.11 | H10 off ~30 s | At most one sensor notice, not repeated every few seconds; no HR-based instructions while HR is missing; recording continues | ☐ | |
| 2.12 | Airplane mode for the whole run | Coaching works fully offline; recording unaffected | ☐ | |
| 2.13 | Screen off, backgrounded, several min | Instructions keep coming; click keeps tempo; GPS+HR+steps still arrive | ☐ | |
| 2.14 | TTS unavailable (disable TTS engine in Android settings, short run) | Card/strip say "Voice unavailable, text only"; text instructions still show; no crash | ☐ | |
| 2.15 | Finish Run → Finish Training | Normal recovery/recap flow unchanged; run syncs | ☐ | |
| 2.16 | Web run detail after sync | Run linked to the plan; plan outcome stored (plan history on Coach page) | ☐ | |
| 2.17 | "Coach this run" off, short run | No speech, no strip, no Coach metronome mode; run identical to pre-coach behavior | ☐ | |

## Part 3 — Full lifecycle with real provider (needs key)
| # | Check | Expected | OK | Notes |
|---|-------|----------|----|-------|
| 3.1 | Coach page: AI off by default | Off, consent not given | ☐ | |
| 3.2 | Enable AI | Requires consent (current version); preview of what is sent is shown | ☐ | |
| 3.3 | Complete a run (or use a recent one), press **Analyse run** | Assessment appears on run detail; no raw GPS / identifying data in the preview | ☐ | |
| 3.4 | Payload preview vs provider | Preview matches what was sent (check server log/stored request; key never visible in responses, logs or rows) | ☐ | |
| 3.5 | Profile | Measured values vs inferred (with confidence) clearly distinguished; nothing zero-filled | ☐ | |
| 3.6 | Next recommended session | Sensible, sustainable (not an interval session every time) | ☐ | |
| 3.7 | Accept (also try Modify and Disregard on another) | State transitions work; modified values validated | ☐ | |
| 3.8 | Run it with coaching (Part 2) | Works as above | ☐ | |
| 3.9 | Analyse the next run | Assessment references the previous plan's outcome | ☐ | |
| 3.10 | Disable AI / remove key | Run, history, accepted plans and phone coaching keep working; analysis reports AI not configured/disabled gracefully | ☐ | |
| 3.11 | Rate limit | Max 10 attempts / 24 h respected (optional) | ☐ | |

## Wrap-up
- Failures / observations: 
- Then: mark `Sprint04_GhostCoach/99_sprint_log.md` device checks done (or open fix items).
