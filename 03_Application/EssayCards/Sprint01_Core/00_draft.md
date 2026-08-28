# Sprint Draft — EssayCards MVP: Single Essay Read + Review Loop

## Goal

Create a new Atlas application that pairs long-form essay reading with spaced-repetition
flashcards. A flashcard always links back to the essay passage that taught it; the essay
reader lets the user jump forward into review at the end of each section.

This sprint proves the full mechanic end to end on **one** essay. It does not build a
multi-essay library or an in-app content editor.

Component name `EssayCards` is a placeholder — rename freely during design review if a
better name comes to mind.

## Layer

03_Application

## Component

EssayCards

## Scope

- Ingest one essay from a markdown source file into the database (essay → ordered
  sections → flashcards per section).
- Reader view: render essay sections in order; each section shows a "Review this
  section" action once read.
- Review session view: shows due flashcards (front only), a flip action to reveal the
  answer, then four grade buttons. Each flashcard's answer view carries a "Jump to
  passage" link back to the exact section it came from.
- Spaced-repetition scheduling: grading a card computes its next due time using the
  algorithm defined below and persists it.
- A global "Due for review" entry point that surfaces every due card across the essay,
  not just the section just read (cards from earlier sections become due again over
  time and must resurface).

## Out of Scope

- Multiple essays / topic library UI
- In-app authoring or editing UI for essay text or flashcards
- User accounts / multi-user review state
- Typed-answer grading (this app is flip-and-self-assess only, not text matching)
- Review statistics, streaks, retention graphs
- Notifications/reminders when cards become due
- Offline support
- Any ingestion path other than the markdown format defined below (no file upload UI,
  no API-based import in this sprint)

## Content Ingestion

The essay is authored offline as a single markdown file and loaded into the database by
a one-shot ingestion script (run manually by the user after editing the file — not an
HTTP endpoint in this sprint).

**Source file convention** (exact grammar is the design phase's to finalize, but the
shape below is fixed):

- YAML front matter: `title`, `slug` (essay identity)
- Each `##` heading starts a new **section** (the "about one page" unit). Section title
  = heading text. Section anchor = an explicit slug the author assigns in the heading
  (e.g. `## Origins of the Format {#origins}`) — anchors must be author-assigned, not
  auto-generated from heading text, so they stay stable if a heading is reworded later.
- Flashcards for a section are declared in a fenced block at the end of that section's
  content, each with an **author-assigned stable id** (e.g. `fc-origins-1`). Stable ids
  are required because re-running ingestion after an edit must update existing rows
  in place (matched by id), never duplicate them or reset their review state.
- Re-ingestion is an upsert keyed by: essay by `slug`, section by `(essay_id,
  anchor_slug)`, flashcard by `(essay_id, card_id)`. A flashcard's SRS review state
  (`last_reviewed_at`, `next_due_at`) is never touched by re-ingestion — only its
  question/answer text and section link update.
- Deleting a flashcard from the source file does not delete its row (avoids silently
  destroying review history) — it is out of scope for this sprint to reconcile
  deletions; flag this as a known gap in the design artifact.

## Data Model

### Essay
- id
- title
- slug (unique)
- created_at, updated_at

### EssaySection
- id
- essay_id (FK → Essay)
- order_index (defines reading order within the essay)
- heading
- anchor_slug (unique within essay; stable, author-assigned)
- body_markdown
- created_at, updated_at

### Flashcard
- id
- essay_id (FK → Essay, denormalized for direct due-queue filtering)
- section_id (FK → EssaySection)
- card_key (author-assigned stable id from the source file, unique within essay)
- question
- answer
- created_at, updated_at

### FlashcardReviewState
- flashcard_id (FK → Flashcard, one row per flashcard)
- last_reviewed_at (nullable — null means never reviewed)
- next_due_at (not null — a freshly ingested card is due immediately: `next_due_at`
  defaults to the card's `created_at`)
- updated_at

Rules:
- A flashcard belongs to exactly one section and one essay.
- Deleting a section is out of scope for this sprint (content is edited via the source
  file and re-ingested; no delete path needed for a single static essay).

## Spaced Repetition Algorithm

**Time authority (R-CON-AL-06):** all "now" values used in scheduling are **server
time**, taken when the review request is handled. The client never computes or sends a
timestamp for grading — it only sends which button was pressed.

Four grade buttons, exactly these:

| Button | Behavior |
|---|---|
| `again` (the "False" button) | `next_due_at = now + 5 seconds`. Flat — no floor/doubling logic applies. |
| `hard` | floor = 1 minute |
| `good` | floor = 20 minutes |
| `easy` | floor = 1 day |

For `hard` / `good` / `easy`, on every grading event:

```
elapsed = (last_reviewed_at is null) ? null : (now - last_reviewed_at)
interval = (elapsed is null) ? floor : max(floor, 2 * elapsed)
next_due_at = now + interval
```

For **every** button, including `again`:
- `last_reviewed_at` is set to `now` after grading. This means a failed (`again`) review
  resets the elapsed-time clock — the next `hard`/`good`/`easy` grade after a fail
  compares against time-since-the-fail, not time since the last successful review.

A card that has never been reviewed (`last_reviewed_at is null`) uses only the floor —
there is no prior interval to double.

## API

Required endpoints. All under `/api/essaycards`.

```
GET  /api/essaycards/essays
GET  /api/essaycards/essays/{essay_id}
GET  /api/essaycards/flashcards/due
POST /api/essaycards/flashcards/{flashcard_id}/review
```

### `GET /api/essaycards/essays`
- No parameters.
- Returns Dataset: list of `{ id, title, slug }`.
- Ordering: `created_at asc`.
- Empty result is valid (no essay ingested yet) — UI shows an empty state, not an error.

### `GET /api/essaycards/essays/{essay_id}`
- Returns Dataset: essay `{ id, title, slug }` plus its sections, ordered by
  `order_index asc`, each `{ id, heading, anchor_slug, order_index, body_markdown }`.
- 404 → `ApiError` if `essay_id` does not exist.

### `GET /api/essaycards/flashcards/due`
- Params: `essay_id` (optional), `section_id` (optional, requires `essay_id`).
  - Neither given: all due cards system-wide.
  - `essay_id` only: all due cards in that essay.
  - Both given: due cards in that section only (used by the "Review this section"
    jump link).
- "Due" = `next_due_at <= now` (server time).
- Returns Dataset: list of `{ flashcard_id, question, answer, essay_id, section_id,
  anchor_slug, next_due_at }`. `answer` is included in the payload (not a separate
  reveal call) — the UI hides it client-side until flip; this is not a security
  boundary, just a display state.
- Ordering: `next_due_at asc` (most overdue first).
- Empty result is valid — "nothing due right now."

### `POST /api/essaycards/flashcards/{flashcard_id}/review`
- Mutation endpoint (R-CON-BP-04 exempt from Dataset requirement).
- Body: `{ "grade": "again" | "hard" | "good" | "easy" }`.
- On success: `200` with a typed record `{ flashcard_id, last_reviewed_at,
  next_due_at }`.
- On error (unknown `flashcard_id`, invalid `grade`): `ApiError`.

## UI

- Reader view: renders one essay's sections in order, standard markdown rendering.
  At the end of each section, a "Review this section" button navigates to the review
  session filtered to that section.
- Review session view: shows one due card at a time (question only), a "Flip" action
  reveals the answer plus a "Jump to passage" link (navigates to the reader at that
  section's anchor), then the four grade buttons appear.
- A top-level "Due for review" nav entry opens the review session with no section
  filter (global due queue).
- Session ends when the due queue (as loaded at session start) is exhausted; it does
  not live-poll for newly-due cards mid-session.

## Open Design Questions (for design review)

- Exact markdown grammar for the source file and the flashcard fenced-block syntax is
  not fully specified here — designer must finalize and document it in
  `10_architecture.json`.
- Deletion/reconciliation of sections or flashcards removed from the source file is an
  explicitly known gap (see Content Ingestion) — confirm this is acceptable for Sprint 1
  or scope a minimal handling.
