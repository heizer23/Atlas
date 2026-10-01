# Test Spec — EssayCards — Sprint11_ReviewStats

## Scope
Tests `GET /api/essaycards/review-stats/summary` (the three rolling-window review-performance rollup) and the new Stats page that renders it. Out of scope: `GET /experiment/summary`, `GET /flashcards/stats`, and any per-essay/topic/scheduler scoping — none of these are touched by this sprint.

## Scenarios

### Always three fixed rows in day/week/month order
- **Given:** the fixture review history contains reviews scattered across recent hours, days, and weeks, for a mix of schedulers and grades
- **When:** `GET /api/essaycards/review-stats/summary` is called
- **Then:** the response is a Dataset with exactly three rows, whose `period` values are `day`, `week`, `month`, in that order

### Day window excludes reviews older than 24 hours
- **Given:** the fixture includes a review roughly 2 hours ago, another roughly 3 days ago, and another roughly 40 days ago
- **When:** `GET /api/essaycards/review-stats/summary` is called
- **Then:** the `day` row's `reviews` count includes only the ~2-hours-ago review; the `week` row additionally includes the ~3-days-ago review; the `month` row additionally includes reviews within the last 30 days but not the ~40-days-ago review; a review counted in `day` is also counted in `week` and `month` (the windows overlap, they do not partition)

### Grade breakdown sums to reviews count
- **Given:** the fixture's `week` window contains a mix of `again`/`hard`/`good`/`easy` graded reviews
- **When:** `GET /api/essaycards/review-stats/summary` is called
- **Then:** for the `week` row, `again_count + hard_count + good_count + easy_count` equals `reviews`, and `failures` equals `again_count`

### Recall rate is null when a window has zero reviews
- **Given:** the fixture contains no reviews within the last 24 hours
- **When:** `GET /api/essaycards/review-stats/summary` is called
- **Then:** the `day` row has `reviews` equal to `0` and `recall_rate` equal to `null` — never `0`

### Recall rate computed from reviews and failures
- **Given:** the fixture's `month` window contains a known number of reviews with a known number of `again`-graded failures among them
- **When:** `GET /api/essaycards/review-stats/summary` is called
- **Then:** the `month` row's `recall_rate` equals `(reviews - failures) / reviews` for that window

### Aggregation is scheduler-agnostic
- **Given:** the fixture's `week` window contains completed reviews assigned to both the `classic` and the `fsrs` scheduler
- **When:** `GET /api/essaycards/review-stats/summary` is called
- **Then:** the `week` row's counts include reviews from both schedulers combined, and no row or field in the response breaks the counts out by scheduler

### Rapid-retry reviews are included, not filtered out
- **Given:** the fixture's `day` window contains a review whose `prior_review_interval` is short (a rapid retry / relearning review, unlike an ordinary due review)
- **When:** `GET /api/essaycards/review-stats/summary` is called
- **Then:** that review is included in the `day` row's `reviews` and grade-breakdown counts — this endpoint applies no `prior_review_interval` filter, unlike `GET /experiment/summary`'s `ordinary_due_reviews` filter

### [UI] Stats page shows three window cards with grade breakdown
- **Given:** a user opens EssayCards and reviews have already been recorded (some within the last day, some only within the last week or month)
- **When:** the user selects the "Stats" nav entry (reachable at `/essaycards/stats`) and the page loads
- **Then:** three cards are visible, labeled for the Day, Week, and Month windows in that order, each showing its review count, its recall rate as a percentage — or the text "No reviews yet" when there is no data for that window — and a breakdown of again/hard/good/easy counts
