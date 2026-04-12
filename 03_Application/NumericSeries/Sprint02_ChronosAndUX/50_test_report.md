# Test Report — NumericSeries — Sprint02_ChronosAndUX

**Verdict:** TESTS_PASSING
**Date:** 2026-04-12
**Fix iteration:** 0

## Results

| Scenario | Test function | Status | Failure reason |
|----------|--------------|--------|----------------|
| Happy path — single entry inserted by name | `test_happy_path_single_entry_inserted_by_name` | PASS | — |
| Happy path — multiple entries inserted | `test_happy_path_multiple_entries_inserted` | PASS | — |
| Case-insensitive name match | `test_case_insensitive_name_match` | PASS | — |
| Series not found — label exists but no series record | `test_series_not_found_label_exists_no_series_record` | PASS | — |
| Series not found — label does not exist at all | `test_series_not_found_label_does_not_exist` | PASS | — |
| Invalid value — non-finite number rejected | `test_invalid_value_null_rejected` | PASS | — |
| Invalid timestamp rejected | `test_invalid_timestamp_rejected` | PASS | — |

## Test output

```
tests/test_chronos_write.py::test_happy_path_single_entry_inserted_by_name PASSED
tests/test_chronos_write.py::test_happy_path_multiple_entries_inserted PASSED
tests/test_chronos_write.py::test_case_insensitive_name_match PASSED
tests/test_chronos_write.py::test_series_not_found_label_exists_no_series_record PASSED
tests/test_chronos_write.py::test_series_not_found_label_does_not_exist PASSED
tests/test_chronos_write.py::test_invalid_value_null_rejected PASSED
tests/test_chronos_write.py::test_invalid_timestamp_rejected PASSED

7 passed, 2 warnings in 0.66s
```

Warnings are FastAPI deprecation notices for `on_event` — not test failures, no action required.

## Failure Analysis

All scenarios passed.

## Required Action

Sprint is ready for `/sprint-close`.
