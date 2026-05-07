# Sprint01_ExerciseUX — WorkoutTracker

## Summary
Three focused UI improvements to the exercise list and detail views. No schema changes, no new endpoints.

---

## Item 1 — Bug: Delete option clipped for last exercise

### Problem
When opening the three-dots menu on the last exercise row in a session, the dropdown popup (Edit / Delete) extends below the container boundary and is clipped. The "Delete" item is unreachable.

### Root cause
`ExerciseList` wrapper div has `overflow: hidden` (required for `borderRadius: 12` corner clipping). The dropdown is `position: absolute` relative to the button container, so it overflows the `ExerciseList` div and is masked.

### Fix
Use `position: fixed` for the dropdown. On open, read the button's viewport coordinates with `getBoundingClientRect()` and position the dropdown using those coordinates. This makes the dropdown a viewport-level overlay that is unaffected by any ancestor's `overflow`.

Implementation notes:
- Add a `useRef` on the three-dots button inside `ExerciseRow`.
- On toggle, store `{ top, right }` from `buttonRef.current.getBoundingClientRect()` in state.
- Render the dropdown with `position: fixed`, `top: buttonRect.bottom + 4`, `right: window.innerWidth - buttonRect.right`.
- The existing click-outside handler in `ExerciseList` remains unchanged.
- Apply the same fix to the `SessionList` dropdown (same pattern, same problem).

---

## Item 2 — Feature: Rep-progress indicator on exercise rows

### Description
In the exercise list for a session (the `exercises` inner view), each exercise row should show a compact colored chip indicating whether this session's total reps are better, worse, or the same as the previous session for that exercise.

- **Green** chip: current `total_reps` > previous `total_reps`
- **Red** chip: current `total_reps` < previous `total_reps`
- **Grey** chip (outline only, no fill): current `total_reps` == previous `total_reps`, or no prior history exists for this exercise

### Where it renders
Inside `ExerciseRow`, between the exercise name/weight block and the mini bar chart. It is a small pill showing the delta value: e.g. `+8`, `-3`, `=` (or just a colored dot/rectangle if delta is not shown).

Preferred layout: colored rectangle (pill), 36–44 px wide, 20 px tall, showing the numeric delta with a `+`/`−` prefix. Grey with no prefix (`—`) when no prior data.

### Data source
`historyByExercise[exerciseName]` is already loaded. The previous value is the last row in `history.rows` whose `id !== row.id`. `total_reps` for a history row = `set1_reps + set2_reps + set3_reps + set4_reps + set5_reps` (sum null-safe). The current row's `row.total_reps` is already computed by the backend.

### Colors
- Green: `var(--atlas-chart-3)` (already used in charts) with white/on-primary text, or use a semantic success token if available.
- Red: `var(--md-sys-color-error)` with `var(--md-sys-color-on-error)` text.
- Grey/neutral: `var(--md-sys-color-outline-variant)` border, transparent fill, `var(--md-sys-color-on-surface-variant)` text.

---

## Item 3 — Feature: Historical chart column at correct date position

### Problem
When opening an exercise from a past session (not today), `ExerciseView` appends a `liveRow` with `workout_date: "Today"` at the far right of the history chart. This is misleading — it appears as a separate future column rather than the actual historical data point for that session.

### Fix
- Replace `workout_date: "Today"` in `liveRow` with the actual `row.workout_date`.
- Instead of always appending `liveRow` at the end of `data`, insert it at the correct chronological position (after the last row whose `workout_date <= row.workout_date`, or in sorted order).
- The existing `_active: true` flag and `fillOpacity` logic (active bars at full opacity, others at 0.38) already handles the visual distinction — no color changes needed.
- Since `filteredHistory` already excludes the current row, re-inserting the liveRow at the correct sorted position is a simple splice or sort on `workout_date`.

Implementation: after constructing `filteredHistory.rows` (without current row), find the insertion index by comparing `workout_date` strings (ISO format sorts lexicographically). Insert `liveRow` at that index. Pass this merged array as `data` instead of appending.

Note: when `completed.some(c => c)` is false (user hasn't edited anything), still show the liveRow at the correct position using the stored rep values from `row`.
