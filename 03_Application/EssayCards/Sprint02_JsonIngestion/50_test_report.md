# Test Report — EssayCards — Sprint02_JsonIngestion

**Verdict:** TESTS_PASSING
**Date:** 2026-08-28
**Fix iteration:** 0

## Results

| Scenario | Test | Type | Status | Failure reason |
|----------|------|------|--------|----------------|
| Ingest — creates a new essay via JSON | test_ingest_json_creates_new_essay | backend | PASS | — |
| Ingest — upserts onto an existing essay by slug and preserves review state | test_ingest_json_upserts_onto_existing_essay_preserves_review_state | backend | PASS | — |
| Ingest — order_index follows payload array order | test_ingest_json_order_index_follows_payload_array_order | backend | PASS | — |
| Ingest — rejects a malformed payload before any write (all-or-nothing rollback) | test_ingest_json_rejects_malformed_payload_writes_nothing | backend | PASS | — |
| Ingest — rejects duplicate anchor_slug within payload | test_ingest_json_rejects_duplicate_anchor_slug_in_payload | backend | PASS | — |
| Ingest — rejects duplicate card id within payload | test_ingest_json_rejects_duplicate_card_id_in_payload | backend | PASS | — |
| Ingest — rejects a card id colliding with an existing card in a different section | test_ingest_json_rejects_card_id_collision_with_different_existing_section | backend | PASS | — |
| Ingest — rejects an unparsable JSON body | test_ingest_json_rejects_unparsable_json_body | backend | PASS | — |
| Ingest — rejects a payload missing a required top-level field | test_ingest_json_rejects_missing_required_top_level_field | backend | PASS | — |
| Ingest — rejects an empty sections array | test_ingest_json_rejects_empty_sections_array | backend | PASS | — |
| [UI — manual] Add / Update Essay view submits JSON and shows a success summary | — | manual | MANUAL | not applicable — manual verification scenario, no automated UI infrastructure for EssayCards per design |
| [UI — manual] Add / Update Essay view shows an inline error without clearing the textarea | — | manual | MANUAL | not applicable — manual verification scenario, no automated UI infrastructure for EssayCards per design |
| [UI — manual] Essay picker lists more than one ingested essay | — | manual | MANUAL | not applicable — manual verification scenario, no automated UI infrastructure for EssayCards per design |

### Sprint01 regression suite (36 tests) — unchanged, not part of 10_test_spec.md scenarios but required to pass as the refactor's regression gate

| File | Tests | Status |
|------|-------|--------|
| tests/test_essays.py | 4 | PASS |
| tests/test_flashcards.py | 11 | PASS |
| tests/test_ingest.py | 8 | PASS |
| tests/test_scheduling.py | 11 | PASS |
| tests/test_shell_proxy.py | 2 | PASS |

## Test output

```
============================= test session starts ==============================
platform linux -- Python 3.12.14, pytest-9.1.1, pluggy-1.6.0 -- /usr/local/bin/python3.12
collected 46 items

tests/test_essays.py::test_list_essays_returns_dataset PASSED            [  2%]
tests/test_essays.py::test_list_essays_empty PASSED                      [  4%]
tests/test_essays.py::test_essay_detail_returns_ordered_sections PASSED  [  6%]
tests/test_essays.py::test_essay_detail_not_found PASSED                 [  8%]
tests/test_flashcards.py::test_due_no_params_returns_system_wide PASSED  [ 10%]
tests/test_flashcards.py::test_due_scoped_to_essay PASSED                [ 13%]
tests/test_flashcards.py::test_due_scoped_to_section PASSED              [ 15%]
tests/test_flashcards.py::test_due_section_without_essay_rejected PASSED [ 17%]
tests/test_flashcards.py::test_due_excludes_not_yet_due_cards PASSED     [ 19%]
tests/test_flashcards.py::test_due_empty_result PASSED                   [ 21%]
tests/test_flashcards.py::test_review_again_schedules_five_seconds PASSED [ 23%]
tests/test_flashcards.py::test_review_good_first_time_uses_floor PASSED  [ 26%]
tests/test_flashcards.py::test_review_good_repeat_uses_doubled_elapsed PASSED [ 28%]
tests/test_flashcards.py::test_review_invalid_grade_rejected PASSED      [ 30%]
tests/test_flashcards.py::test_review_unknown_flashcard_not_found PASSED [ 32%]
tests/test_ingest.py::test_ingest_creates_essay_sections_and_cards PASSED [ 34%]
tests/test_ingest.py::test_reingest_preserves_review_state PASSED        [ 36%]
tests/test_ingest.py::test_reingest_updates_changed_text_only PASSED     [ 39%]
tests/test_ingest.py::test_ingest_missing_anchor_rejected PASSED         [ 41%]
tests/test_ingest.py::test_ingest_malformed_flashcards_yaml_rejected PASSED [ 43%]
tests/test_ingest.py::test_ingest_multiple_flashcards_blocks_rejected PASSED [ 45%]
tests/test_ingest.py::test_ingest_duplicate_card_key_rejected PASSED     [ 47%]
tests/test_ingest.py::test_ingest_duplicate_anchor_slug_rejected PASSED  [ 50%]
tests/test_ingest_endpoint.py::test_ingest_json_creates_new_essay PASSED [ 52%]
tests/test_ingest_endpoint.py::test_ingest_json_upserts_onto_existing_essay_preserves_review_state PASSED [ 54%]
tests/test_ingest_endpoint.py::test_ingest_json_order_index_follows_payload_array_order PASSED [ 56%]
tests/test_ingest_endpoint.py::test_ingest_json_rejects_malformed_payload_writes_nothing PASSED [ 58%]
tests/test_ingest_endpoint.py::test_ingest_json_rejects_duplicate_anchor_slug_in_payload PASSED [ 60%]
tests/test_ingest_endpoint.py::test_ingest_json_rejects_duplicate_card_id_in_payload PASSED [ 63%]
tests/test_ingest_endpoint.py::test_ingest_json_rejects_card_id_collision_with_different_existing_section PASSED [ 65%]
tests/test_ingest_endpoint.py::test_ingest_json_rejects_unparsable_json_body PASSED [ 67%]
tests/test_ingest_endpoint.py::test_ingest_json_rejects_missing_required_top_level_field PASSED [ 69%]
tests/test_ingest_endpoint.py::test_ingest_json_rejects_empty_sections_array PASSED [ 71%]
tests/test_scheduling.py::test_again_is_flat_five_seconds_regardless_of_last_reviewed_at PASSED [ 73%]
tests/test_scheduling.py::test_first_time_review_uses_floor_only[hard] PASSED [ 76%]
tests/test_scheduling.py::test_first_time_review_uses_floor_only[good] PASSED [ 78%]
tests/test_scheduling.py::test_first_time_review_uses_floor_only[easy] PASSED [ 80%]
tests/test_scheduling.py::test_repeat_review_doubles_elapsed_when_it_exceeds_floor[hard] PASSED [ 82%]
tests/test_scheduling.py::test_repeat_review_doubles_elapsed_when_it_exceeds_floor[good] PASSED [ 84%]
tests/test_scheduling.py::test_repeat_review_doubles_elapsed_when_it_exceeds_floor[easy] PASSED [ 86%]
tests/test_scheduling.py::test_repeat_review_uses_floor_when_it_exceeds_doubled_elapsed[hard] PASSED [ 89%]
tests/test_scheduling.py::test_repeat_review_uses_floor_when_it_exceeds_doubled_elapsed[good] PASSED [ 91%]
tests/test_scheduling.py::test_repeat_review_uses_floor_when_it_exceeds_doubled_elapsed[easy] PASSED [ 93%]
tests/test_scheduling.py::test_invalid_grade_raises_value_error PASSED   [ 95%]
tests/test_shell_proxy.py::test_essaycards_proxy_returns_json PASSED     [ 97%]
tests/test_shell_proxy.py::test_shell_serves_app_at_basepath PASSED      [100%]

======================== 46 passed, 4 warnings in 2.69s ========================
```

Confirmatory split runs (same container, same session):
```
$ pytest tests/test_essays.py tests/test_flashcards.py tests/test_ingest.py tests/test_scheduling.py tests/test_shell_proxy.py -q
36 passed, 4 warnings in 2.56s

$ pytest tests/test_ingest_endpoint.py -q
10 passed, 3 warnings in 1.26s
```

No `tests/ui/` directory exists for EssayCards (confirmed via `ls`), consistent with 10_test_spec.md's scope note ("no automated UI test infrastructure is set up for EssayCards") and the 3 scenarios being explicitly labeled `[UI — manual]`. Playwright step (Step 2b) was skipped — not applicable, not a failure.

## Failure Analysis

All scenarios passed. The full suite is 46/46 green: all 10 new `POST /api/essaycards/essays/ingest` scenarios from 10_test_spec.md pass, and — critically for this refactor sprint — all 36 Sprint01 regression tests (`test_essays.py`, `test_flashcards.py`, `test_ingest.py`, `test_scheduling.py`, `test_shell_proxy.py`) pass unchanged with zero test-file modifications, confirming `backend.ingest.upsert_document()` extraction did not alter the markdown CLI path's behavior.

The 3 `[UI — manual]` scenarios (Add/Update Essay success summary, inline error without clearing textarea, essay picker with multiple essays) are noted as MANUAL per design — EssayCards has no `tests/ui/` directory and no automated UI test infrastructure, which matches 10_test_spec.md's explicit scope statement. These are not failures and require human verification before sprint close.

## Required Action

Proceed to `/sprint-close` after a human manually verifies the 3 `[UI — manual]` scenarios (Add/Update Essay submit-success, inline-error-preserves-textarea, and multi-essay picker listing).
