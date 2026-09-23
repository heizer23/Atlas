# Implementation Review — EssayCards — Sprint10_DualSchedulerAB

**Verdict:** APPROVED
**Date:** 2026-09-23
**Reviewer:** independent-review-agent (Phase D, per `00_draft.md` §2)

## Scope

Independent adversarial review of the implemented code (working-tree diff on
`essaycards-sprint10-dual-scheduler-ab`, not yet committed), performed without
relying on prior agents' self-reports. All claims below were checked directly
against the actual diff, the running test container, and py-fsrs 6.3.2's
installed source — not accepted from `10_architecture.json` /
`11_design_review.md` / `13_design_review.md` / `50_test_report.md` at face
value, though all four were read first for context.

## Blocking Issues

| # | Location | Rule / Contract Violated | Required Change |
|---|----------|--------------------------|-----------------|
| _(None)_ | | | |

## Non-Blocking Issues

| # | Location | Observation |
|---|----------|-------------|
| 1 | `backend/scheduling.py::decide_scheduler_assignment` | The Python new-card hash (`sha256(flashcard_id)[0] % 2`) and the SQL migration hash (`hashtext(flashcard_id::text) % 2`) are two independent, unrelated hash functions over the same id space. This is explicitly documented as a deliberate, safe divergence (disjoint cohorts, no cross-language parity need) in both `CLAUDE.md` and `schema.sql`'s migration comment, and I agree with that reasoning — flagging only so a future sprint doesn't assume the two are the same function. |
| 2 | `tests/fixtures.sql` | The pre-Sprint10 fixture-pinning `UPDATE` (needed because `conftest.py`'s per-test `TestClient(app)` re-fires the startup handler and therefore reruns the migration backfill every test) is a real, non-obvious gotcha that the implementer caught, fixed, and self-reported via `EVD-2026-09-23-002`. No further action needed — noted here only for continuity, since it's exactly the kind of interaction a later sprint touching fixtures could reintroduce. |

_(Both items are informational; neither blocks approval.)_

## Findings Detail (most important)

1. **Selection-mechanism preservation — verified independently, holds.**
   `compute_next_due_at` (lines 47–73 of `backend/scheduling.py`) is
   byte-for-byte identical to `main`'s version (diffed directly:
   `git show main:.../scheduling.py` vs. working tree — only docstring/import
   lines above it changed). `GET /flashcards/due`'s SQL
   (`list_due_flashcards`) gained exactly one additive `SELECT` column
   (`frs.scheduler`); the `WHERE` clause (RECENT/BACKLOG eligibility, the
   `review_interval >= '24 hours'` review-vs-focus gate) and the full `ORDER
   BY` (RECENT-first, `next_due_at DESC` / `review_interval DESC` / tie
   breakers) are untouched. `GET /flashcards/stats`
   (`flashcard_queue_stats`) has **zero** diff lines at all — confirmed via
   `git diff --stat`, the seven forecast bands are completely unmodified.

2. **Atomicity — verified.** `POST /flashcards/{id}/review` reads `now()`
   once, dispatches to `ClassicScheduler`/`FSRSScheduler`, then performs the
   `flashcard_review_state` `UPDATE`, the conditional `fsrs_card_state`
   upsert, and the unconditional `review_events` insert all on the same
   cursor inside one `with get_db() as conn: with conn.cursor() as cur: ...
   conn.commit()` block — a single commit covers all three writes.
   `backend/database.py::get_db()`'s generator rolls back on any exception
   before returning the connection to the pool, so a failure partway through
   cannot leave a partial write.

3. **Migration correctness and idempotency — verified, including a direct
   idempotency test.** Both `schema.sql` migration `UPDATE`s are guarded on
   `scheduler_assigned_at IS NULL`; after the first run every row has a
   non-null value, so a rerun of `init_schema()` (which happens on every
   container startup) matches zero rows. Neither `UPDATE`'s `SET` list
   touches `next_due_at`/`review_interval`/`last_reviewed_at`. Already-reviewed
   rows go to `classic`/`legacy_retained_classic` unconditionally; never-reviewed
   pre-existing rows go through the same balanced hash as a new card, reason
   `migrated_never_reviewed_random`. `tests/test_migration.py` exercises all
   three properties directly against the DB (not through the HTTP layer),
   including a rerun test that asserts the row is byte-for-byte unchanged
   (including `scheduler_assigned_at` itself) on the second pass.

4. **Assignment idempotency across all three creation sites — verified.**
   `backend/ingest.py::_upsert_flashcard`, `backend/routers/flashcards.py::
   _upsert_question`, and `backend/exploration.py::execute_plan`'s
   `create_card` branch each call `decide_scheduler_assignment` exactly once,
   only inside their existing `if row["was_inserted"]:` gate — never on the
   update path. No endpoint request body anywhere accepts or reads a
   `scheduler` key (checked by grep across `backend/routers/`).

5. **Vocabulary leakage — none found.** Grepped `src/ShellEntry.tsx` for
   FSRS-native terms (stability, difficulty, FSRS state names); the only hit
   is the plain-English word "relearning" in one dashboard caption
   ("immediate relearning and rapid retries are excluded"), which is
   ordinary English, not FSRS-internal vocabulary, and matches the mission's
   own language in `00_draft.md §7`.

6. **Scope creep — none found.** No per-card scheduler-switching endpoint, no
   FSRS parameter-optimization code, no per-essay scheduler config, no
   changes to Directed Study or new-card prioritization. The only new route
   is `/experiment` (dashboard) and the only new backend endpoint is `GET
   /experiment/summary`, both within mission scope.

7. **Independent test run — confirms the report.** Ran
   `docker exec atlas-essaycards-test pytest tests/ -v` myself:
   **260 passed, 1 failed** — identical to `50_test_report.md`. Independently
   re-verified the excluded failure
   (`test_examinations.py::test_import_stores_new_result_without_overwriting_history`)
   is pre-existing and unrelated: `git diff --stat` shows zero changes to
   `tests/test_examinations.py` in this sprint's working tree, and
   `git log --follow` shows the test function was introduced in `11c94ae`,
   well before Sprint10.

8. **Design-review process quality.** The one real Major finding from Phase
   B/C's own design review (`was_due` cannot separate rapid retries from
   genuine spaced review, because the due-queue's own unchanged base
   eligibility makes `was_due` true for virtually every reachable review) was
   correctly diagnosed and correctly fixed by switching the dashboard filter
   to `prior_review_interval >= interval '24 hours'`. I independently
   re-derived the same conclusion by reading `list_due_flashcards`'s `WHERE`
   clause before reading the review document, and confirmed
   `backend/routers/experiment.py`'s actual SQL uses the corrected filter,
   not `was_due`. `test_experiment_summary_excludes_non_due_reviews_from_recall_sample`
   and `test_experiment_summary_reports_assigned_reviewed_completed_and_recall_with_sample_size`
   both assert this against independently-computed ground-truth SQL rather
   than re-deriving the implementation's own query, which is good test
   hygiene.

9. **py-fsrs API usage verified against the installed library.** Confirmed
   interactively inside `atlas-essaycards-test` (fsrs==6.3.2 installed,
   matching the `>=6.3.2` pin): `Scheduler.review_card(card, rating,
   review_datetime=...)` returns `(Card, ReviewLog)`; `Card.to_dict()` /
   `Card.from_dict()` round-trip; `State` enum values are exactly
   `{Learning: 1, Review: 2, Relearning: 3}`, matching the
   `ck_fsrs_card_state_fsrs_state check (fsrs_state in (1, 2, 3))` constraint
   and the code's `int(new_card.state)` cast.

## Approval Condition

None — approved as-is. No Critical or Major issues found; no evidence-store
entry was required from this review (both non-blocking items above were
already self-identified and logged by the implementer as
`EVD-2026-09-23-002`/`003`, and neither rises to Major on independent
re-examination since both were caught and fixed pre-test-run).
