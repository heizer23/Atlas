# Test Spec — RunningTracker — Sprint04_GhostCoach

## Scope
Server coach behavior (consent, payload allow-list, analysis with a FAKE provider, validation, profile, plans, outcome hook) with pytest in `atlas-runningtracker-test`, the deterministic phone coaching engine and plan/session logic with Kotlin JVM tests, and the web Coach UI with stubbed Playwright responses; the real provider, TTS audio, ducking, headphones, screen-off and a full device run are explicitly out of scope (listed as `[UI — manual]`, reported as untested). No test performs a network call; the test container has no API key.

Conventions: fixture objects are the `fix-` rows named in `10_scaffolding.json` (tests/fixtures.sql). `[Phone JVM]` scenarios are Kotlin unit tests, `[UI]` scenarios are Playwright with stubbed API, everything else is pytest.

## Scenarios — consent and egress

### AI is off by default
- **Given:** the seeded settings row
- **When:** the client reads the coach settings
- **Then:** ai_enabled is false, consent_current is false, key_configured reflects the test environment (false), and no consent timestamp is present.

### Enabling AI requires the current consent version
- **Given:** AI disabled
- **When:** the client enables AI without consent_version, then with an old version, then with the current version shown by the settings read
- **Then:** the first two are rejected with CONSENT_VERSION_MISMATCH (422) and leave the state unchanged; the third enables AI and records consent version and time.

### Disabling AI clears consent
- **Given:** AI enabled with consent recorded
- **When:** the client sets ai_enabled false
- **Then:** ai_enabled is false, consent version and time are cleared, and an analysis request is rejected CONSENT_REQUIRED.

### Goal text null versus omitted
- **Given:** a stored goal text
- **When:** the client patches only ai_enabled (goal omitted), then patches goal_text null, then patches goal_text with whitespace only, then with 501 characters
- **Then:** the goal survives the first patch, is cleared by null, whitespace is stored as cleared, and 501 characters is rejected 422.

### Preview shows exactly what would be sent
- **Given:** fix-run-coach-1 with history runs and a stored goal text, AI disabled
- **When:** the client requests the analysis preview, then runs an analysis with the fake provider
- **Then:** the preview is available without consent and makes no outbound call; the payload the fake provider received is byte-identical to the compact form of the previewed document and to the stored sent_payload of the analysis.

### Payload contains only allow-listed fields
- **Given:** fixtures whose titles, comments, categories and route names contain marker strings and whose runs have GPS samples
- **When:** the payload for fix-run-coach-1 is built
- **Then:** every key at every depth belongs to the declared allow-list, none of the marker strings, uuids, ISO timestamps or coordinate-like values appear anywhere in the serialized document, absolute dates are absent (only relative days and weekday), and missing values are null, never zero.

### Payload history is bounded
- **Given:** more complete runs than the history limit, some started after the analysed run
- **When:** the payload is built
- **Then:** only the latest allowed number of earlier runs are included, newest first, runs started after the analysed run are excluded, and an oversize document drops the oldest history runs first while the analysed run stays.

### Key never leaves the server side
- **Given:** a fake provider configuration with a recognisable key value
- **When:** settings, preview, analysis, error responses and the log output of an analysis are inspected
- **Then:** the key value appears in none of them and in no stored row; settings expose only key_configured.

### Host outside the allow-list is refused without a call
- **Given:** a configured URL whose host is not in the allow-list
- **When:** the user requests an analysis
- **Then:** the request fails AI_NOT_CONFIGURED 503, settings report key_configured false, no coach_ai_calls row is recorded, and the fake transport received no request.

## Scenarios — analysis

### Analysis happy path
- **Given:** AI enabled with current consent, configured fake provider returning a valid assessment, one allowed inferred profile update and a valid easy_continuous plan, and fix-run-coach-1 with at least three complete runs
- **When:** the user requests an analysis
- **Then:** an analysis is stored and returned with the assessment, the inferred profile row appears with a capped confidence, a recommended plan row exists and is linked as plan_id, the measured profile rows are refreshed, one ok call is recorded, and the response is a Dataset.

### Analysis is idempotent unless forced
- **Given:** an existing analysis for the run
- **When:** the user requests the analysis again without force, then with force
- **Then:** the first returns the stored analysis and the fake provider receives no request; the forced call contacts the provider once, updates the same analysis row, supersedes the earlier still-recommended plan and creates a new recommended plan.

### Analysis check order
- **Given:** an unknown run id; an uploading run; a complete run shorter than the minimum; AI disabled; AI enabled but key not configured; the daily cap reached
- **When:** the user requests an analysis in each situation
- **Then:** the results are NOT_FOUND 404, RUN_NOT_ANALYSABLE 409, RUN_NOT_ANALYSABLE 409, CONSENT_REQUIRED 403, AI_NOT_CONFIGURED 503 and RATE_LIMITED 429 respectively, and the fake provider received no request in any of them.

### Provider failure leaves no analysis
- **Given:** a fake provider that times out, returns HTTP 500, or returns a redirect
- **When:** the user requests an analysis
- **Then:** the result is AI_UNAVAILABLE 502, no analysis or plan row is created, one provider_error call is recorded, and a retry after the provider recovers succeeds.

### Invalid provider output is rejected
- **Given:** a fake provider returning non-JSON text, a JSON object with an extra top-level key, or an empty assessment
- **When:** the user requests an analysis
- **Then:** the result is AI_INVALID_RESPONSE 502, nothing is stored except one invalid_response call record.

### Invalid plan keeps the assessment
- **Given:** a provider response with a valid assessment and a plan whose heart-rate range exceeds the bounds
- **When:** the user requests an analysis
- **Then:** the analysis is stored with plan_rejected_reason plan_bounds, no plan row is created, and the response shows no plan_id.

### Interval plans stay occasional
- **Given:** one of the latest plans (fix-plan-interval) is an interval plan that was neither disregarded nor superseded
- **When:** the provider recommends another interval plan
- **Then:** the plan is rejected with plan_interval_frequency while the assessment is kept; after the earlier interval plan is disregarded the same recommendation is accepted.

### Inferred profile needs enough runs
- **Given:** a provider response with inferred updates (one valid, one unknown key, one confidence 0.99) and a history of fewer than three complete runs, then of ten runs
- **When:** the analysis runs in each case
- **Then:** with fewer than three runs no inferred row is stored; with ten runs only the valid key is stored, its confidence is capped by the run count, and the unknown key is dropped.

### Analysis read for the run detail
- **Given:** one run with and one run without an analysis
- **When:** the client reads the analysis of each
- **Then:** the first returns one row, the second returns an empty Dataset (total 0), and an unknown run returns NOT_FOUND 404.

## Scenarios — profile, plans, outcome

### Measured profile is deterministic and never zero-filled
- **Given:** fix-run-coach-1..4 (cadence on three of them) and then a window with no cadence at all
- **When:** the measured profile is computed
- **Then:** natural cadence, step length, HR at median pace, runs and kilometres per week, and the PRs have the expected values for the fixtures; with no cadence those rows are absent (not 0); hr_at_median_pace is absent with fewer than three qualifying runs; weekly windows use the runs' own dates, not the server clock.

### Profile read order
- **Given:** one measured and one inferred row
- **When:** the client reads the profile
- **Then:** the measured row is first, the inferred row carries a confidence and the measured row has none; an empty profile returns an empty Dataset.

### Next session selection
- **Given:** fix-plan-accepted (no run) and fix-plan-recommended
- **When:** the client reads next-session, then after the accepted plan is disregarded, then with no open plans
- **Then:** first the accepted plan, then the recommended plan, then an empty Dataset.

### Accept a plan unchanged
- **Given:** fix-plan-recommended
- **When:** the client patches status accepted without overrides
- **Then:** the plan becomes accepted with a decision time, its active_plan equals the recommendation, and any other accepted plan without a run becomes superseded.

### Modify with null versus omitted
- **Given:** a recommended hr_controlled-free plan with HR, pace and cadence targets
- **When:** the client accepts with overrides that set the cadence range, clear pace with null and omit hr
- **Then:** the active plan has the new cadence range on every steady/work segment, no pace target, the original HR range, and the stored recommendation (plan) is unchanged.

### Invalid overrides are rejected
- **Given:** a recommended plan
- **When:** the client accepts with a heart-rate range outside the bounds, then clears the heart-rate target on an hr_controlled plan
- **Then:** both fail PLAN_INVALID 422 and the plan stays recommended.

### Forbidden transitions
- **Given:** a disregarded plan, a completed plan, and an accepted plan that already has a linked run
- **When:** the client tries to accept the disregarded plan, disregard the completed plan, and modify the linked accepted plan
- **Then:** each fails INVALID_TRANSITION 409; an unknown plan id fails NOT_FOUND 404.

### Plan history list
- **Given:** plans in several statuses
- **When:** the client reads the plan list with default limit, limit 1, and limit 0 or 51
- **Then:** rows are newest first, limit 1 returns one row, and the out-of-range limits return 422.

### Phone fetches the active plan
- **Given:** an accepted plan without a run and a paired device token
- **When:** the phone requests next-plan with a valid token, with no token, and after the plan is disregarded
- **Then:** the first returns plan id, schema version and the active plan; the second is 401 DEVICE_UNAUTHORIZED; the third returns all-null; the public (Cloudflare-marked) request path is forbidden as for the other native routes.

### Finish links the plan and stores the outcome
- **Given:** an accepted plan and a run that finishes with that coach_plan_id and complete verified samples
- **When:** the finish call completes, and then the same finish is replayed
- **Then:** the plan is linked to the run and completed with an outcome (planned and done seconds, completed flag, in-range fractions that are null where the plan had no target), the measured profile is refreshed, the response is unchanged, and the replay leaves one linked plan and recomputes the same outcome.

### Finish ignores unknown or unusable plan ids
- **Given:** a finish with a malformed id, an unknown id, a disregarded plan's id, and a plan already linked to another run
- **When:** each finish is called
- **Then:** all return the normal complete response, no plan is linked or changed, and an old-format body without coach_plan_id still succeeds.

### Coach hook errors never break finish
- **Given:** a forced error inside the coach finish hook
- **When:** a run finishes
- **Then:** the finish response is the normal complete response and the error is only logged.

### Existing behavior unchanged without coaching
- **Given:** AI disabled and no plans
- **When:** runs are listed, a run detail is opened, a run finishes and a ghost profile is requested
- **Then:** responses and stored metrics are identical to the previous sprint.

## Scenarios — plan schema parity

### Plan schema golden cases agree on server and phone
- **Given:** tests/fixtures/coach_plan_golden.json
- **When:** the server validator and the phone parser process every case
- **Then:** valid plans are accepted by both, invalid plans are rejected by the server with the expected reason code, malformed plans are Invalid on the phone, and schema_version 2 is plan_schema on the server and Unsupported on the phone.

## Scenarios — live coaching engine [Phone JVM]

### [Phone JVM] Sustained deviation triggers one instruction
- **Given:** a steady segment with HR range 130-145 and a settled session
- **When:** HR is 155 for fewer than the sustain time, then continuously for the sustain time
- **Then:** nothing is said in the first case; exactly one 'heart rate above target' instruction is issued in the second; a reading inside the tolerance band never starts the timer.

### [Phone JVM] No instruction during settling or pause
- **Given:** a deviating reading at the very start of the session and right after a segment change, and a paused session
- **When:** ticks continue
- **Then:** no corrective instruction is issued before the settle time of the segment elapsed, and none while paused, muted or disabled; out-of-range timers restart after resume.

### [Phone JVM] One instruction at a time with priority
- **Given:** HR above range, pace too fast and cadence too low at the same time, all sustained
- **When:** ticks pass over several minutes at the normal frequency
- **Then:** at most one instruction per tick; heart-rate is spoken first, then pace, then cadence, each only after the global gap and its own cooldown.

### [Phone JVM] Conflicting instructions are suppressed
- **Given:** HR above range while pace is too slow and cadence is low, all sustained
- **When:** ticks pass
- **Then:** no instruction to speed up or raise cadence is issued while the heart rate is above range; after HR returns to range the pending push instruction can be issued.

### [Phone JVM] Gaps and cooldowns follow the frequency setting
- **Given:** the same persistent deviation under Low, Normal and High frequency
- **When:** a long sequence of ticks is run
- **Then:** the spacing between instructions is never below the gap of the chosen frequency, the same kind repeats no sooner than its cooldown, and a repeat needs the deviation to be sustained again.

### [Phone JVM] Segment announcements
- **Given:** an interval plan with warmup, work and recovery segments
- **When:** the clock passes each boundary
- **Then:** a segment-start instruction is issued on the first tick of every segment, a 'begins in 30 seconds' warning once before a long enough segment ends, the start announcement wins when both fall on one tick, and a plan-complete message is issued once at the end after which the engine stays silent; announcements respect the plan's trigger list.

### [Phone JVM] Recovery mid-plan does not replay announcements
- **Given:** an engine created for a plan at an active time inside the third segment
- **When:** the first ticks run
- **Then:** no start announcement is produced for the segments that already began.

### [Phone JVM] Missing or unreliable sensors
- **Given:** a segment with HR, pace and cadence targets
- **When:** HR is missing or older than the stale limit for longer than the sensor-lost time, pace is missing, or cadence is missing
- **Then:** a single sensor-lost notice per dimension is issued at most once per notice cooldown (HR and GPS only), no corrective instruction for the missing dimension is produced, missing cadence is silent, and nothing is ever computed from a zero reading.

### [Phone JVM] Keep-rhythm is rare
- **Given:** all evaluated dimensions in range
- **When:** a long in-range sequence runs
- **Then:** a keep-rhythm message appears only after the maintain time and the quiet time since the last instruction, then not again until the quiet time passes, and only if enabled by the plan.

### [Phone JVM] Engine is deterministic
- **Given:** the same plan, settings and input sequence
- **When:** the engine runs twice
- **Then:** the instruction sequences are identical, and the engine uses no clock other than the supplied active time.

### [Phone JVM] Metronome follows the plan cadence
- **Given:** a coach session whose current segment has a cadence range, and then a segment without one
- **When:** the metronome targets are computed in COACH mode with a ghost session present
- **Then:** the raw target is the range midpoint, then none; MATCH_GHOST and ATTACK_102 are not offered while the coach cadence target exists; COACH is never persisted; without a coach session the Sprint03 mode lists are unchanged.

### [Phone JVM] Coach failures never reach the run
- **Given:** a fake speech output that throws or reports unavailable, and an engine fed an input that raises
- **When:** ticks run through the controller
- **Then:** speech failure falls back to text only, an engine exception disables the coach session without propagating, and the recording state is untouched.

### [Phone JVM] Plan cache behavior offline
- **Given:** a cached plan and a refresh that fails, then a refresh returning no active plan
- **When:** the refresh runs
- **Then:** the failed refresh keeps the cached plan, the null plan clears the cache, and an unsupported schema version is reported as such and not coached.

### [Phone JVM] Plan link survives restart and upload
- **Given:** a run started with a cached plan
- **When:** RunMeta is serialized and decoded, and an old meta without the key is decoded, and finish is built
- **Then:** the plan id round-trips, old metas decode with no plan, and the finish body carries coach_plan_id only when a plan is linked.

## Scenarios — web UI

### [UI] Run detail shows the stored assessment
- **Given:** a run whose analysis exists (stubbed)
- **When:** the user opens the run detail page
- **Then:** the Coach card shows the assessment text and previous-recommendation effect as plain text, and no Analyse button is required.

### [UI] Analyse run with consent missing
- **Given:** a run without an analysis and a stubbed 403 CONSENT_REQUIRED on analysis
- **When:** the user presses Analyse run
- **Then:** the button is disabled while pending, the error message appears in the card, and a link to the Coach page is shown.

### [UI] Analyse run success
- **Given:** a stubbed successful analysis response
- **When:** the user presses Analyse run
- **Then:** the card shows the returned assessment and, if a plan was recommended, a pointer to the Coach page; a stubbed 502 shows the ApiError message and keeps the button usable.

### [UI] Consent flow on the Coach page
- **Given:** AI disabled, key configured (stubbed settings)
- **When:** the user opens the Coach page, reads the destination and data categories, opens the payload preview for a run, and switches AI on
- **Then:** the preview shows the payload JSON, the toggle sends the current consent version, the page shows AI enabled; with key not configured the toggle is disabled with an explanation.

### [UI] Accept, modify and disregard the next session
- **Given:** a stubbed recommended session
- **When:** the user presses Accept, or edits the cadence range and clears the pace fields before accepting, or presses Disregard
- **Then:** the accept request carries no overrides; the modify request carries the cadence object, null for cleared fields and omits untouched fields; Disregard sends status disregarded; the card reflects the returned status; with no session the page shows an empty state.

### [UI] Profile and history render
- **Given:** stubbed profile and plan history
- **When:** the user views the Coach page
- **Then:** measured rows are listed before inferred rows, inferred rows show their confidence, and the plan history lists status and outcome summary.

### [UI — manual] Phone coach card and offline plan
- **Given:** an accepted plan on the server and a paired phone
- **When:** the user opens the Run home panel online, then disables connectivity and reopens it
- **Then:** the card shows the plan, offline it still shows the cached plan with the offline note, and disregarding the plan on the web removes it after the next online refresh.

### [UI — manual] Coaching a real session
- **Given:** an accepted plan with HR and cadence targets, headphones, music playing, screen off
- **When:** the user starts the run with 'Coach this run' on and runs the session
- **Then:** instructions are audible through the headphones with brief ducking of the music, spacing and wording are acceptable, the coach strip and mute work, the metronome follows the plan cadence in COACH mode, recording and the race UI are unaffected, and TTS missing falls back to on-screen text; marked untested until performed on the device.

### [UI — manual] First complete lifecycle
- **Given:** AI enabled with a real key and model configured by the operator
- **When:** the user completes a run, presses Analyse run, accepts the recommended session, runs it with coaching, and analyses the next run
- **Then:** every lifecycle step of the draft's definition of done works end to end, the second analysis references the first plan's outcome, and the payload preview matches what the provider received; marked untested until performed.
