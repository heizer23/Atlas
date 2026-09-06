# Sprint05 — Review-queue ordering

## Scope

Change **only** which eligible card `GET /api/essaycards/flashcards/due` shows
next. No change to the interval calculation (`backend/scheduling.py`) or the
meaning of the `again` / `hard` / `good` / `easy` buttons.

## Eligibility (unchanged)

A card is eligible when `next_due_at <= now()` (Postgres server clock,
R-CON-AL-06).

## New ordering — two categories, RECENT entirely before BACKLOG

### A. RECENT — relearning / short-term
`last_reviewed_at >= now() - interval '24 hours'` **and** `next_due_at <= now()`.

- Rolling 24h window off the same `now()`. **Not** calendar-day / "reviewed
  today" logic — the local midnight boundary is irrelevant.
- `last_reviewed_at IS NULL` is never RECENT.
- Sort **`next_due_at` DESC** (closest to now first). Example: Card A came due
  20 min ago, Card B 2 min ago → B first. A card the user just pushed 5 minutes
  into the future disappears, then re-enters near the front once those 5 minutes
  elapse.

### B. BACKLOG — everything else eligible
- Sort by the interval the card is currently scheduled across,
  `next_due_at - last_reviewed_at`, **DESC** (longest first, shortest last).
- Overdue duration must **not** affect order. 90d interval card only 1 min
  overdue still beats a 1d interval card days overdue.
- Purpose: mature long-interval cards are verified first; if still known they
  get pushed far out and leave the active workload. Immature short-interval
  cards are still reached — below mature backlog, above new cards.

### C. New cards
`interval = 0`. The data model already represents a new card as
`last_reviewed_at IS NULL` (`backend/ingest.py` seeds it). interval 0 sorts
behind every reviewed backlog card automatically — no separate queue, no
"block new cards until backlog empty" gate.

## `lastReviewedAt` source of truth

There is **no** flashcard answer/history table in EssayCards. `last_reviewed_at`
lives directly on `essaycards.flashcard_review_state` (one row per card) and is
written on every graded review — including `again` — from a single Postgres
`select now()`. Use it directly: no join, no `MAX()`, no new table, no new
index, no duplicate persistent state. (`section_examinations` is append-only but
is oral-exam history for essay *sections*, unrelated to flashcards.)

## Required test coverage

- recently reviewed card becoming due again
- recent due card beats normal backlog
- recent category ordered closest-due first
- backlog ordered longest-interval first
- overdue duration does not affect backlog order
- card reviewed > 24h ago falls back to backlog
- rolling 24h boundary (no calendar-day component)
- new card (interval 0) sorts behind reviewed backlog
- new card available once no positive-interval backlog remains
- card with no history row treated as never reviewed (`last_reviewed_at IS NULL`)

## Note

Implemented directly from this draft at the user's request; the full
`R-PRO-BP-01` design→review→test agent pipeline was not run for this change.
