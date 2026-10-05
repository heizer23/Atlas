# Test Spec — HabitTracker — Sprint01_Core

## Scope

Backend API behavior for habit definitions (CRUD + reorder), the daily review day-model
(defaults/merging, frozen confirmed display, draft-save idempotency), and the reporting
grid/stats endpoint, including Europe/Berlin time-authority correctness. Out of scope:
any automatic data source, notifications, or visual/styling correctness.

## Scenarios

### Habit list — starter seed present on first run
- **Given:** a freshly started HabitTracker instance with no prior habits.
- **When:** `GET /api/habittracker/habits` is called.
- **Then:** exactly five habits are returned, ordered by `display_order`, matching the
  starter set (Worked out / No sweets / No vaping / Measured blood pressure / Reviewed
  EssayCards), all `default_checked: false`.

### Habit list — seeding is a one-time, table-emptiness check
- **Given:** the starter seed has already run once and one starter habit (fixture
  `fix-habit-worked-out`) has since been renamed by the user.
- **When:** the application restarts and `seed_starter_habits()` runs again.
- **Then:** no additional habits are inserted — the habit count is unchanged and the
  renamed habit keeps its new name.

### Create habit — success
- **Given:** no habit named "Read 10 pages" exists yet.
- **When:** `POST /api/habittracker/habits` is called with `{name: "Read 10 pages",
  default_checked: false, active_from: "2026-10-01"}`.
- **Then:** the response is HTTP 201 with the created habit, `display_order` set to one
  past the current maximum, server-assigned (not client-supplied).

### Create habit — missing name is rejected
- **Given:** a valid `active_from` and no `name` field.
- **When:** `POST /api/habittracker/habits` is called.
- **Then:** the response is an ApiError with code `VALIDATION_ERROR`, and no row is
  written.

### Update habit — partial update leaves other fields unchanged
- **Given:** the fixture habit `fix-habit-no-sweets` with `description: null`.
- **When:** `PATCH /api/habittracker/habits/{fix-habit-no-sweets}` is called with only
  `{default_checked: true}`.
- **Then:** the response is HTTP 200 with `default_checked: true`, and `name`,
  `description`, `active_from` are unchanged from before the call.

### Update habit — explicit null clears description
- **Given:** the fixture habit `fix-habit-no-sweets` with a non-null `description`.
- **When:** `PATCH /api/habittracker/habits/{fix-habit-no-sweets}` is called with
  `{description: null}`.
- **Then:** the response's `description` is `null`.

### Update habit — omitting description leaves it unchanged
- **Given:** the fixture habit `fix-habit-no-sweets` with a non-null `description`.
- **When:** `PATCH /api/habittracker/habits/{fix-habit-no-sweets}` is called with a body
  that does not include the `description` key at all.
- **Then:** the response's `description` is unchanged from before the call.

### Update habit — explicit null on name is rejected
- **Given:** the fixture habit `fix-habit-no-sweets`.
- **When:** `PATCH /api/habittracker/habits/{fix-habit-no-sweets}` is called with
  `{name: null}`.
- **Then:** the response is an ApiError with code `VALIDATION_ERROR`, and the habit's
  name is unchanged.

### Update habit — archiving via end_date
- **Given:** the fixture habit `fix-habit-no-vaping` with `end_date: null`.
- **When:** `PATCH /api/habittracker/habits/{fix-habit-no-vaping}` is called with
  `{end_date: "2026-10-15"}`.
- **Then:** the response's `end_date` is `"2026-10-15"`, and the habit is not deleted.

### Update habit — un-archiving by explicit null
- **Given:** the fixture habit `fix-habit-archived` with `end_date: "2026-09-01"`.
- **When:** `PATCH /api/habittracker/habits/{fix-habit-archived}` is called with
  `{end_date: null}`.
- **Then:** the response's `end_date` is `null`.

### Update habit — end_date before active_from is rejected
- **Given:** the fixture habit `fix-habit-no-vaping` with `active_from: "2026-01-01"`.
- **When:** `PATCH /api/habittracker/habits/{fix-habit-no-vaping}` is called with
  `{end_date: "2025-12-31"}`.
- **Then:** the response is an ApiError with code `VALIDATION_ERROR`, and the habit's
  `end_date` is unchanged.

### Update habit — unknown id
- **Given:** no habit exists with the given id.
- **When:** `PATCH /api/habittracker/habits/{unknown_id}` is called with any body.
- **Then:** the response is an ApiError with code `NOT_FOUND`.

### Reorder habits — full permutation including a swap
- **Given:** the five starter habits at `display_order` 0-4.
- **When:** `POST /api/habittracker/habits/reorder` is called with their ids in fully
  reversed order.
- **Then:** the response is HTTP 200, and a subsequent `GET /habits` returns them in the
  new reversed order with no duplicate or missing `display_order` values.

### Reorder habits — mismatched id set is rejected
- **Given:** the five starter habits exist.
- **When:** `POST /api/habittracker/habits/reorder` is called with only four of their
  ids.
- **Then:** the response is an ApiError with code `VALIDATION_ERROR`, and no
  `display_order` values are changed.

### Daily review — unreviewed day uses current defaults
- **Given:** the fixture habit `fix-habit-worked-out` with `default_checked: false`, and
  no daily review has ever been saved for `2026-10-05`.
- **When:** `GET /api/habittracker/reviews/2026-10-05` is called.
- **Then:** the response's `status` is `"unreviewed"`, and the habit's `checked` value
  is `false` (its current default).

### Daily review — draft save preserves edited values and merges new habits
- **Given:** a draft already exists for `2026-10-06` with `fix-habit-worked-out` saved as
  `checked: true`, and `fix-habit-no-sweets`'s `default_checked` is `false`.
- **When:** `GET /api/habittracker/reviews/2026-10-06` is called.
- **Then:** `fix-habit-worked-out`'s `checked` is `true` (the saved draft value, not
  re-derived from its current default), and `fix-habit-no-sweets`'s `checked` is `false`
  (its current default, since no draft row exists yet for that habit on this date).

### Daily review — editing a habit's default does not change an existing draft
- **Given:** the draft from the previous scenario, with `fix-habit-no-sweets` not yet
  saved on `2026-10-06`.
- **When:** `fix-habit-no-sweets`'s `default_checked` is changed to `true` via PATCH,
  then `GET /api/habittracker/reviews/2026-10-06` is called again.
- **Then:** `fix-habit-worked-out`'s `checked` is still `true` (unaffected — it already
  had a saved row), and `fix-habit-no-sweets`'s `checked` is now `true` (it had no saved
  row yet, so it picks up the new current default).

### Daily review — confirming a day stamps confirmed_at and counts it
- **Given:** the Unreviewed day `2026-10-07` with the current active habit set.
- **When:** `PUT /api/habittracker/reviews/2026-10-07` is called with `status:
  "confirmed"` and `habit_results` covering exactly that active set.
- **Then:** the response's `status` is `"confirmed"` and `confirmed_at` is set; a
  subsequent `GET /reviews/2026-10-07` returns the identical saved set.

### Daily review — confirmed day display is frozen against later habit edits
- **Given:** `2026-10-07` was confirmed in the previous scenario with
  `fix-habit-worked-out` included.
- **When:** `fix-habit-worked-out` is archived (end_date set to before `2026-10-07`) via
  PATCH, then `GET /api/habittracker/reviews/2026-10-07` is called again.
- **Then:** `fix-habit-worked-out` still appears in the response's `habits` array with
  its originally confirmed `checked` value, unaffected by the archival.

### Daily review — PUT is idempotent
- **Given:** the confirmed day from the above scenario.
- **When:** the identical `PUT /api/habittracker/reviews/2026-10-07` call (same status,
  same habit_results) is repeated.
- **Then:** the response is unchanged in content, no duplicate `habit_results` rows
  exist for that date, and `confirmed_at` reflects the most recent call.

### Daily review — PUT rejects a habit_results set that omits an expected habit
- **Given:** the Unreviewed day `2026-10-08` whose active habit set currently has five
  habits.
- **When:** `PUT /api/habittracker/reviews/2026-10-08` is called with `habit_results`
  covering only four of the five.
- **Then:** the response is an ApiError with code `VALIDATION_ERROR`, and no row is
  written for that date.

### Daily review — PUT rejects a habit_results set that adds an unexpected habit
- **Given:** the Unreviewed day `2026-10-08`.
- **When:** `PUT /api/habittracker/reviews/2026-10-08` is called with `habit_results`
  covering the full expected set plus one extra, unrelated `habit_id`.
- **Then:** the response is an ApiError with code `VALIDATION_ERROR`.

### Daily review — re-confirming accepts exactly the previously saved set even after the active window changes
- **Given:** a day already confirmed with a habit set that includes `fix-habit-archived`,
  and `fix-habit-archived`'s active window has since been edited to no longer cover that
  date.
- **When:** `PUT /api/habittracker/reviews/{that date}` is called again with `status:
  "confirmed"` and `habit_results` covering exactly the previously saved set (including
  `fix-habit-archived`).
- **Then:** the response is HTTP 200 and the correction succeeds (the frozen set, not
  the current active window, is what re-confirmation is validated against).

### Daily review — editing an already-confirmed day downgrades it to draft
- **Given:** the confirmed day `2026-10-07`.
- **When:** `PUT /api/habittracker/reviews/2026-10-07` is called with `status: "draft"`
  and an edited `habit_results` set (one checkbox flipped).
- **Then:** the response's `status` is `"draft"`, and `confirmed_at` is unchanged from
  its value before this call (not cleared, not re-stamped).

### Daily review — malformed date is rejected
- **Given:** no particular fixture state.
- **When:** `GET /api/habittracker/reviews/not-a-date` is called.
- **Then:** the response is an ApiError with code `VALIDATION_ERROR`.

### Reports — grid cell states cover all four cases
- **Given:** within a known week, `fix-habit-worked-out` has a confirmed-checked result
  on one date, a confirmed-unchecked result on another date, a draft-only (unconfirmed)
  result on a third date, and is outside its active window on a fourth date.
- **When:** `GET /api/habittracker/reports?period=week&anchor_date={that week}` is
  called.
- **Then:** the corresponding grid cells report `"completed"`, `"not_completed"`,
  `"unreviewed"`, and `"not_active"` respectively.

### Reports — per-habit rate omits percentage when eligible is zero
- **Given:** a reporting period in which `fix-habit-worked-out` has zero confirmed days.
- **When:** `GET /api/habittracker/reports?period=week&anchor_date={that week}` is
  called.
- **Then:** `fix-habit-worked-out`'s row has `eligible_confirmed_days: 0` and
  `rate: null` (never `0`).

### Reports — period-level elapsed days never counts future dates
- **Given:** a reporting period (`period=week`) whose anchor_date places "today" in the
  middle of the week.
- **When:** `GET /api/habittracker/reports?period=week&anchor_date={that week}` is
  called.
- **Then:** `period_summary.elapsed_days` equals the count of dates from the period's
  start through today inclusive, not the full period length.

### Reports — empty habit set still returns a valid period_summary
- **Given:** a reporting period entirely before any habit's `active_from` (or before the
  starter seed has ever run).
- **When:** `GET /api/habittracker/reports?period=week&anchor_date={that period}` is
  called.
- **Then:** the response is HTTP 200 with `rows: []`, and `period_summary.confirmed_days`
  /`period_summary.elapsed_days` are still correctly computed (not omitted or null).

### Reports — invalid period parameter is rejected
- **Given:** no particular fixture state.
- **When:** `GET /api/habittracker/reports?period=day&anchor_date=2026-10-01` is called.
- **Then:** the response is an ApiError with code `VALIDATION_ERROR`.

### [UI — manual] Daily Review shows a clear Unreviewed/Draft/Confirmed status
- **Given:** a user opens the Daily Review screen for a date that has never been touched.
- **When:** the screen loads.
- **Then:** a status indicator clearly reads "Unreviewed" (distinct from the checkbox
  states themselves); after the user toggles one checkbox, the indicator updates to
  "Draft"; after tapping **Confirm day**, it updates to "Confirmed".

### [UI — manual] Checkbox edits are never lost on navigation away
- **Given:** a user is on the Daily Review screen and toggles a checkbox, then
  immediately navigates to another screen before any visible save confirmation appears.
- **When:** the user returns to that same date's Daily Review screen later.
- **Then:** the toggled checkbox's new value is present, reflected as a Draft (or
  Confirmed, if Confirm day was tapped), never reverted to its prior value.

### [UI — manual] Reports grid cell drill-through opens the correct day
- **Given:** a user is viewing the Reports grid for a week.
- **Then:** tapping any grid cell navigates to the Daily Review screen for that cell's
  exact date, showing that date's actual saved or computed habit state.
