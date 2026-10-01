# Test Report — EssayCards — Sprint11_ReviewStats

**Verdict:** TESTS_PASSING
**Date:** 2026-09-26
**Fix iteration:** 0

## Results

| Scenario | Test | Type | Status | Failure reason |
|----------|------|------|--------|----------------|
| Always three fixed rows in day/week/month order | `test_review_stats_summary_returns_three_fixed_rows_in_order` | backend | PASS | — |
| Day window excludes reviews older than 24 hours | `test_review_stats_day_window_excludes_reviews_older_than_24_hours` | backend | PASS | — |
| Grade breakdown sums to reviews count | `test_review_stats_grade_breakdown_sums_to_reviews` | backend | PASS | — |
| Recall rate is null when a window has zero reviews | `test_review_stats_recall_rate_is_null_when_window_has_zero_reviews` | backend | PASS | — |
| Recall rate computed from reviews and failures | `test_review_stats_recall_rate_computed_from_reviews_and_failures` | backend | PASS | — |
| Aggregation is scheduler-agnostic | `test_review_stats_aggregation_is_scheduler_agnostic` | backend | PASS | — |
| Rapid-retry reviews are included, not filtered out | `test_review_stats_includes_rapid_retry_reviews` | backend | PASS | — |
| [UI] Stats page shows three window cards with grade breakdown | `tests/ui/review_stats.spec.ts` (3 tests: nav entry, card order, recall+breakdown per card) | UI | PASS | — |

## Test output

```
$ docker compose -f 01_System/test/compose.test.yml --env-file 01_System/config.env \
    --env-file 01_System/secrets.env up -d essaycards-test --build
 Image test-essaycards-test Built
 Container atlas-essaycards-test Recreated
 Container atlas-essaycards-test Started

$ docker ps --filter name=atlas-essaycards-test --format '{{.Names}}\t{{.Status}}'
atlas-essaycards-test	Up 4 seconds

$ docker exec atlas-postgres psql -U atlas -lqt | grep atlas_test
 atlas_test | atlas | UTF8 | libc | en_US.utf8 | en_US.utf8 |

$ docker exec atlas-essaycards-test pytest tests/ -v
============================= test session starts ==============================
platform linux -- Python 3.12.14, pytest-9.1.1, pluggy-1.6.0
collected 269 items

... (263 pre-existing tests across test_essays.py, test_flashcards.py,
    test_experiment.py, test_shell_proxy.py, test_images.py, etc. — all PASSED) ...

tests/test_review_stats.py::test_review_stats_summary_returns_three_fixed_rows_in_order PASSED [ 86%]
tests/test_review_stats.py::test_review_stats_day_window_excludes_reviews_older_than_24_hours PASSED [ 86%]
tests/test_review_stats.py::test_review_stats_grade_breakdown_sums_to_reviews PASSED [ 87%]
tests/test_review_stats.py::test_review_stats_recall_rate_is_null_when_window_has_zero_reviews PASSED [ 87%]
tests/test_review_stats.py::test_review_stats_recall_rate_computed_from_reviews_and_failures PASSED [ 88%]
tests/test_review_stats.py::test_review_stats_aggregation_is_scheduler_agnostic PASSED [ 88%]
tests/test_review_stats.py::test_review_stats_includes_rapid_retry_reviews PASSED [ 88%]
...
tests/test_shell_proxy.py::test_review_stats_summary_proxy_returns_json PASSED [ 99%]

=================================== FAILURES ===================================
_______ test_import_stores_new_result_without_overwriting_history ________
    ...
    history = client.get(_history_url(SECTION_ORIGINS_ID))
    rows = history.json()["rows"]
    assert len(rows) == 3
>   assert rows[0]["score"] == 5  # most recent first
E   assert 4 == 5
tests/test_examinations.py:112: AssertionError

=========================== short test summary info ============================
FAILED tests/test_examinations.py::test_import_stores_new_result_without_overwriting_history
================== 1 failed, 268 passed, 4 warnings in 32.87s ==================

$ docker exec atlas-playwright npx playwright test 03_Application/EssayCards/tests/ui/ \
    --config=02_Platform/Atlas_Shell/playwright.config.ts --reporter=list
Running 3 tests using 1 worker

  ✓  1 …review_stats.spec.ts:21:5 › Stats nav entry navigates to the review stats page (363ms)
  ✓  2 …review_stats.spec.ts:30:5 › review stats page shows three window cards in Day, Week, Month order (351ms)
  ✓  3 …review_stats.spec.ts:42:5 › each window card shows a recall rate and a full grade breakdown (501ms)

  3 passed (1.9s)
```

## Failure Analysis

All scenarios in `10_test_spec.md` for this sprint (Sprint11_ReviewStats) passed —
7 backend scenarios and the 1 `[UI]` scenario (covered by 3 Playwright test cases).

One unrelated pre-existing failure was observed and independently verified, not
taken on faith from the implementer's note:
`tests/test_examinations.py::test_import_stores_new_result_without_overwriting_history`
fails with `assert 4 == 5`. Root cause: the test hardcodes an imported
`examined_at` of `"2026-08-28T14:30:00Z"` and asserts that row (`score=5`) is
"most recent first" in the history, while `tests/fixtures.sql` seeds a sibling
row for the same section at `now() - interval '2 days'` (`score=4`). As of
today (2026-09-26), `now() - 2 days` = 2026-09-24, which is later than the
hardcoded 2026-08-28 date, so the fixture row now sorts first — a date-based
flake caused by the calendar advancing past the test's hardcoded date, not by
anything touched in this sprint. `10_test_spec.md`'s Scope section explicitly
excludes examinations from this sprint, `review_stats.py`/`test_review_stats.py`
never touch `section_examinations`, and this test predates Sprint11 in the repo
history. Per the sprint's guidance, this does not block a `TESTS_PASSING`
verdict for this sprint's own scenarios, but it is flagged here since it will
recur on every run until `test_examinations.py` is updated to use a relative
date (e.g. `now() - interval '1 day'`) instead of a hardcoded absolute one.

## Required Action

Proceed to `/sprint-close` for Sprint11_ReviewStats. Separately (out of this
sprint's scope), file a fix for the pre-existing `test_examinations.py` date-based
flake so it does not keep failing as the calendar advances.
