# EssayCards — Oral exams and section progression

Split out of `CLAUDE.md` (reference detail; load when working on this area).

## Oral examinations
(Sprint14 added scope, the 70% pass rule and state transitions on top of the round trip below
— see `## Section progression (Sprint14)`; `section_examinations` gained `passed`.)
Sections already have a stable author-assigned id (`anchor_slug`, unique per essay) —
that id is reused as-is for examination history; no separate section-id scheme was
introduced. "Version" of a section is `essay_sections.updated_at`, snapshotted into
`section_examinations.section_version_at` at export time — not a separate counter.
"Current understanding" of a section is never stored; it is always the latest row in
`essaycards.section_examinations` for that section_id.

Round trip: `GET /api/essaycards/essays/{id}/examination-package` builds a
self-contained JSON package (essay + sections + flashcards + each section's derived
last examination) for pasting into ChatGPT — copied to the clipboard by the "Export
for examination" button in ReaderView, together with the scoring-rubric prompt in
`EXAM_PROMPT_INTRO_*` (src/prompts.ts). ChatGPT's JSON reply is pasted into
`ImportExaminationsView` (`/essaycards/examinations/import`) and posted to
`POST /api/essaycards/examinations/import`, which resolves each result's
`essay_slug`/`section_anchor_slug` and inserts a new row — never updates or deletes
an existing one. Same validate-everything-before-any-write pattern as
`/essays/ingest`; `NOT_FOUND` if a slug pair doesn't resolve, `VALIDATION_ERROR` for
any structural problem, all-or-nothing across the whole batch.

The export endpoint is a GET that returns a bespoke JSON body rather than a Dataset —
a deliberate R-CON-BP-04 exemption (see backend/routers/examinations.py module
docstring): it's copied to the clipboard for an external LLM, not rendered by a
Dataset-consuming UI component. `GET /sections/{id}/examinations` (the plain history
list shown under each section in ReaderView) IS real UI-visible tabular data and
returns a proper Dataset.

**Nugget freshness (Sprint09, infrastructure only — not surfaced).** The export
package's `build_export_package` also attaches per-section `nugget_versions:
{nugget_key: live nuggets.updated_at}` for that section's currently-referenced
nuggets, mirroring the existing `section_version` field. Import accepts an optional
per-result `nugget_versions` and stores it **verbatim** (never recomputed) into the
new `section_examinations.nugget_versions_at` column — `null` means "predates this
feature" and skips the nugget-level check; absent on import stores `null` too. A pure
helper, `backend/examinations.py::nugget_freshness_flags(recorded, current)`, compares
a stored value against a freshly computed one and returns the changed/missing keys —
it exists and is tested, but is **not called by any endpoint or UI this sprint**; where
it is eventually surfaced is explicitly deferred.


## Section progression (Sprint14)
Replaces Sprint12's `## Learning progress` (the four-milestone `learning_level` and its nine
fields are gone). Everything below is DERIVED at query time from stored oral state plus
`flashcard_review_state.review_interval` — no traffic-light color is ever stored. All state
SQL lives in `backend/progress.py`; the pass rule and oral-state transitions live in
`backend/oral_state.py`; revalidation primitives in `backend/revalidation.py`.

**Pass rule.** See the Glossary: passed iff score >= 5 of 6 (70%). Computed once at import,
stored in `section_examinations.passed` / `essay_examinations.passed`; nothing re-derives it.
The package's `scoring` block echoes the rule so prompts and verdicts cannot drift.

**Section state** (highest satisfied wins): `blue` iff section unguided passed; else `green`
iff guided passed AND >= 1 card AND every card seen with `review_interval >= 24h`; else
`yellow` iff guided passed; else `grey`. A guided-passed section with zero cards is yellow,
never green. Blue needs only the unguided pass (an unguided pass on a never-guided section is
blue). `GET /progress/sections` returns one row per section (flat; client groups by
`essay_id`) with `state`, `next_step`, scores, passed dates, `cards_total`/`cards_established`,
`is_locked`.

**Essay state** (highest satisfied wins): `violet` iff essay unguided passed; else `blue` iff
>= 1 section and every section unguided passed; else `green` iff >= 1 card and every card
`review_interval >= 30 days` (learned); else `yellow` iff guided ESSAY oral passed (section
guided orals never count); else `grey`. Zero-card / zero-section essays are never vacuously
green/blue.

**Unlock.** A card is eligible for review only if its section's `section_oral_state` row has
`guided_passed`. Cards stay stored and counted; a card added later to an already-passed
section is unlocked automatically. `POST /flashcards/{id}/review` on a locked card is
`VALIDATION_ERROR` (no write). `GET /essays/{id}/questions` rows carry `is_locked`,
`card_state` (`locked|new|learning|established|learned`) and `needs_revalidation`.
Existing sections were grandfathered once at migration (`guided_pass_source =
'grandfathered'`: any reviewed card, or a guided exam scored >= 3).

**Oral import.** `POST /examinations/import` results carry a required `scope`
(`section` | `essay`). `section` needs `section_anchor_slug` + `section_version`; `essay`
must omit or null `section_anchor_slug` (omitted == null) and ignores `section_version` /
`nugget_versions`. All-or-nothing in one transaction; transitions apply in server import
order. Guided pass is sticky (a later failing guided attempt only updates the latest score).
A failing unguided SECTION attempt only records history. The response adds per result
`scope`, `passed`, `score_percent`, `effects`, and a top-level `revalidation` list.
`GET /essays/{id}/examination-package` now requires `exam_type` AND `scope`
(`section` also requires `section_id`; `essay` forbids it); `GET /essays/{id}/examinations`
lists whole-essay attempts.

**Failure cascade.** A failing unguided ESSAY attempt made while the essay was Violet, in the
same transaction: clears essay unguided pass (`unguided_invalidated_at = now()`), clears every
section's unguided pass, and flags every card of the essay that has been reviewed at least once
(`needs_revalidation = true`). Untouched: guided state, all attempt history, FSRS state, due
dates, intervals. A failing unguided essay attempt while NOT Violet is history-only.

**Revalidation.** Flagged cards are served by `GET /flashcards/revalidation` (any due date) and
excluded from `GET /flashcards/due`. The review endpoint derives the mode from the flag:
grade `again` = incorrect, any other grade = correct. Correct: flag cleared, an audit row in
`revalidation_events` (`preserved`), and NOTHING else changes (no FSRS call, no `review_events`
row). Incorrect: flag cleared and the normal FSRS failure path runs, plus a `failed` audit row.
The review UI in `?revalidate=1` mode shows exactly two buttons: Correct (sends `good`) and
Incorrect (sends `again`). Revalidation of an essay is complete when its pending count is 0.

**UI.** Overview: one large `EssayProgressDot` + one small dot per section (`SectionProgressDots`);
dots are native buttons with title + aria-label, their click stops propagation so they never also
open the essay row; a collapsed `ProgressLegend`; a `Revalidate (N)` control when pending > 0.
Reader: locked sections show a lock hint and a disabled "Review this section"; section menus
offer section-scope orals, the essay menu whole-essay orals.

**Known gaps (documented, not guarded).** State transitions follow server import order, not
`examined_at` order; editing a section after its oral pass does not invalidate the pass;
re-importing an identical failing result double-applies at most once (a second failing result is
history-only because the claim is already false).


## Guided progression (Levels 1-6)
Guided SECTION orals are Socratic learning conversations, not exams. They never score, never schedule
and never confer mastery (only `unguided_*` does). Code: `backend/guided.py`, `backend/routers/guided.py`.

**Levels** (specs live once in `guided.py::GUIDED_LEVELS`, shipped in the package as `level_spec`):
1 Orientation, 2 Comprehension, 3 Connections, 4 Application, 5 Critical understanding, 6 Independence.
Every level revisits the whole argument spine with more depth and less AI guidance.

**State.** `section_oral_state.guided_level` (0-6) = highest level the LEARNER confirmed. `guided_passed`
now means "Level 1 completed" and stays the single card-unlock flag (`UNLOCKED_SECTION_SQL` unchanged);
a passed row with level 0 (legacy/test seed) reads as Level 1 (`guided.current_level`,
`progress.GUIDED_LEVEL_SQL`). `guided_pass_source` gains `'guided_level'`.

**History.** `section_guided_sessions` (append-only): level, `section_version_at`, `session_at`,
transcript, AI `recommendation` (`advance|continue`) + `rationale`, brief `demonstrated`, `gaps`
(`[{text, serious}]`, only gaps still unresolved), `unguided_suggested`, the learner's `learner_decision`
(`advance|stay`) and `advanced_to`. The latest session's `demonstrated` + `gaps` plus the last 3 sessions'
outcomes are carried into the next package as `guided_progress`.

**Flow.** `GET /sections/{id}/guided-package` (default level = completed+1; `?level=` 1..completed+1)
-> ChatGPT -> paste in `ImportGuidedView`, which previews the recommendation and asks the learner to
Advance or Stay (advancing against an AI `continue` needs a second confirmation) -> `POST /guided/import`
with `learner_decision`. Server rules: advance iff `learner_decision = advance` AND `level = completed+1`;
a level above completed+1 is a `VALIDATION_ERROR`; a level at or below completed is recorded as practice;
progress never goes down; a reply recommending `advance` while listing a `serious` gap is rejected.
Several levels may be completed in one sitting; no cooldown, no FSRS. Completing Level 1 unlocks the
section's cards (effect `section_guided_unlocked`).

**Closed path.** `POST /examinations/import` rejects `exam_type=guided` + `scope=section`, and the
examination package rejects the same combination, so there is exactly one way to unlock cards.
Guided ESSAY-scope orals are unchanged exams (essay yellow light).

**Progress payload.** `GET /progress/sections` rows gain `guided_level` and `unguided_suggested`
(level >= 5); `next_step` becomes `unguided_oral` from Level 5 regardless of card state. Traffic-light
colours are unchanged. Guided sessions count in `GET /review-stats/summary` `orals_count` /
`guided_orals_count`.

**Migration.** At schema init every existing `guided_passed` section gets `guided_level = 1` (the backfill
is re-run safe); no higher level is inferred. Old guided `section_examinations` rows remain as history.

## Oral recall (Sprint16_RecallFSRS)
Two independent dimensions: **understanding** = guided level 0-6 (no FSRS); **recall** = unguided oral reconstruction, FSRS-scheduled per section and per essay (`recall_state`, append-only `recall_reviews`; `backend/recall.py`). Flashcards, oral recall and guided learning are three separate activities with separate queues (`/review`, `/recall`, reader menu).
- Status (derived): `not_established` (no successful review) / `current` / `due` (`next_due_at <= now()` or last rating `again` after establishment). Hard/Good/Easy establish; a first Again does not.
- Scheduler: FSRS-6 with no intra-day steps (`scheduling.recall_scheduler()`); the server clock drives scheduling, the reply's `examined_at` is evidence only.
- Import (`POST /examinations/import`, `exam_type: unguided`): `recall {rating, independent_elements, prompted_elements, missing_elements, misunderstandings, followups_asked<=2}` replaces the 0-6 score. Prompted recall caps at Hard (validated). Guided essay orals still use the score.
- Retired: the unguided-essay failure cascade (no more automatic revalidation flags from oral failures); legacy `unguided_*` columns are frozen history. `migrate_recall_state.py` seeds `recall_state` once from passed legacy unguided orals (one synthetic Good dated at the real `unguided_passed_at`; no review rows fabricated; legacy exam rows untouched).
- Recommendations (`GET /progress/sections` `next_step`): `guided_oral` (Level 1) -> `recall_due` -> `guided_next` (below Level 5) -> `unguided_recall` (Level >= 5, not established) -> `guided_next` (Level 6). Flashcard state never gates anything.
- API: `GET /recall/due`, `GET /recall/reviews`; progress rows gain `recall_*`, `next_guided_level`; essay rows gain `essay_recall_*`, `recall_due_count`.
- Overview dots: fill = guided level (grey/yellow -> dark green), ring = recall (none / solid / dashed). No essay-level fill; essay shows only a recall ring.
