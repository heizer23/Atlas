# RunningTracker Sprint 04 – Ghost Coach V1: Adaptive Personal Running Coach

## 0. Conflicts to resolve before design (R-OPS-BP-01 / R-OPS-BP-02)

1. **Roadmap scope conflict.** `GhostRunner_Roadmap.md` lists "Personalized AI coaching" under *Explicitly Out of Scope for Now*. This sprint reverses that decision. Roadmap must be updated (move to a new section) once the user confirms.
2. **Numbering.** Roadmap Sprint 4 (First-Run Experience & Standalone Release) is not yet built; it is not `Sprint04_*` in the folder scheme. This sprint takes folder `Sprint04_GhostCoach`; roadmap Sprint 4 will become Sprint05+ and must be reconciled with the standalone goal (the external AI call and "offline during runs" stay compatible; the Atlas/Tailscale coupling note still applies).
3. **New external exposure (security).** Sending training data to an external AI provider is the first outbound data flow of RunningTracker. Requirements: explicit opt-in consent, off by default, API key stored server-side only (never on phone), minimal payload (no raw GPS tracks unless needed; prefer aggregated/derived data), no new inbound ports. Design must state exactly what leaves the system.
4. **Layer split.** AI orchestration, profile, plans, outcomes → `03_Application/RunningTracker`. Live coaching engine, audio, metronome integration → `01_System/AtlasPhone`. No domain logic in `02_Platform`.

## 0a. V1 scope (trimmed, authoritative over §1 where they differ)

The lifecycle in §12 is the goal; everything not needed for it is deferred. §1 is kept as the long-term product definition.

**In V1**
- Post-run AI analysis (§4): comparison with recent runs, pace vs HR, cadence, fatigue/drift, effectiveness of the previous recommendation. Concise assessment stored per run.
- Athlete profile (§3), reduced: aerobic/HR-at-pace, natural cadence, average step length, training frequency/volume, PRs, trends, preferences. Each value tagged measured vs inferred, with confidence. No per-gradient modelling.
- Training plans (§5), reduced types: easy continuous, HR-controlled, recovery, endurance, interval. Fields: distance/duration, HR range, pace range, cadence range, warm-up/cool-down, interval/recovery segments, coaching triggers. Accept / modify / disregard.
- Local deterministic coaching engine (§8) in AtlasPhone: smoothed measurements vs plan, tolerances, cooldowns, one instruction at a time, missing-sensor handling, mute/disable, configurable frequency, audio via headphones + existing metronome, coaching beats ghost competition.
- Technical requirements (§11) in full: versioned plan schema, versioned configurable prompt, validation of AI output, local storage of accepted plans, recommendation/outcome history, explicit consent, graceful operation without AI.
- UX (§10) minimal: next recommended session, post-run assessment, unobtrusive live coaching. Race UI unchanged.

**Deferred (not built, no schema/stubs beyond what the plan schema's `version` field allows)**
- Route intelligence and terrain-anticipating instructions (§6).
- Running economy experiments (§7) and the "personal record attempt" plan type.
- Personalized challenges (§9).
- Optional athlete development overview screen; per-gradient profile; optional step-length targets in plans.

## 1. Source definition (verbatim from user, 2026-11-15)

### 1. Product vision

Ghost Runner evolves from a competitive running application into an intelligent, personalized training companion.

Two complementary systems operate simultaneously:

- Ghost Runner: Compete against previous performances.
- Ghost Coach: Improve long-term running performance through personalized training recommendations and live guidance.

The objective is sustainable fitness, running efficiency, enjoyment and continuous improvement—not professional athletic performance.

### 2. Architecture

Separate coaching intelligence from real-time execution.

AI coaching engine

- Performs post-run analysis.
- Maintains a persistent athlete profile.
- Develops training strategies.
- Generates structured training plans.
- Identifies upcoming personal challenges.

Local running application

- Receives structured training parameters.
- Monitors live sensor data against targets.
- Provides visual and acoustic feedback.
- Operates entirely offline during runs.

No real-time AI inference or API connection should be required during training.

### 3. Persistent athlete profile

Maintain an evolving profile based on historical training data:

- Aerobic endurance
- Running efficiency
- Heart rate at comparable speeds
- Natural cadence
- Average step length
- Performance on different gradients
- Fatigue and cardiac drift
- Training frequency and volume
- Personal records
- Development trends
- Training preferences and objectives

Distinguish measured values from inferred characteristics. Maintain confidence levels for inferred information.

Avoid drawing strong conclusions from individual runs.

### 4. Post-run AI analysis

After each completed run, make relevant historical and current training data available to the AI.

Analyse:

- Performance compared with previous runs
- Pace relative to heart rate
- Cadence and step-length relationships
- Route-specific performance
- Signs of fatigue
- Progress toward training goals
- Effectiveness of previous coaching recommendations

Generate a concise, personalized post-run assessment and update the athlete profile.

### 5. Adaptive training plans

The AI should generate structured, machine-readable recommendations for upcoming sessions.

Supported training types:

- Easy continuous run
- Heart-rate-controlled run
- Recovery run
- Running economy experiment
- Endurance run
- Interval training
- Personal record attempt

Training plans should support:

- Target distance and duration
- Target heart-rate range
- Target pace range
- Target cadence range
- Optional step-length guidance
- Route-specific targets
- Interval and recovery segments
- Warm-up and cool-down phases
- Coaching message triggers

The user must be able to accept, modify or disregard recommendations.

Prioritize sustainable progression and enjoyable running. High-intensity sessions should be occasional and purposeful.

### 6. Route intelligence

Build reusable route profiles from historical runs and available elevation data.

Identify recurring route characteristics:

- Uphill and downhill segments
- Typical pace changes
- Typical heart-rate responses
- Physically demanding sections
- Opportunities for recovery

Allow coaching instructions to anticipate upcoming terrain rather than merely reacting to current measurements.

Example:

"Uphill section approaching in 100 metres. Shorten your steps and reduce your pace slightly."

Distinguish measured terrain from inferred route characteristics.

### 7. Running economy experiments

Allow the AI to design small experiments embedded within normal training sessions.

For example, compare slightly different cadences at comparable speeds and gradients.

Use repeated observations to estimate which cadence and step-length combinations appear most efficient for the individual athlete.

Calculate average step length from speed and cadence. Recognize that pace, cadence and step length are interdependent rather than independent targets.

Account for delayed heart-rate responses, fatigue and environmental influences.

Avoid prescribing a universal optimal cadence or claiming biomechanical improvements that cannot be measured.

### 8. Real-time coaching engine

Implement a lightweight, deterministic local coaching engine.

Compare smoothed live measurements against the active training plan and trigger feedback where appropriate.

Example instructions:

- "Reduce your pace slightly."
- "Increase cadence by three steps per minute."
- "Maintain this rhythm."
- "Your heart rate is above target."
- "Recovery interval begins in 30 seconds."
- "Uphill section approaching."

Requirements:

- Acoustic feedback through headphones
- Integration with the existing cadence metronome
- Configurable coaching frequency
- Tolerance ranges and notification cooldowns
- Handling of missing or unreliable sensor data
- Ability to mute or disable coaching
- Training objectives take priority over competitive ghost performance

Avoid excessive notifications and conflicting instructions.

### 9. Personalized challenges

Maintain awareness of longer routes, personal records and previous achievements.

Identify opportunities when historical performance suggests the athlete may be ready for a meaningful challenge.

Example:

"Your aerobic performance has improved over the last eight runs. You may be ready for another Alster run. Based on comparable sessions, a new personal best appears achievable."

Consider estimated duration, training readiness, recovery and the user's available time.

Challenges should feel like occasional meaningful events rather than daily obligations.

### 10. User experience

Ghost Coach and Ghost Runner must remain simultaneously available.

Introduce:

- Next recommended training session
- Post-run coaching assessment
- Upcoming personal challenges
- Optional athlete development overview
- Unobtrusive live coaching integration

Preserve the existing race-focused running interface. Coaching should complement it without introducing unnecessary visual complexity.

### 11. Technical requirements

- Versioned training-plan schema
- Persistent athlete profile
- Versioned and configurable AI coaching prompt
- Validation of AI-generated parameters
- Local storage of accepted training plans
- Historical coaching recommendations and outcomes
- Explicit consent for sending training data to an external AI provider
- Graceful operation without AI availability

Reuse existing Ghost Runner infrastructure wherever possible.

### 12. Definition of done

The first complete coaching lifecycle works end to end:

1. The athlete completes a run.
2. The AI analyses the performance and relevant history.
3. The athlete profile is updated.
4. The AI recommends the next training session.
5. The athlete accepts the recommendation.
6. The application provides offline coaching during that session.
7. The results inform subsequent recommendations.

Advanced physiological modelling and highly accurate performance predictions are not prerequisites for V1.
