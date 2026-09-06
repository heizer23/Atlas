# Test Spec — EssayCards — Sprint05_ReviewQueueOrdering

## Scope

Backend API tests for `GET /api/essaycards/flashcards/due` ordering only.
Eligibility (`next_due_at <= now()`), scoping params, response shape, and the
`POST .../review` scheduling formula are unchanged and covered by
Sprint01_Core. UI: the review screen renders `rows` in server order and steps
through them unchanged — no new UI behavior, no new UI scenario.

All scenarios use the fixture essay `Essay E` (`fc-e-*` cards in
`tests/fixtures.sql`), nine eligible cards laid out so that the expected full
order is:

    RECENT : fc-e-recent-23h, fc-e-recent-near, fc-e-recent-far
    BACKLOG: fc-e-back-90d, fc-e-back-30d, fc-e-back-25h, fc-e-back-1d,
             fc-e-back-20min, fc-e-new

## Scenarios

### Recently reviewed card becomes due again
- **Given:** fixture `fc-e-recent-23h` — last reviewed 23h ago, `next_due_at` 90s in the past
- **When:** GET /flashcards/due?essay_id={Essay E}
- **Then:** the card is present in `rows`

### Recent due card takes priority over backlog
- **Given:** three RECENT cards and six BACKLOG cards, all eligible
- **When:** the queue is fetched
- **Then:** every RECENT card precedes every BACKLOG card, including the 90-day-interval mature card

### Recent category ordered by closest due time first
- **Given:** `fc-e-recent-near` due 2m ago, `fc-e-recent-far` due 20m ago
- **When:** the queue is fetched
- **Then:** `fc-e-recent-near` precedes `fc-e-recent-far` (next_due_at DESC)

### Backlog ordered by longest interval first
- **Given:** backlog cards with scheduled intervals 90d, 30d, 1d, 20min, and a never-reviewed card
- **When:** the queue is fetched
- **Then:** order is 90d → 30d → 1d → 20min → new

### Overdue duration does not affect backlog order
- **Given:** `fc-e-back-90d` ~1h overdue, `fc-e-back-1d` ~1d overdue, `fc-e-back-20min` ~3d overdue
- **When:** the queue is fetched
- **Then:** order is 90d → 1d → 20min — the reverse of most-overdue-first

### Card reviewed more than 24h ago falls back to backlog
- **Given:** `fc-e-back-25h` — last reviewed 25h ago, currently due
- **When:** the queue is fetched
- **Then:** it appears after every RECENT card, positioned among backlog by its ~25h interval (below the 30d card, above the 1d card)

### Rolling 24-hour boundary, no calendar-day logic
- **Given:** `fc-e-recent-23h` (reviewed 23h ago) and `fc-e-back-25h` (reviewed 25h ago) both came due ~90s ago
- **When:** the queue is fetched
- **Then:** the 23h card is RECENT, the 25h card is BACKLOG — decided purely by the `now() - 24h` rolling delta, independent of where local midnight falls

### New card (interval 0) sorts behind reviewed backlog
- **Given:** `fc-e-new` has `last_reviewed_at IS NULL`, currently due
- **When:** the queue is fetched
- **Then:** it appears after every reviewed backlog card

### New card available once no positive-interval backlog remains
- **Given:** every positive-interval backlog card is graded `easy` (pushed far into the future)
- **When:** the queue is re-fetched
- **Then:** `fc-e-new` remains, no positive-interval backlog card precedes it (only still-due RECENT cards do), and it is the last row

### Card with no history row treated as never reviewed
- **Given:** EssayCards has no per-review history table; `fc-e-new` has `last_reviewed_at IS NULL`
- **When:** the queue is fetched
- **Then:** the card is not in the RECENT category and is ordered as interval 0
