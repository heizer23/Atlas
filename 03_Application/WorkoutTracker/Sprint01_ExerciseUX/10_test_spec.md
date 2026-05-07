# Test Spec — WorkoutTracker — Sprint01_ExerciseUX

## Scope
UI behavioral correctness of the three exercise UX fixes in ShellEntry.tsx: dropdown overflow fix, rep-progress chip rendering, and chronological chart insertion. No backend or API contract testing. All scenarios are UI-level; automated Playwright infrastructure is not yet set up for WorkoutTracker.

## Scenarios

### [UI — manual] Dropdown not clipped for last exercise row
- **Given:** A session is open with at least two exercises; the last exercise row is at or near the bottom of the ExerciseList container
- **When:** The user taps the three-dots menu button on the last exercise row
- **Then:** The dropdown (Edit / Delete) is fully visible and both items are reachable without scrolling; the dropdown is not clipped by the list container boundary

### [UI — manual] Dropdown not clipped for last session row
- **Given:** The sessions list contains at least two sessions; the last session row is at or near the bottom of the SessionList container
- **When:** The user taps the three-dots menu button on the last session row
- **Then:** The dropdown (Copy / Delete) is fully visible and both items are reachable; the dropdown is not clipped by the list container boundary

### [UI — manual] Rep-progress chip green — current reps exceed previous
- **Given:** An exercise row where the current session's total_reps is greater than the most recent prior session's total_reps for that exercise
- **When:** The exercises list for that session is displayed
- **Then:** A green pill chip appears between the exercise name and the mini bar chart, showing a positive numeric delta (e.g. "+8")

### [UI — manual] Rep-progress chip red — current reps below previous
- **Given:** An exercise row where the current session's total_reps is less than the most recent prior session's total_reps for that exercise
- **When:** The exercises list for that session is displayed
- **Then:** A red pill chip appears, showing a negative numeric delta (e.g. "−3")

### [UI — manual] Rep-progress chip grey — no prior history or equal reps
- **Given:** An exercise row where either no prior history exists for that exercise, or the prior session's total_reps equals the current session's total_reps
- **When:** The exercises list for that session is displayed
- **Then:** A grey outline pill appears showing "—" with no fill color

### [UI — manual] ExerciseView chart places active bar at correct historical date
- **Given:** The user opens an exercise from a past session (not today); the history chart has multiple data points
- **When:** ExerciseView renders the full-size history chart
- **Then:** The active bar (full opacity) appears at the column corresponding to the actual workout_date of that session, not at a separate "Today" column appended at the far right

### [UI — manual] ExerciseView chart correct position when no edits made
- **Given:** The user opens an exercise from a past session and has not modified any rep values
- **When:** ExerciseView renders the full-size history chart
- **Then:** The liveRow (active bar) still appears at the correct chronological position using the stored rep values from the row, not appended at the end
