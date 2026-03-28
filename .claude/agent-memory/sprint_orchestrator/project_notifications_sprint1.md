---
name: Notifications Sprint1 Pattern
description: First Platform-layer Notifications sprint; defines a two-agent (Atlas Claude / Android Claude) delivery split with FCM payload as the explicit boundary artifact
type: project
---

Sprint1_MVP for Workouttracker under 02_Platform/Notifications is the first sprint in this component.

Key structural facts:
- Layer: 02_Platform (Platform layer) — designer must be sprint_design_platform, not sprint_design_application
- Two coordinated delivery agents: Atlas Claude (server-side, up to FCM dispatch) and Android Claude (Android shell, after FCM receipt)
- The FCM payload contract + deep-link handling spec is the explicit boundary artifact that must be produced before implementation splits
- No sprint_conventions.md exists at the Notifications root — canonical R-PRO-BP-01 process applies in full
- Sprint folder name uses a space ("Sprint1_MVP for Workouttracker") — deviates from canonical `Sprint<N>_<Title>` (no spaces); do not flag as a violation since folder already exists

**Why:** The Notifications platform is being introduced to support WorkoutTracker's rest timer feature. The architecture is server-FCM-Android, requiring explicit handoff coordination between two separate implementation agents.

**How to apply:** When routing this sprint, always use sprint_design_platform (not application). Ensure design artifacts explicitly define the FCM payload contract as a named boundary artifact, not just a prose note. Flag to specs reviewer that scheduling mechanism must be resolved in design_specs.md.
