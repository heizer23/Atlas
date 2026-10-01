# Sprint11 — Review performance statistics page

## Scope

A new statistics page answering "how did I do?" — review-performance rollups
over three trailing windows: a day, a week, and a month. Read-only, additive
only: no existing table, endpoint, or UI is changed in place. Global scope
(across every essay); no per-essay/topic/section breakdown this sprint.

This is a user-performance dashboard, distinct from the existing
`GET /experiment/summary` (`## Dual scheduler A/B (Sprint10)`), which compares
Classic vs. FSRS. This sprint aggregates across both schedulers — a reviewer
wants to know how *they* did, not which algorithm scheduled the card. Do not
duplicate or modify the experiment dashboard.

## 0. Data source

`essaycards.review_events` (Sprint10, append-only — see schema.sql) already
records everything needed: one row per completed review, with `reviewed_at`,
`grade` (`again`/`hard`/`good`/`easy`), `flashcard_id`, `scheduler`,
`prior_review_interval`. No schema change is required for this sprint — this
is a read-only aggregation feature.

## 1. Window definitions (R-CON-AL-06 — time authority)

Server time only (Postgres `now()`), computed fresh on every request — no
client-supplied time input anywhere in this feature.

Rolling trailing windows off `now()`, **not** calendar day/week/month
boundaries — this matches the existing precedent already established
elsewhere in this app (`## Due-queue ordering`'s RECENT window:
`last_reviewed_at >= now() - interval '24 hours'`, and `GET /flashcards/stats`'s
`within_1_day` / `within_7_days` / `within_30_days` forecast bands). Reusing
the same rolling-window convention keeps "a day" consistent across every
EssayCards surface rather than introducing a second, calendar-based meaning
of "day" alongside the existing rolling one.

- **Day** — `reviewed_at >= now() - interval '24 hours'`
- **Week** — `reviewed_at >= now() - interval '7 days'`
- **Month** — `reviewed_at >= now() - interval '30 days'`

Windows are independent, not exclusive buckets (a review counted in Day is
also counted in Week and Month) — this is a "how did I do over the trailing
N" report, not a partition of history into non-overlapping bands (contrast
with `GET /flashcards/stats`, whose seven bands are deliberately
non-overlapping/zero-filled; this is a different, and here inappropriate,
shape for the same underlying data).

## 2. Metrics per window

For each of the three windows, compute from `review_events`:

- `reviews` — count of all rows in the window.
- `unique_cards` — `count(distinct flashcard_id)` in the window.
- `again_count` / `hard_count` / `good_count` / `easy_count` — per-grade
  breakdown, summing to `reviews`.
- `failures` — alias/equal to `again_count`. Named separately for the same
  reason `GET /experiment/summary` names it separately: it is the quantity
  `recall_rate` is derived from, and the two must always be read together.
- `recall_rate` — `(reviews - failures) / reviews`, **`null` when
  `reviews == 0`** (not `0`) — same "no data yet vs. 0% recall" distinction
  already established in `backend/routers/experiment.py`. Do not filter by
  `prior_review_interval` here (unlike the experiment dashboard's
  ordinary-due-reviews filter) — this page reports on the reviewer's actual
  completed work in the window, including relearning/rapid retries; excluding
  them would make "how did I do today" undercount today's real session.

## 3. Backend API

New `backend/routers/review_stats.py`, mounted in `backend/main.py` after the
existing routers (same registration pattern as `experiment.router`).

- `GET /api/essaycards/review-stats/summary` — Dataset (R-CON-BP-04), always
  exactly three rows, `day` then `week` then `month`, in that fixed order —
  same fixed-row-order convention as `GET /experiment/summary`'s two rows, so
  a window with zero reviews still appears, zero-filled, rather than being
  absent. No query parameters this sprint (see Non-goals). Single query
  against `review_events` computing all three windows via `count(*) filter
  (where ...)`, mirroring the `filter (where ...)` style already used in
  `experiment.py`'s `_review_counts_by_scheduler` — do not run three separate
  round trips for three windows.
- Column schema: `period` (string), `reviews` (number), `unique_cards`
  (number), `again_count` / `hard_count` / `good_count` / `easy_count`
  (number), `failures` (number), `recall_rate` (number, nullable).

## 4. Frontend

New `ReviewStatsView` in `src/ShellEntry.tsx`, reachable at
`/essaycards/stats`, added to `mobilePrimaryNav`/the desktop nav array in
`src/shellConfig.ts` immediately after the existing `essaycards-experiment`
entry (`order: 5`, label `Stats`) — same registration mechanism already used
for every other top-level EssayCards view, no new nav pattern introduced.

Layout: three cards/columns (Day / Week / Month — the fixed row order from
§3), each showing the review count, recall rate as a percentage (or "No
reviews yet" when `recall_rate` is `null` — never render "0%" for that case,
per §2), and the four-grade breakdown. Reuse the existing Material 3 surface
tokens already used by `ExperimentDashboardView` / `ReviewStatsPanel` — no new
visual language.

## 5. Non-goals (explicit)

Per-essay/topic/section scoping; per-scheduler breakdown (already covered by
`GET /experiment/summary`); historical trend charts / graphs over time;
calendar-aligned "today"/"this week" (as opposed to the rolling windows in
§1); export of this data; any change to `review_events`, `experiment.py`, or
the existing forecast-band `GET /flashcards/stats` endpoint; streaks or
gamification; write/mutation endpoints of any kind — this entire sprint is
read-only.

## Note

Product request from the user in chat ("a statistics page to see how i did on
a day, in a week, and in a month"), scoped and drafted by Claude Code — the
user asked for all assumptions to be made without further back-and-forth.
Window semantics (§1), recall-rate null-vs-zero handling (§2), and
scheduler-agnostic scope were the three judgment calls; each is resolved
above by following an existing in-app precedent rather than inventing a new
convention. Intended to go through the full `R-PRO-BP-01` pipeline
(`sprint_design_application` → `sprint_design_reviewer` → `sprint_implement`
→ `sprint_test_runner`), same as Sprint09.
