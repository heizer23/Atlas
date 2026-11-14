# Ghost Runner — Product Evolution Roadmap

Canonical product definition for the four Ghost Runner sprints. Each roadmap sprint is implemented as its own Atlas sprint folder; do not combine sprints.

**Numbering (R-OPS-BP-01):** Roadmap Sprint 1 = `RunningTracker/Sprint02_RunFinishAndRecovery` (RunningTracker Sprint01 already exists: RecordAndSync). Work spans `03_Application/RunningTracker` (backend, schema, web) and `01_System/AtlasPhone` (native runner). Roadmap Sprint 4 (standalone app) will conflict with the current Atlas/Tailscale coupling and must surface that explicitly when it starts.

| Roadmap sprint | Atlas sprint folder | Status |
|---|---|---|
| 1 Run Completion, Recovery & Analytics | `Sprint02_RunFinishAndRecovery` | TESTS_PASSING (device checks pending) |
| 2 Live Racing, Cadence & Audio Pacing | `Sprint03_CadenceAndLiveRacing` | draft written |
| 3 Ghost Identity, History & League | — | defined only |
| 4 First-Run Experience & Standalone Release | — | defined only |

---

## Product Vision

Ghost Runner is a standalone, local-first running application that turns running into a competition against the user's previous performances.

Its central experience is simple: **You are racing against your past selves.**

Historical runs become persistent competitors with their own identity, performance patterns, and history. Over time, the user builds a field of familiar opponents, learns their strengths and weaknesses, and progresses through a personal racing league.

The application should remain simple enough that a new user can enjoy running without configuring a training plan, creating an account, or learning complicated functionality.

## General Architectural Principles

- Preserve the existing Ghost Runner architecture: Android/TWA, native functionality where necessary, phone GPS, and Polar H10 heart-rate integration.
- Runs must work offline, including during temporary sensor or connectivity interruptions.
- Store raw sensor measurements wherever available. Derived statistics should be recalculable.
- Keep simulated data distinguishable from measured data.
- Maintain compatibility with historical runs.
- Avoid unnecessary AI or server processing when deterministic algorithms can achieve the same result.
- New functionality must not compromise the reliability of the existing running experience.

---

## Sprint 1 — Run Completion, Recovery & Analytics

### Objective

Transform the end of a run into a rewarding experience while improving the quality of the recorded and displayed statistics.

### 1. Separate Run and Training Completion

Introduce two distinct actions.

**Finish Run**
- Stop the running timer and distance accumulation.
- Finalize the running route, pace, distance, and ghost rankings.
- Stop GPS tracking once the run is finalized.
- Continue collecting heart-rate data from the Polar H10.
- Transition to the recovery screen.

**Finish Training**
- Stop heart-rate recording.
- Save the complete training session, including the recovery segment.
- Display the final recap.

Recovery is stored as a distinct phase, not included in the running averages.

### 2. Heart-Rate Recovery

Measure heart-rate recovery (HRR) after the run.

Display:
- Heart rate at the end of the run.
- Heart rate after 60 seconds.
- Heart rate after 120 seconds.
- HRR60: reduction from finishing HR after 60 seconds.
- HRR120: reduction after 120 seconds.
- Recovery heart-rate curve.

The recovery graph continues until Finish Training is pressed.

Use short smoothing around measurement points without introducing significant delay. Recovery values should be computed consistently and remain comparable between runs.

The user should receive guidance to recover consistently, preferably standing or walking gently in the same manner each time.

Do not treat HRR as equivalent to returning to resting heart rate.

### 3. Heart-Rate Smoothing

Keep the original heart-rate values.

Introduce configurable display smoothing:
- Raw
- 5-second rolling window (default)
- 10-second rolling window

Handle obvious sensor artifacts and missing samples appropriately.

Never interpret missing heart-rate measurements as zero.

The smoothed series should be used for visualization while original measurements remain available.

### 4. Post-Run Celebration

Create a dedicated recap screen with a clear hierarchy.

Primary results:
- Distance
- Running time
- Average pace
- Final position among historical ghosts
- Number of ghosts overtaken
- Whether the selected rival was defeated

Secondary results:
- Heart-rate profile
- Average and maximum heart rate
- HRR60 and HRR120, once available
- Pace evolution
- Comparison to the selected ghost

Highlight genuine achievements, such as personal records and improvements in ranking.

The recap should feel satisfying without excessive animation, gamification pop-ups, or clutter.

### Sprint 1 Acceptance Criteria

- Running stops while HR recording continues.
- Recovery is excluded from pace, distance, and running HR averages.
- HRR60 and HRR120 are calculated correctly.
- Existing historical runs remain accessible.
- Missing heart-rate data is handled gracefully.
- Raw measurements remain intact.
- Final recap works with and without a connected H10.

---

## Sprint 2 — Live Racing, Cadence & Audio Pacing

### Objective

Make Ghost Runner a more engaging live racing experience while giving runners useful control over their rhythm.

### 1. Step and Cadence Tracking

Use the Android step-detection capabilities available on the device.

Record step timestamps during running.

Calculate cadence in steps per minute (SPM).

The calculation should tolerate occasional missed steps. For example, if the normal interval is approximately 375 ms and one interval is 750 ms, this may indicate a missed detection rather than a sudden halving of cadence.

Use robust interval estimation and conservative correction rules.

Do not invent steps during genuine walking, stopping, or irregular movement.

Store the original step events and calculate a processed cadence series, including confidence information where useful.

Allow historical analysis to be recalculated as the algorithm improves.

### 2. Cadence Metronome

Introduce a very quiet click sound through the user's headphones.

Modes:
- **Off** — no cadence audio.
- **Match Ghost** — match the selected ghost's recorded cadence at the corresponding position along the route.
- **Attack +2%** — target approximately 102% of the selected ghost's cadence.

The 2% adjustment is a cadence increase, not a guaranteed 2% increase in running speed.

The cadence target should change smoothly rather than abruptly jumping when the ghost changes rhythm.

The user must be able to toggle modes quickly without navigating multiple screens.

Support operation with the screen off or when the TWA is not in the foreground, using the appropriate native Android facilities.

If an old ghost has no recorded cadence, display that limitation and offer a fallback such as a manually selected cadence. Do not invent historical cadence from speed.

### 3. Live Racing Chart

Keep the existing main map and portrait-oriented running layout.

Expand the lower visualization into two complementary sections.

**Left — Racing Performance**

Primary metric: time advantage or disadvantage against the selected ghost at the same route position.

Display:
- Current time difference.
- Direction of change: gaining or losing ground.
- Recent history of the time difference, approximately 1–2 minutes.
- Current rolling pace, initially using a 20-second window.
- Ghost's pace on the corresponding section.

The graph should make it immediately obvious whether the gap is closing.

Avoid plotting pace and time difference on a shared numerical axis.

**Right — Heart Rate**

Display:
- Current heart rate, smoothed over approximately 5 seconds.
- Heart-rate history.
- Selected ghost's historical heart rate, where available.
- Clear distinction between the user and ghost series.

Historical ghost heart rate must be aligned to the corresponding route position rather than blindly using the same elapsed time.

### 4. Ghost Racing Audio

The cadence metronome should be quiet, unobtrusive, and compatible with music or podcasts.

Avoid frequent voice announcements.

Audio timing should remain accurate even if the UI refresh rate drops.

### Sprint 2 Acceptance Criteria

- Real cadence can be recorded on supported devices.
- Missed steps do not cause unreasonable cadence spikes or drops.
- The metronome works reliably through headphones.
- Cadence audio continues appropriately with the screen off.
- Ghost-match mode is based on recorded cadence.
- Speed and time-difference displays remain readable while running.
- Live updates do not noticeably degrade GPS or heart-rate recording.

---

## Sprint 3 — Ghost Identity, History & League

### Objective

Turn anonymous historical runs into persistent competitors with meaningful history.

### 1. Persistent Ghost Identity

Each eligible historical run becomes a ghost with:
- Stable unique identifier.
- User-editable name.
- Original run date.
- Original completion time and route.
- Historical ranking information.
- Champion history.
- Associated visual color.

The ghost retains its identity permanently, even after dropping out of the active top 10 or top 20.

Names and identities must never be reassigned automatically.

### 2. Visual Identity

Introduce a restrained color system.

Hue represents the year the run occurred. For example: 2026 orange, 2027 blue, 2028 green.

Saturation represents historical distinction.
- Former champions: stronger saturation.
- Ordinary ghosts: muted saturation.
- Current champion: optional small crown or subtle additional indicator.

The selected rival must remain visually recognizable regardless of color.

Colors are primarily an atmospheric element conveying running history. They should not compete with essential running information.

### 3. Multiple Ghosts on the Map

Display multiple historical runners simultaneously.

Initially support a field of up to 10 historical ghosts, with a design capable of accommodating larger fields later.

Keep non-selected ghosts visually simple.

Only the selected rival receives the detailed gap comparison, pace comparison, and optional heart-rate comparison.

Performance and readability take priority over showing every available statistic.

### 4. All-Time Leaderboard

Maintain an all-time leaderboard for comparable runs on the same course.

Show: rank, ghost name, completion time, original date, former champion distinction.

Keep the full historical archive even if only a subset of ghosts is shown on the map.

Preserve the history of former record holders so that a ghost such as Alex can be identified as a previous champion even years after losing the title.

### 5. Personal Racing League

Introduce a challenge ladder separate from the all-time leaderboard.

The leaderboard measures historical achievement. The league measures the user's current progression.

Example:
- Current rival: #4
- Beat #4: challenge #3 next time.
- Beat #3: challenge #2.
- Eventually challenge #1.

After an extended break or a sustained decline in performance, the user should be able to move down the ladder and work back up.

Do not demote the user based on one bad run.

Use a simple recent-performance rule, potentially the last three comparable runs, with hysteresis to avoid constant movement between ranks.

Keep the league algorithm understandable and testable.

The chosen rival can be overridden manually.

### 6. Race Recap Integration

Include the names of defeated ghosts in the post-run recap. Examples:
- Overtook Alex.
- Beat Ben by 14 seconds.
- Advanced to challenge rank #3.

These messages must reflect actual recorded results.

### Sprint 3 Acceptance Criteria

- Ghost names persist after ranking changes.
- Year colors remain consistent.
- Former champions retain their distinction.
- Ghosts do not lose their underlying historical data when leaving the active field.
- Users can select a rival manually.
- League rank and all-time rank remain separate.
- Results and rival selection are consistent across app restarts.
- Comparisons are restricted to compatible routes and distances.

---

## Sprint 4 — First-Run Experience & Standalone Release

### Objective

Make Ghost Runner enjoyable immediately for someone who has no historical data and has never used Atlas.

### 1. Virtual First-Run Competitors

Provide three virtual pacers:

| Pacer | Pace | 3 km time |
|---|---|---|
| Fast | 6:00/km | 18:00 |
| Medium | 7:00/km | 21:00 |
| Easy | 8:00/km | 24:00 |

They should be identified as simulated runners, not actual historical performances.

The user should be able to compare their own progress against all three.

Important technical constraint: on an unknown first-run route, future GPS positions are unavailable. The application should therefore show virtual opponents using relative distance or progress, rather than pretending to know their exact position on an unseen route.

Once historical routes exist, normal map-based ghost comparisons can take over.

### 2. Simulated Heart Rates

Virtual runners may have illustrative heart-rate curves.

These can use age-based maximum-heart-rate estimates as one input, but they must not be presented as healthy targets or personalized physiological predictions.

Simulated heart-rate values must be clearly distinguishable from real recordings.

### 3. Transition to Real Ghosts

The first completed run establishes the user's first real ghost.

On the second run, they can race their previous performance.

As more real runs accumulate, virtual competitors become less prominent and can disappear from the active field.

The user must always be able to access previous real performances.

### 4. Standalone Android App

Prepare Ghost Runner as an independent Android application.

Requirements:
- No dependency on installing the Atlas launcher or unrelated Atlas modules.
- No mandatory account registration.
- Local storage of running and sensor data.
- Appropriate Android permissions and explanations.
- Compatibility with the existing supported heart-rate sensors.
- Data export and backup options.
- Reliable operation when the display is off or the app is backgrounded.
- Recovery from interrupted recording sessions.

Avoid adding workout/strength-training functionality during this release. It remains a potential future extension.

### 5. Release Quality

Test the complete running lifecycle: Start → Run → Race → Finish Run → Recovery → Finish Training → Recap.

Include cases involving:
- GPS drift or signal loss.
- Bluetooth heart-rate disconnection.
- Missing step events.
- Interrupted and resumed sessions.
- Background operation.
- Low battery.
- App process termination.
- Existing-data migration.
- Runs with no ghost or no HR sensor.

A public release must not lose or corrupt a run when one sensor fails.

### Sprint 4 Acceptance Criteria

- A first-time user can start running without setup beyond necessary permissions.
- Virtual opponents work without historical data.
- A second run can compete with the first.
- All critical operations work without Atlas.
- Offline recording and local persistence are reliable.
- Failures are communicated clearly without generating misleading statistics.

---

## Delivery Instructions (apply to every sprint)

Before implementation of each sprint:

1. Inspect the existing repository, architecture, and tests.
2. Identify reusable components and existing functionality.
3. Propose an implementation plan and data-model changes.
4. Keep changes limited to the current sprint.
5. Add unit tests and relevant Android/device-level integration tests.
6. Preserve historical data and provide migrations when necessary.
7. Produce a short completion report with implemented features, tests, limitations, and deferred work.

Do not combine all four sprints into one development task.

## Explicitly Out of Scope for Now

- Online multiplayer.
- Social leaderboards.
- Cloud synchronization.
- Subscription systems.
- Personalized AI coaching.
- Complete workout/strength-training integration.
- Complex animations, character avatars, or fictional ghost personalities.

**Guiding principle:** Make running feel like a race, but keep the application simpler than the game it creates.
