---
name: WorkoutTracker Sprint01 Pattern
description: Frontend-only UX fixes sprint for WorkoutTracker; IMPLEMENTATION_IN_PROGRESS; shell rebuild required before manual verification
type: project
---

Sprint01_ExerciseUX for WorkoutTracker is a pure frontend sprint (no backend, no schema changes).

Three changes all in `03_Application/WorkoutTracker/src/ShellEntry.tsx`:
1. Dropdown overflow fix: ExerciseRow and SessionList now use `position: fixed` dropdowns with `getBoundingClientRect()` instead of `position: absolute` (was clipped by `overflow: hidden` on the list container).
2. RepChip: new inline component rendering a colored delta pill on each ExerciseRow. Green/red/grey based on current vs previous total_reps. Placed between the name/weight block and the mini bar chart.
3. ExerciseView chart fix: liveRow now uses `row.workout_date` instead of the string "Today", and is spliced into filteredHistory at the correct chronological position rather than appended.

**Why:** The sprint has no automated test infrastructure (all scenarios are `[UI — manual]`). Test spec is present but no pytest or Playwright tests were written.

**How to apply:** Shell rebuild is required before any changes are visible:
```
cd /home/linse/Prod/Atlas/02_Platform/Atlas_Shell
npx vite build
docker cp dist/. atlas-shell:/usr/share/nginx/html/
```

State: IMPLEMENTATION_IN_PROGRESS — human must invoke `/sprint-close` after verifying the three fixes in the live UI.

First sprint for WorkoutTracker — no prior `00_architecture/` folder exists; design artifacts are in Sprint01_ExerciseUX only.
