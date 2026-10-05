# Sprint Draft — HabitTracker MVP: Daily Review, Habit Definitions, Reporting

## Goal

A personal habit tracker built around one evening ritual: review today (or any day),
confirm which configured habits were actually done, and later see how consistent that
has been. Fast and comfortable on mobile — this is meant to be used once a day, every
day. All inputs are manual this sprint; automatic activity feeds (workouts,
flashcards, blood pressure) are explicitly deferred to a later sprint.

## Layer

03_Application

## Component

HabitTracker

## Scope

- Daily review screen: review and confirm a single day's habits, defaulting to today,
  with the ability to open and correct any previous day.
- Habit definition screen: create, edit, reorder, and archive habits.
- Reporting screen: weekly/monthly completion grid and per-habit rates for a selected
  period, with drill-through back into a day's review.
- Five starter habits, seeded at first run (see Habit Definitions).

## Out of Scope

- Any automatic data source (workouts, EssayCards review activity, blood-pressure
  tracker) — everything is a manual checkbox this sprint. The data model reserves a
  `source` field per result (see Data Model) so a later sprint can add automatic
  sources without a schema change, but no integration exists yet.
- Reminders/notifications.
- Automatic promotion of a habit's default to checked based on performance — default
  changes are always an explicit manual edit on the habit definition screen.
- Schedules, weekly targets, quantities, or non-daily habits — every habit is daily in
  this sprint.
- Gamification (streaks, badges, scoring).
- Multi-user accounts, sharing, or permissions — single-user system, matches the rest
  of Atlas.
- Deleting a habit definition — archiving (setting an end date) is the only retirement
  path, so historical reviews always resolve.

## Day Model and Review States

A day is identified by its Europe/Berlin calendar date (see Time Authority). A day has
exactly one of three states, determined entirely by whether and how it has been saved
— there is no stored "unreviewed" row:

- **Unreviewed** — no saved record exists for the date. The review screen computes a
  fresh view from current habit definitions (see Defaults and Merging) and nothing is
  persisted until the user changes something.
- **Draft** — the user has changed at least one checkbox for that date since it was
  last unreviewed or last confirmed, and the edit has been saved as a draft. Drafts
  persist across navigation/reloads but are explicitly excluded from report counts and
  rates.
- **Confirmed** — the user tapped **Confirm day**. The full set of habit results for
  that date is saved, `confirmed_at` is stamped, and the day counts in reports.

Draft saving is automatic (no separate "save draft" button — only **Confirm day** is a
user-facing action per the requirement): each checkbox change persists immediately as
a draft via the same idempotent endpoint Confirm uses, just with a different status
(see API). Design phase may debounce the network call, but the contract is: no edit is
ever silently lost on navigation away, and no unconfirmed edit is ever counted as
completed.

Re-confirming an already-confirmed day (i.e. correcting a past day) overwrites that
day's saved results and `confirmed_at`. Confirming is idempotent: repeating it with the
same payload must not create duplicate rows (single row per date, upserted).

## Defaults and Merging

This is the one piece of real logic in the sprint — get it exactly right, since it's
what "preselected habits are assumptions, not facts" depends on.

**Habit list for a given date** = every habit whose active window covers that date:
`habit.active_from <= date` and (`habit.end_date is null` or `date <= habit.end_date`),
in the habit's configured `display_order`.

**Checked value for each habit on an Unreviewed or Draft day** (i.e. not yet
confirmed):
- If a saved result row already exists for (date, habit) — from a prior draft save —
  use its stored `checked` value.
- Otherwise (habit has no saved row yet for this date — true for every habit on a
  first-ever view of an Unreviewed day, and also true for a habit that became active,
  or was created, after this date's draft was first saved) — use that habit's
  *current* `default_checked`.

This merge means: editing a habit's default never changes a date's already-saved draft
or confirmed values (R-CON-AL per-field semantics), but it does supply a sensible
starting value for any habit the draft hasn't seen yet. This directly implements "a
default change must not change saved reviews or existing drafts."

**Confirmed day display is frozen**: reopening a Confirmed day shows exactly its saved
result rows — one per habit that was part of that confirmation — joined to each
habit's name/description for display. It does **not** recompute "habits active on this
date" from the current habit definitions. This is what "reopening a confirmed day must
show its saved results, not reapply defaults" requires: if a habit's active window or
archive state is edited after the fact, previously confirmed days are unaffected and
keep showing the exact habit set and values they were confirmed with.

(This also resolves the apparent tension with the Habit List rule above, which applies
only to Unreviewed/Draft — i.e. not-yet-locked-in — days.)

## Data Model

Three separate tables, matching "keep habit definitions, daily review status, and
individual habit results separate":

### Habit
- id
- name
- description (nullable — optional short text)
- default_checked (bool)
- display_order (integer, unique, defines configured order)
- active_from (date)
- end_date (date, nullable — set only when archived; null means still active)
- created_at, updated_at (server time)

Archiving a habit sets `end_date` to a chosen date; it is never deleted. "Un-archiving"
(clearing `end_date`) is in scope as a plain field edit — same endpoint, same rules —
since the draft doesn't call it out as forbidden and the UI needs no separate flow for
it.

### DailyReview
- id
- review_date (date, unique — one row per calendar date, ever)
- status: `draft` | `confirmed`
- confirmed_at (timestamptz, nullable — set on confirm, cleared is never needed since a
  row's existence already implies draft-or-later)
- created_at, updated_at (server time)

### HabitResult
- id
- review_date (paired with Habit, not a surrogate FK to DailyReview.id, so every query
  reads directly as `where review_date = $1` without an extra join — same rationale as
  StoryReader's version-pinning pattern)
- habit_id (FK → Habit)
- checked (bool)
- source: `manual` (enum/text, default and only value this sprint — reserved column so
  a future automatic source doesn't require a migration)
- created_at, updated_at (server time)
- Unique on (review_date, habit_id) — confirming or draft-saving a day upserts this set,
  never appends duplicates.

## Habit Definitions (starter data)

Seeded once, at first run, editable immediately afterward (not read-only defaults
baked into code):

| name | default | active_from |
|---|---|---|
| Worked out | unchecked | sprint launch date |
| No sweets | unchecked | sprint launch date |
| No vaping | unchecked | sprint launch date |
| Measured blood pressure | unchecked | sprint launch date |
| Reviewed EssayCards | unchecked | sprint launch date |

`display_order` = the order listed above. Design phase picks the exact seeding
mechanism (schema.sql seed insert vs. a startup check) — same idempotency requirement
as everything else here: re-running startup must not duplicate the five rows.

## Reporting

**Period selection**: week or month, navigable (prev/next), anchored on a selected
date (defaults to the period containing today).

**Grid**: habits (rows, configured order, including archived ones that were active at
any point in the period) × dates in the period (columns). Each cell is exactly one of:

- `completed` — a HabitResult row exists for (date, habit), the day's status is
  `confirmed`, and `checked = true`.
- `not_completed` — a HabitResult row exists for (date, habit), the day's status is
  `confirmed`, and `checked = false`.
- `not_active` — no HabitResult row exists for (date, habit), **and** the habit's
  current active window excludes that date (`date < active_from` or `date >
  end_date`).
- `unreviewed` — every other case: no HabitResult row and the habit's window currently
  covers the date (day never touched, or only ever drafted, for that habit) — this
  bucket also covers future dates and draft-only days, matching "do not treat
  unreviewed or future days as failures."

Note the asymmetry with the Daily Review screen's frozen-confirmed-day rule: here, the
presence of a saved HabitResult row (from a confirmed OR draft day) is what decides
`not_active` vs `unreviewed`/`completed`/`not_completed` — a habit's current window
only matters when no row exists at all for that date. This keeps a habit that was
later archived still shown correctly for dates it actually has results on.

**Per-habit stats for the period**:
- Eligible confirmed days = count of dates in the period where the day's status is
  `confirmed` and a HabitResult row exists for that habit (i.e. the habit was part of
  that confirmation).
- Completed count = subset of the above with `checked = true`.
- Rate = completed / eligible, shown as a percentage **with the denominator visible**
  (e.g. "5 / 6 confirmed days"). If eligible = 0, show no percentage — just the
  denominator (e.g. "0 confirmed days") — never "0%" or "—%" implying a computed zero.

**Period-level stat**: confirmed days vs. elapsed days, where elapsed days = dates in
the period from the period start through `min(period_end, today)` inclusive (today in
Europe/Berlin) — future dates are never counted in the denominator.

**Drill-through**: tapping any grid cell or day column opens that date's Daily Review
screen.

## API

All under `/api/habittracker`.

```
GET   /habits
POST  /habits
PATCH /habits/{habit_id}
POST  /habits/reorder

GET   /reviews/{date}
PUT   /reviews/{date}

GET   /reports
```

### `GET /habits`
- No parameters. Returns Dataset: every habit (including archived), ordered by
  `display_order`. Empty result is valid only pre-seed; otherwise the five starters
  are always present at minimum.

### `POST /habits`
- Mutation. Body: `{ name, description?, default_checked, active_from }`.
  `display_order` is assigned server-side as `max(display_order) + 1` — not
  client-supplied, so reordering stays the single source of truth for order.
- On success: `201` with the created Habit record.
- On error (missing `name`, invalid `active_from`): `ApiError VALIDATION_ERROR`.

### `PATCH /habits/{habit_id}`
- Mutation, partial update (R-CON-AL-04). Body may include any of: `name`,
  `description`, `default_checked`, `active_from`, `end_date`.
- `description`: omitted = unchanged; explicit `null` = clears it; a string = sets it.
  Frontend must send `null` explicitly to clear, never omit to mean "clear" (R-CON-AL-04/05).
- `end_date`: omitted = unchanged; explicit `null` = un-archives (clears it); a date =
  archives as of that date. Archiving is just this field edit — no separate
  "archive" endpoint.
- Editing `default_checked` only ever affects future Unreviewed/Draft merges (see
  Defaults and Merging) — never past saved rows.
- On success: `200` with the updated Habit record. On error (unknown id, invalid date
  ordering such as `end_date < active_from`): `ApiError`.

### `POST /habits/reorder`
- Mutation. Body: `{ habit_ids: [ ... ] }` — the full ordered list of every habit id
  (including archived ones, which keep a stable position among themselves). Sets
  `display_order` to each id's index. Rejected with `ApiError VALIDATION_ERROR` if the
  set of ids doesn't exactly match all existing habits.
- On success: `200`, no body required.

### `GET /reviews/{date}`
- `date`: path param, `YYYY-MM-DD`, interpreted as a Europe/Berlin calendar date (not
  validated against "today" — any past or future date is a valid lookup).
- Returns Dataset (single row): `{ review_date, status: "unreviewed"|"draft"|"confirmed",
  confirmed_at, habits: [{ habit_id, name, description, display_order, checked }] }`,
  computed per Defaults and Merging / Confirmed day display is frozen above.
- Always 200 — an Unreviewed date is a valid, computed response, not a 404.

### `PUT /reviews/{date}`
- Mutation. Body: `{ status: "draft"|"confirmed", habit_results: [{ habit_id, checked }] }`.
  `habit_results` must cover exactly the habit set the client was shown for that date
  (the full set from the last `GET`, with edits applied) — this endpoint always
  replaces the complete set for the date, never a partial patch of a subset of habits.
- Upserts the DailyReview row (by unique `review_date`) and the HabitResult rows (by
  unique `(review_date, habit_id)`) in one transaction. Setting `status: "confirmed"`
  stamps `confirmed_at = now()` (server time); setting `status: "draft"` leaves
  `confirmed_at` as it was (null if never confirmed before).
- Safe to repeat with the same payload — no duplicate rows, confirming twice or
  draft-saving twice is a no-op beyond the timestamp update (R-CON-AL-05 round-trip,
  R-PRO-BP-01 §"safe to repeat").
- On success: `200` with the same shape `GET /reviews/{date}` returns. On error
  (`habit_results` references an unknown `habit_id`, or omits/adds to the expected
  set): `ApiError VALIDATION_ERROR`.

### `GET /reports`
- Params: `period` (`week`|`month`, required), `anchor_date` (`YYYY-MM-DD`, required —
  the frontend resolves "defaults to the period containing today" client-side-once and
  always sends an explicit anchor; no implicit server-side "today" fallback here, to
  keep this endpoint's output pure given its inputs per R-CON-AL-01).
- Boundary construction: `week` = Monday–Sunday containing `anchor_date` (ISO week);
  `month` = the calendar month containing `anchor_date`, Europe/Berlin.
- Returns Dataset: grid rows (one per habit, including archived-but-relevant-in-period
  ones) × the period's dates, cell states as in Reporting above; plus per-habit stats
  (eligible confirmed days, completed count, rate-or-null) and the period-level
  confirmed-vs-elapsed count.
- Empty-result behavior: a period with zero habits ever active in it still returns a
  valid Dataset with zero grid rows (not an error) — this can only happen before the
  starter habits are seeded or for a period entirely before every habit's
  `active_from`.

## UI

Registered in Atlas Shell (`src/shellConfig.ts`) with `mobilePrimaryNav` as the primary
target — daily, one-handed use is the main use case, same rationale as StoryReader.

- **Daily Review** (`/habittracker`, optional `/habittracker/review/:date`): date
  picker/prev-next defaulting to today; list of that date's habits in configured
  order, each a checkbox pre-set per Defaults and Merging; a status indicator
  distinguishing Unreviewed / Draft / Confirmed at a glance (not just via the
  checkboxes — the requirement explicitly calls out telling an unreviewed day apart
  from a confirmed-but-incomplete one); single **Confirm day** button.
- **Habit Definitions** (`/habittracker/habits`): list in configured order with
  reorder controls, each row editable (name, description, default, active-from,
  archive toggle / end date); add-new-habit form. Archived habits shown, visually
  distinguished, not hidden.
- **Reports** (`/habittracker/reports`): period switcher (week/month) with prev/next
  navigation; grid; per-habit stat rows below or beside it; confirmed-vs-elapsed
  summary for the period; tapping a grid cell or date column opens that date in Daily
  Review.

## Time Authority

Europe/Berlin is authoritative for every calendar-date concept in this app: "today"
for defaulting the Daily Review screen and bounding "elapsed days" in Reports, and the
day boundary used whenever a date is written or compared. This is computed
server-side (server converts its clock to Europe/Berlin), never trusted from the
client — the client only ever sends an explicit `date`/`anchor_date` string, never a
raw timestamp or "is this today" boolean (R-CON-AL-06). The one client-side use of
"today" is purely cosmetic (which date the Daily Review screen opens to, and which
period Reports defaults to on first load) and is always re-expressed as an explicit
`date`/`anchor_date` param before it reaches the API — the server does not need to
agree with the client's clock for correctness, only for that one default's presentation.

## Open Design Questions (for design review)

- Exact debounce/timing of automatic draft-save on checkbox toggle (immediate vs.
  short debounce) — contract only requires no edit is ever lost.
- Whether `end_date` ordering validation (`end_date >= active_from`) belongs in the
  backend, the DB (CHECK constraint), or both.
- Exact visual treatment for the three day-status states and the four grid cell
  states — functionally specified above, visual design left to implementation.
