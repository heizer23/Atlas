# Test Report — EssayCards — Sprint03_Images

**Verdict:** TESTS_PASSING
**Date:** 2026-08-30
**Fix iteration:** 1

## Results

| Scenario | Test | Type | Status | Failure reason |
|----------|------|------|--------|----------------|
| Scan imports new staged images | test_scan_imports_new_images_and_downscales_oversized | backend | PASS | — |
| Scan is idempotent on a second run | test_scan_is_idempotent_on_second_run | backend | PASS | — |
| Scan skips a non-image file and keeps going | test_scan_skips_non_image_file_and_continues | backend | PASS | — |
| Scan skips an oversized GIF | test_scan_skips_oversized_gif | backend | PASS | — |
| Scan resolves a slug collision | test_scan_slug_collision_appends_hash_suffix | backend | PASS | — |
| Scan infrastructure failure returns an ApiError | test_scan_infra_failure_returns_api_error | backend | PASS | — |
| List images returns a Dataset newest first | test_list_images_returns_dataset_newest_first | backend | PASS | — |
| List images is valid when empty | test_list_images_empty_is_valid | backend | PASS | — |
| Get image serves bytes with an immutable cache header | test_get_image_serves_bytes_with_immutable_cache | backend | PASS | — |
| Get image with an unknown slug returns 404 | test_get_image_unknown_slug_returns_404 | backend | PASS | — |
| Get image when the row exists but the file is missing returns 404 | test_get_image_row_present_file_missing_returns_404 | backend | PASS | — |
| [UI] Review card renders a Markdown image in the answer | (none) | UI | UNTESTED | No `tests/ui/` directory exists in the component and no Playwright/UI execution infrastructure is present for EssayCards. Per R-PRO-BP-01 §10 this `[UI]` scenario should be relabelled `[UI — manual]` until UI execution infra exists. Recorded as untested, not passing. |
| [UI — manual] Images view: Copy Markdown button copies the snippet | (none) | manual | MANUAL | Untested by design — clipboard reads are unreliable under automated browsers; requires human verification. |

Backend totals: 11 scenarios — 11 PASS, 0 FAIL. Full suite: 74 collected, 73 passed, 1 failed (the single failure is the pre-existing, unrelated wall-clock fixture fragility in `test_examinations.py`, see Failure Analysis §2 — it does not affect the Sprint03 verdict).

## Test output

```
$ docker exec atlas-essaycards-test pytest tests/ -v

tests/test_images.py::test_scan_imports_new_images_and_downscales_oversized PASSED [ 44%]
tests/test_images.py::test_scan_is_idempotent_on_second_run PASSED       [ 45%]
tests/test_images.py::test_scan_skips_non_image_file_and_continues PASSED [ 47%]
tests/test_images.py::test_scan_skips_oversized_gif PASSED               [ 48%]
tests/test_images.py::test_scan_slug_collision_appends_hash_suffix PASSED [ 50%]
tests/test_images.py::test_scan_infra_failure_returns_api_error PASSED   [ 51%]
tests/test_images.py::test_list_images_returns_dataset_newest_first PASSED [ 52%]
tests/test_images.py::test_list_images_empty_is_valid PASSED             [ 54%]
tests/test_images.py::test_get_image_serves_bytes_with_immutable_cache PASSED [ 55%]
tests/test_images.py::test_get_image_unknown_slug_returns_404 PASSED     [ 56%]
tests/test_images.py::test_get_image_row_present_file_missing_returns_404 PASSED [ 58%]

(essays / flashcards / ingest / ingest_endpoint / scheduling / shell_proxy: all pass)

tests/test_examinations.py::test_import_stores_new_result_without_overwriting_history FAILED [  9%]

=========================== short test summary info ============================
FAILED tests/test_examinations.py::test_import_stores_new_result_without_overwriting_history
=================== 1 failed, 73 passed, 4 warnings in 7.06s ===================
```

Pre-existing unrelated failure detail:

```
        history = client.get(_history_url(SECTION_ORIGINS_ID))
        assert history.status_code == 200
        rows = history.json()["rows"]
        assert len(rows) == 3
>       assert rows[0]["score"] == 5  # most recent first
E       assert 4 == 5
tests/test_examinations.py:103: AssertionError
```

## Failure Analysis

All 11 Sprint03 backend scenarios pass. The fix iteration 1 change to
`backend/import_images.py` resolved the `NoActiveSqlTransaction: SAVEPOINT can only be
used in transaction blocks` failure that previously broke the four scan scenarios and,
transitively, `test_get_image_serves_bytes_with_immutable_cache`. The new
`_ensure_in_transaction(conn, cur)` helper issues `begin` only when the pooled
connection's `transaction_status` is `TRANSACTION_STATUS_IDLE` before each per-file
`savepoint import_one`, and `scan_staging` now ends with `conn.rollback()`. All scan,
list, and get-image scenarios now exercise their intended code paths and pass.

### 1. UI scenarios

- `[UI] Review card renders a Markdown image in the answer` — UNTESTED. EssayCards has
  no `tests/ui/` directory and no Playwright execution infrastructure. The spec labels
  this `[UI]` (not `[UI — manual]`); per R-PRO-BP-01 §10 it should be relabelled
  `[UI — manual]` until UI execution infra exists. Recorded as untested, not passing —
  this does not block the verdict.
- `[UI — manual] Copy Markdown button copies the snippet` — MANUAL, untested by design.
  Requires human verification that the clipboard contains exactly
  `![](/api/essaycards/images/<slug>)` after clicking **Copy Markdown**.

### 2. Pre-existing, unrelated: `test_examinations.py::test_import_stores_new_result_without_overwriting_history`

Not in Sprint03 scope and not caused by the images implementation. Wall-clock-dependent
test/fixture fragility: `tests/fixtures.sql` seeds section examination `5e000002` with
`examined_at = now() - interval '2 days'` (score 4), while the test posts a new
examination with a hard-coded `examined_at` of `2026-08-28T14:30:00Z` (score 5) and
asserts it sorts first. Run today (2026-08-30) at ~14:57 UTC, `now() - 2 days` is later
than `2026-08-28T14:30:00Z`, so the score-4 fixture row sorts first and `rows[0]["score"]`
is 4. The Sprint03 diff to `fixtures.sql` only appends image rows and does not touch the
examination rows. Fix belongs in `test_examinations.py` / the examination fixture (use a
relative or clearly-ordered timestamp), independent of this sprint's fix loop. This
failure does not change the Sprint03 verdict.

## Required Action

None for Sprint03 — all 11 backend scenarios pass; proceed to `/sprint-close`. Separately
(outside this sprint), repair the pre-existing time-relative failure in
`test_examinations.py::test_import_stores_new_result_without_overwriting_history`, and
consider relabelling the `[UI]` review-card scenario as `[UI — manual]` until EssayCards
has Playwright infrastructure.
