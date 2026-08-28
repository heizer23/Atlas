# Test Report — EssayCards — Sprint01_Core

**Verdict:** TESTS_PASSING
**Date:** 2026-08-28
**Fix iteration:** 0

## Results

| Scenario | Test | Type | Status | Failure reason |
|----------|------|------|--------|----------------|
| List essays returns Dataset | test_list_essays_returns_dataset | backend | PASS | — |
| List essays empty | test_list_essays_empty | backend | PASS | — |
| Essay detail returns ordered sections | test_essay_detail_returns_ordered_sections | backend | PASS | — |
| Essay detail not found | test_essay_detail_not_found | backend | PASS | — |
| Due flashcards — no params returns system-wide queue | test_due_no_params_returns_system_wide | backend | PASS | — |
| Due flashcards — scoped to essay | test_due_scoped_to_essay | backend | PASS | — |
| Due flashcards — scoped to essay and section | test_due_scoped_to_section | backend | PASS | — |
| Due flashcards — section_id without essay_id is rejected | test_due_section_without_essay_rejected | backend | PASS | — |
| Due flashcards — excludes not-yet-due cards | test_due_excludes_not_yet_due_cards | backend | PASS | — |
| Due flashcards — empty result when nothing due | test_due_empty_result | backend | PASS | — |
| Review — grade again schedules five seconds out | test_review_again_schedules_five_seconds | backend | PASS | — |
| Review — grade good on a never-reviewed card uses the floor | test_review_good_first_time_uses_floor | backend | PASS | — |
| Review — grade good on a repeat review doubles elapsed time | test_review_good_repeat_uses_doubled_elapsed | backend | PASS | — |
| Review — invalid grade rejected | test_review_invalid_grade_rejected | backend | PASS | — |
| Review — unknown flashcard not found | test_review_unknown_flashcard_not_found | backend | PASS | — |
| Ingestion — creates essay, sections, and flashcards due immediately | test_ingest_creates_essay_sections_and_cards | backend | PASS | — |
| Ingestion — re-ingesting an unchanged file preserves review state | test_reingest_preserves_review_state | backend | PASS | — |
| Ingestion — re-ingesting edited text updates content only | test_reingest_updates_changed_text_only | backend | PASS | — |
| Ingestion — missing anchor slug aborts with no rows written | test_ingest_missing_anchor_rejected | backend | PASS | — |
| Ingestion — malformed flashcards YAML aborts with no rows written | test_ingest_malformed_flashcards_yaml_rejected | backend | PASS | — |
| Ingestion — multiple flashcards blocks in one section aborts | test_ingest_multiple_flashcards_blocks_rejected | backend | PASS | — |
| Ingestion — duplicate card id within file aborts | test_ingest_duplicate_card_key_rejected | backend | PASS | — |
| [UI — manual] Reader view renders sections in order with a Review this section action | — | manual | MANUAL | requires human verification |
| [UI — manual] Review session flip-and-grade flow | — | manual | MANUAL | requires human verification |
| [UI — manual] Jump to passage navigates to the exact section | — | manual | MANUAL | requires human verification |
| [UI — manual] Global "Due for review" entry point surfaces cards from all sections | — | manual | MANUAL | requires human verification |

Supporting direct scheduling-formula tests (not individually enumerated as spec scenarios but explicitly in-scope per `10_test_spec.md` §Scope) all passed: `test_again_is_flat_five_seconds_regardless_of_last_reviewed_at`, `test_first_time_review_uses_floor_only[hard/good/easy]`, `test_repeat_review_doubles_elapsed_when_it_exceeds_floor[hard/good/easy]`, `test_repeat_review_uses_floor_when_it_exceeds_doubled_elapsed[hard/good/easy]`, `test_invalid_grade_raises_value_error`. Two shell-proxy integration tests (`test_essaycards_proxy_returns_json`, `test_shell_serves_app_at_basepath`) and one extra ingestion edge case beyond the spec (`test_ingest_duplicate_anchor_slug_rejected`) also passed — extra coverage, not required by the spec.

No `tests/ui/` directory exists in the component; this is expected since all UI scenarios in `10_test_spec.md` are marked `[UI — manual]` (no automated UI test infrastructure was scoped for this sprint). Step 2b (Playwright) was therefore skipped, consistent with instructions.

## Test output

```
============================= test session starts ==============================
platform linux -- Python 3.12.14, pytest-9.1.1, pluggy-1.6.0 -- /usr/local/bin/python3.12
cachedir: .pytest_cache
rootdir: /app
configfile: pyproject.toml
plugins: asyncio-1.4.0, anyio-4.14.2
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 36 items

tests/test_essays.py::test_list_essays_returns_dataset PASSED            [  2%]
tests/test_essays.py::test_list_essays_empty PASSED                      [  5%]
tests/test_essays.py::test_essay_detail_returns_ordered_sections PASSED  [  8%]
tests/test_essays.py::test_essay_detail_not_found PASSED                 [ 11%]
tests/test_flashcards.py::test_due_no_params_returns_system_wide PASSED  [ 13%]
tests/test_flashcards.py::test_due_scoped_to_essay PASSED                [ 16%]
tests/test_flashcards.py::test_due_scoped_to_section PASSED              [ 19%]
tests/test_flashcards.py::test_due_section_without_essay_rejected PASSED [ 22%]
tests/test_flashcards.py::test_due_excludes_not_yet_due_cards PASSED     [ 25%]
tests/test_flashcards.py::test_due_empty_result PASSED                   [ 27%]
tests/test_flashcards.py::test_review_again_schedules_five_seconds PASSED [ 30%]
tests/test_flashcards.py::test_review_good_first_time_uses_floor PASSED  [ 33%]
tests/test_flashcards.py::test_review_good_repeat_uses_doubled_elapsed PASSED [ 36%]
tests/test_flashcards.py::test_review_invalid_grade_rejected PASSED      [ 38%]
tests/test_flashcards.py::test_review_unknown_flashcard_not_found PASSED [ 41%]
tests/test_ingest.py::test_ingest_creates_essay_sections_and_cards PASSED [ 44%]
tests/test_ingest.py::test_reingest_preserves_review_state PASSED        [ 47%]
tests/test_ingest.py::test_reingest_updates_changed_text_only PASSED     [ 50%]
tests/test_ingest.py::test_ingest_missing_anchor_rejected PASSED         [ 52%]
tests/test_ingest.py::test_ingest_malformed_flashcards_yaml_rejected PASSED [ 55%]
tests/test_ingest.py::test_ingest_multiple_flashcards_blocks_rejected PASSED [ 58%]
tests/test_ingest.py::test_ingest_duplicate_card_key_rejected PASSED     [ 61%]
tests/test_ingest.py::test_ingest_duplicate_anchor_slug_rejected PASSED  [ 63%]
tests/test_scheduling.py::test_again_is_flat_five_seconds_regardless_of_last_reviewed_at PASSED [ 66%]
tests/test_scheduling.py::test_first_time_review_uses_floor_only[hard] PASSED [ 69%]
tests/test_scheduling.py::test_first_time_review_uses_floor_only[good] PASSED [ 72%]
tests/test_scheduling.py::test_first_time_review_uses_floor_only[easy] PASSED [ 75%]
tests/test_scheduling.py::test_repeat_review_doubles_elapsed_when_it_exceeds_floor[hard] PASSED [ 77%]
tests/test_scheduling.py::test_repeat_review_doubles_elapsed_when_it_exceeds_floor[good] PASSED [ 80%]
tests/test_scheduling.py::test_repeat_review_doubles_elapsed_when_it_exceeds_floor[easy] PASSED [ 83%]
tests/test_scheduling.py::test_repeat_review_uses_floor_when_it_exceeds_doubled_elapsed[hard] PASSED [ 86%]
tests/test_scheduling.py::test_repeat_review_uses_floor_when_it_exceeds_doubled_elapsed[good] PASSED [ 88%]
tests/test_scheduling.py::test_repeat_review_uses_floor_when_it_exceeds_doubled_elapsed[easy] PASSED [ 91%]
tests/test_scheduling.py::test_invalid_grade_raises_value_error PASSED   [ 94%]
tests/test_shell_proxy.py::test_essaycards_proxy_returns_json PASSED     [ 97%]
tests/test_shell_proxy.py::test_shell_serves_app_at_basepath PASSED      [100%]

=============================== warnings summary ===============================
tests/test_essays.py::test_list_essays_returns_dataset
  /app/backend/main.py:32: DeprecationWarning: on_event is deprecated, use lifespan event handlers instead.
tests/test_essays.py::test_list_essays_returns_dataset
  /app/tests/conftest.py:100: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
tests/test_flashcards.py::test_review_invalid_grade_rejected
  /usr/local/lib/python3.12/site-packages/httpx/_models.py:408: DeprecationWarning: Use 'content=<...>' to upload raw bytes/text content.

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 36 passed, 4 warnings in 2.50s ========================
```

## Failure Analysis

All scenarios passed. The 4 `[UI — manual]` scenarios (Reader view section ordering + "Review this section" action, review session flip-and-grade flow, "Jump to passage" navigation, and the global "Due for review" entry point) are explicitly out of automated scope for this sprint per `10_test_spec.md` §Scope and require human verification — they are not counted as failures.

## Required Action

Proceed to `/sprint-close` after a human performs the 4 manual UI verification scenarios listed above.
