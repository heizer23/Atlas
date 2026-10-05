# Test Spec — EssayCards — Sprint13_ReviewStatsSentenceFeedback

## Scope

Covers the three new/changed backend surfaces (`GET /review-stats/today`, the reshaped
`GET /review-stats/activity`, `new_count` on `GET /review-stats/summary`, and the three new
sentence-feedback endpoints) and the observable Review page / essay reader / Stats page
behavior they drive. Out of scope: anything about `GET /flashcards/due`, `GET /flashcards/stats`,
FSRS scheduling/grading, or `GET /review-stats/intervals` — none of these are touched by this
sprint (see `10_architecture.json` §classification.non_goals).

## Scenarios

### Today endpoint — no scope returns global counts
- **Given:** reviews recorded today for several flashcards across different essays.
- **When:** `GET /review-stats/today` is called with no query parameters.
- **Then:** the response is a single-row Dataset whose `recalls` counts every review recorded
  today across the whole app.

### Today endpoint — section_id without essay_id is rejected
- **Given:** a valid `section_id`.
- **When:** `GET /review-stats/today?section_id=<id>` is called without `essay_id`.
- **Then:** the response is `VALIDATION_ERROR` (400 ApiError).

### Today endpoint — topic combined with essay_id is rejected
- **Given:** a valid `topic` and `essay_id`.
- **When:** `GET /review-stats/today?topic=<topic>&essay_id=<id>` is called.
- **Then:** the response is `VALIDATION_ERROR` (400 ApiError).

### Today endpoint — repeat reviews count once in Unique
- **Given:** a fixture flashcard reviewed three times today (and not before today).
- **When:** `GET /review-stats/today` is called in that card's scope.
- **Then:** `recalls` includes all three reviews, `unique_cards_seen` counts the card once, and
  `first_cards_seen` counts the card once (its first-ever review is also today).

### Today endpoint — a card's first-ever review from yesterday does not count as First today
- **Given:** a fixture flashcard first reviewed yesterday and reviewed again today.
- **When:** `GET /review-stats/today` is called in that card's scope.
- **Then:** `first_cards_seen` does not include that card, while `unique_cards_seen` does.

### Activity endpoint — reshaped row matches the worked example
- **Given:** a fixture UTC calendar day with 20 total reviews, 12 distinct cards reviewed, and
  2 cards whose first-ever review fell on that day.
- **When:** `GET /review-stats/activity` is called.
- **Then:** that day's row reports `recalls=20`, `unique_cards_seen=12`, `first_cards_seen=2` —
  the same numbers the draft's worked example derives Repeat=8/Unique=10/First=2 from.

### Activity endpoint — recall rate is null, not zero, on a day with no reviews
- **Given:** a day within the trailing 30-day window with zero recorded reviews.
- **When:** `GET /review-stats/activity` is called.
- **Then:** that day's row has `recalls=0`, `unique_cards_seen=0`, `first_cards_seen=0`, and
  `recall_rate=null`.

### Summary endpoint — New Cards Seen reflects first-ever reviews inside each window
- **Given:** a fixture flashcard whose first-ever review happened 10 days ago, with no other
  reviews since.
- **When:** `GET /review-stats/summary` is called.
- **Then:** the `month` row's `new_count` includes that card, but the `day` row's `new_count`
  does not.

### Sentence splitting — plain prose splits at sentence boundaries
- **Given:** a section whose `body_markdown` is "The sky is blue. The grass is green. Is that
  surprising?"
- **When:** `GET /essays/{essay_id}/sentences` is called for that essay.
- **Then:** the response contains exactly three ordered rows for that section, one per sentence.

### Sentence splitting — a markdown link is not split at its internal period
- **Given:** a section whose `body_markdown` contains a sentence with
  `[source](http://example.com/a.b)` followed by more prose in the same sentence.
- **When:** `GET /essays/{essay_id}/sentences` is called for that essay.
- **Then:** the link and the surrounding prose remain inside one sentence row, not split at the
  URL's internal period.

### Sentence splitting — a nugget reference is not split
- **Given:** a section whose `body_markdown` contains a sentence with `[[nugget:some-key]]`
  inside it.
- **When:** `GET /essays/{essay_id}/sentences` is called for that essay.
- **Then:** the nugget reference stays inside one intact sentence row.

### Sentence splitting — fenced code content is excluded
- **Given:** a section whose `body_markdown` contains a fenced code block alongside prose
  sentences.
- **When:** `GET /essays/{essay_id}/sentences` is called for that essay.
- **Then:** no returned sentence row contains the fenced code block's content.

### Sentence feedback list — empty when nothing is marked
- **Given:** an essay with sections but no `sentence_feedback` rows.
- **When:** `GET /essays/{essay_id}/sentence-feedback` is called.
- **Then:** the response is a Dataset with zero rows.

### Sentence feedback list — only marked sentences appear
- **Given:** one sentence marked `is_difficult` only and another marked `is_thumbs_up` only,
  among several unmarked sentences in the same essay.
- **When:** `GET /essays/{essay_id}/sentence-feedback` is called.
- **Then:** exactly those two sentence rows are returned; every unmarked sentence is absent.

### Sentence feedback — marking difficult then thumbs up on the same sentence yields one row with both flags
- **Given:** an unmarked sentence (fixture `sentence_index` and its exact `sentence_text`).
- **When:** `PATCH /sections/{section_id}/sentence-feedback` is called with
  `{flag: "difficult", value: true}`, then again with `{flag: "thumbs_up", value: true}`.
- **Then:** `GET /essays/{essay_id}/sentence-feedback` shows exactly one row for that sentence
  with `is_difficult=true` and `is_thumbs_up=true`.

### Sentence feedback — clearing the only true flag deletes the row
- **Given:** a sentence with `is_difficult=true` and `is_thumbs_up=false`.
- **When:** `PATCH .../sentence-feedback` is called with `{flag: "difficult", value: false}`.
- **Then:** a follow-up `GET /essays/{essay_id}/sentence-feedback` no longer includes a row for
  that sentence.

### Sentence feedback — clearing one flag leaves the other flag and the row intact
- **Given:** a sentence with both `is_difficult=true` and `is_thumbs_up=true`.
- **When:** `PATCH .../sentence-feedback` is called with `{flag: "difficult", value: false}`.
- **Then:** a follow-up `GET /essays/{essay_id}/sentence-feedback` still shows a row for that
  sentence, with `is_difficult=false` and `is_thumbs_up=true`.

### Sentence feedback — out-of-range sentence_index is rejected
- **Given:** a section with a known, finite sentence count.
- **When:** `PATCH .../sentence-feedback` is called with a `sentence_index` beyond that count.
- **Then:** the response is `VALIDATION_ERROR` (400 ApiError).

### Sentence feedback — sentence_text mismatch is rejected
- **Given:** a valid `sentence_index` for a section.
- **When:** `PATCH .../sentence-feedback` is called with `sentence_text` that does not match the
  section's current content at that index (simulating a stale client after the section was
  edited).
- **Then:** the response is `VALIDATION_ERROR` (400 ApiError).

### Sentence feedback — unknown section is rejected
- **Given:** a `section_id` that does not exist.
- **When:** `PATCH /sections/{section_id}/sentence-feedback` is called.
- **Then:** the response is `NOT_FOUND` (404 ApiError).

### Sentence feedback — invalid flag value is rejected
- **Given:** a valid section and sentence.
- **When:** `PATCH .../sentence-feedback` is called with `flag` set to something other than
  `"difficult"` or `"thumbs_up"`.
- **Then:** the response is `VALIDATION_ERROR` (400 ApiError).

### [UI] Review page shows no redundant page label on a plain review session
- **Given:** the user navigates to the Review page with no topic/essay scope.
- **When:** the page loads.
- **Then:** no standalone "Review" page-level caption is visible above the stats panel.

### [UI] Review page keeps its Focus caption on a scoped session
- **Given:** the user starts a focus session scoped to one essay.
- **When:** the Review page loads.
- **Then:** a "Focus · this essay" caption is visible above the stats panel.

### [UI] Review page shows the five daily metrics
- **Given:** the user is on the Review page (any scope).
- **When:** the page loads.
- **Then:** five labeled figures are visible, in order: Recalls, Unique, First, Due, New.

### [UI] Review page interval row shows one unlabeled row of six numbers
- **Given:** the user is on the Review page.
- **When:** the page loads.
- **Then:** the interval-distribution row below the five metrics shows six numeric columns with
  no "All" or "Session" row label visible.

### [UI] Essay reader — tapping a sentence opens a two-button feedback popover
- **Given:** the user is reading an essay section in `ReaderView`.
- **When:** the user taps/clicks a sentence.
- **Then:** a popover appears below that sentence with two independently-toggleable controls,
  "Difficult" and "Thumbs up".

### [UI] Essay reader — both flags can be set independently on the same sentence
- **Given:** the feedback popover is open for a sentence with neither flag set.
- **When:** the user taps "Difficult", then — without closing the popover — taps "Thumbs up".
- **Then:** both controls show an active/pressed state.

### [UI] Essay reader — marked sentences persist after reload
- **Given:** a sentence has been marked "Difficult" in a prior step.
- **When:** the page is reloaded.
- **Then:** that sentence shows its trailing difficulty indicator without the popover being
  open.

### [UI] Stats page — Study Activity shows a stacked bar with a recall-rate label per day
- **Given:** the user is on the Stats page.
- **When:** the page loads.
- **Then:** the Study Activity chart shows one column per day with a percentage value rendered
  above each column, and a legend reading "Repeat · Unique · First".

### [UI] Stats page — Observed Recall selector switches the displayed period
- **Given:** the user is on the Stats page, Observed Recall section.
- **When:** the user selects "Week" (having started on the default "Day").
- **Then:** the four displayed figures (Cards Seen, Unique Cards Seen, New Cards Seen, Recall
  Rate) update to the week period's values, and only one period's figures are shown at a time.
