# EssayCards — Sprint history

Split out of `CLAUDE.md` (reference detail; load when working on this area).

## Sprint scope
- Sprint 1: One-shot markdown ingestion CLI, essay/section/flashcard data model, due-queue
  review loop with floor/doubling SRS scheduling, minimal React reader + review session UI.
- Sprint 2: `POST /api/essaycards/essays/ingest` JSON ingestion endpoint plus an in-app
  "Add / Update Essay" paste-JSON UI, sharing one upsert core with the markdown CLI path.
- Sprint 5: two-category ordering for `GET /flashcards/due` (see `## Due-queue ordering`).
- Sprint 7: essay roadmap (`status`), focus vs review sessions, materialised `review_interval`,
  roadmap knowledge indicators on `GET /essays` (see `## Roadmap, focus and review`).
- Sprint 8: card `level`, question-overview screen, single-question maintenance
  (edit/add/export/import) decoupled from essay ingest, single-essay export (see
  `## Question levels and overview`).
- Sprint 9: nuggets (`essaycards.nuggets`, `section_nuggets`), `essays.main_spine_markdown`,
  unified `[[nugget:key]]` reference validation across both ingestion paths, `flashcards.nugget_id`,
  nugget-aware flashcard exploration context, examination `nugget_versions` echo-through, and
  in-app nugget rendering/navigation (see `## Glossary` "Nuggets" and `## Nuggets` below).
- Sprint 10: FSRS as a second, persistently 50/50 A/B-assigned scheduling algorithm alongside
  Classic, a scheduler badge on the review card, and a first-version experiment dashboard.
  Retired in full by Sprint 12 (see below) — kept here only as a historical note.
- Sprint 11: `GET /review-stats/summary` — day/week/month observed recall dashboard.
- Sprint 12: FSRS becomes the SOLE scheduler (Classic + the Sprint10 A/B experiment and its
  dashboard removed entirely), a derived 0-4 essay `learning_level` with a new guided/unguided
  `exam_type` split on oral exams, consolidated essay/section action menus (`ActionMenu`) with a
  persisted category collapse control, and a reworked stats page (`GET /review-stats/activity`,
  `GET /review-stats/intervals`) plus regrouped main nav (see `## FSRS scheduling (Sprint12)` and
  `## Learning progress` (retired by Sprint 14, see `## Section progression (Sprint14)`)).
- Sprint 13: Review page shows a day-based five-metric row (Recalls / Unique / First from
  `GET /review-stats/today`, UTC calendar day; Due / New derived client-side from the due queue) and a
  single unlabeled interval row (the Current/Upcoming/Session UI of `## Review screen` below is
  superseded); Stats page Study Activity is a day-based stacked Repeat/Unique/First chart
  (`GET /review-stats/activity` now returns `recalls`/`unique_cards_seen`/`first_cards_seen`/`recall_rate`)
  and Observed Recall is a day/week/month selector (`/review-stats/summary` gains `new_count`);
  essay reader sentence feedback (`backend/sentences.py::split_sentences`,
  `backend/routers/sentence_feedback.py`, `essaycards.sentence_feedback` — two independent boolean
  flags per sentence, addressed by sentence_index; known gap: feedback can misattach if a section's
  body_markdown is edited after marking).
- Sprint 14: section-level learning progression — derived section/essay traffic lights replace the
  overview's planned/complete pill, card counts and 0–4 level; flashcards locked until a passed guided
  SECTION oral; 70% pass rule on all oral kinds; section- and essay-scope orals; Learned (>= 30d) card
  state; failure-triggered Revalidation that preserves FSRS state unless the card is forgotten
  (see `## Section progression (Sprint14)`). Retires Sprint12's `learning_level` and its nine fields.
- Sprint 15 (fast path): `GET /review-stats/summary` rows gain `orals_count` / `guided_orals_count` /
  `unguided_orals_count` (every `section_examinations` + `essay_examinations` attempt, passed or not, with
  `examined_at` inside the row's rolling 24h / 7d / 30d window); section export gains optional
  `include_examinations` (see `export_insert.md` "Improve section"); Stats `DailyActivityChart` opens
  scrolled to the newest day with the Unique segment on the tertiary colour. Design record:
  `Sprint15_StatsOralsAndImproveSection/05_fast_path_plan.md`.
