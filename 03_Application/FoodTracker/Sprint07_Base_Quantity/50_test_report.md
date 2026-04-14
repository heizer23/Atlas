# Test Report — FoodTracker — Sprint07_Base_Quantity

**Verdict:** TESTS_PASSING
**Date:** 2026-04-14
**Fix iteration:** 1

## Results

| Scenario | Test function | Status | Failure reason |
|----------|--------------|--------|----------------|
| [Backend] Intake with base_quantity scales macros proportionally | `test_intake_with_base_quantity_scales_macros_proportionally` | PASS | — |
| [Backend] Intake without base_quantity stores absolute values with base_quantity 100 | `test_intake_without_base_quantity_stores_absolute_with_base_quantity_100` | PASS | — |
| [Backend] Intake with invalid base_quantity returns VALIDATION_ERROR | `test_intake_with_invalid_base_quantity_returns_validation_error` | PASS | — |
| [Backend] Entry detail GET returns base_quantity as non-null float | `test_entry_detail_returns_base_quantity_as_non_null_float` | PASS | — |
| [Backend] Entry detail GET returns base_quantity 100 for legacy-backfilled row | `test_entry_detail_returns_base_quantity_100_for_legacy_backfilled_row` | PASS | — |
| [Backend] PUT entry accepts and stores updated base_quantity | `test_put_entry_accepts_and_stores_updated_base_quantity` | PASS | — |
| [Backend] PUT entry without base_quantity defaults to 100 | `test_put_entry_without_base_quantity_defaults_to_100` | PASS | — |
| [Backend] Copy entry preserves base_quantity | `test_copy_entry_preserves_base_quantity` | PASS | — |
| [UI — manual] Entry detail always shows Base quantity field | MISSING (manual) | MISSING | UI — manual scenario; no automated test expected |
| [UI — manual] Changing Base quantity rescales macro fields proportionally | MISSING (manual) | MISSING | UI — manual scenario; no automated test expected |

## Test output

```
============================= test session starts ==============================
platform linux -- Python 3.11.15, pytest-9.0.3, pluggy-1.6.0 -- /usr/local/bin/python3.11
collected 25 items

tests/test_sprint06.py::test_intake_with_quantity_g_scales_macros_proportionally PASSED [  4%]
tests/test_sprint06.py::test_intake_without_quantity_g_stores_absolute_values PASSED [  8%]
tests/test_sprint06.py::test_intake_with_invalid_quantity_g_returns_validation_error PASSED [ 12%]
tests/test_sprint06.py::test_intake_with_negative_quantity_g_returns_validation_error PASSED [ 16%]
tests/test_sprint06.py::test_cross_field_checks_apply_to_per_100g_values_before_scaling PASSED [ 20%]
tests/test_sprint06.py::test_entry_detail_get_includes_quantity_g PASSED [ 24%]
tests/test_sprint06.py::test_entry_detail_get_returns_null_quantity_g_for_legacy_row PASSED [ 28%]
tests/test_sprint06.py::test_put_entry_accepts_and_stores_updated_quantity_g PASSED [ 32%]
tests/test_sprint06.py::test_copy_entry_preserves_quantity_g PASSED      [ 36%]
tests/test_sprint06.py::test_copy_entry_with_null_quantity_g_preserves_null PASSED [ 40%]
tests/test_sprint06.py::test_report_includes_alcohol_g_total_in_year_scope PASSED [ 44%]
tests/test_sprint06.py::test_report_includes_alcohol_g_total_in_all_time_scope PASSED [ 48%]
tests/test_sprint06.py::test_report_includes_avg_columns_for_week_scope PASSED [ 52%]
tests/test_sprint06.py::test_report_includes_avg_columns_for_month_scope PASSED [ 56%]
tests/test_sprint06.py::test_report_does_not_include_avg_columns_for_all_time_scope PASSED [ 60%]
tests/test_sprint06.py::test_alcohol_g_avg_cumulative_average_is_correct PASSED [ 64%]
tests/test_sprint07.py::test_intake_with_base_quantity_scales_macros_proportionally PASSED [ 68%]
tests/test_sprint07.py::test_intake_without_base_quantity_stores_absolute_with_base_quantity_100 PASSED [ 72%]
tests/test_sprint07.py::test_intake_with_invalid_base_quantity_returns_validation_error PASSED [ 76%]
tests/test_sprint07.py::test_intake_with_negative_base_quantity_returns_validation_error PASSED [ 80%]
tests/test_sprint07.py::test_entry_detail_returns_base_quantity_as_non_null_float PASSED [ 84%]
tests/test_sprint07.py::test_entry_detail_returns_base_quantity_100_for_legacy_backfilled_row PASSED [ 88%]
tests/test_sprint07.py::test_put_entry_accepts_and_stores_updated_base_quantity PASSED [ 92%]
tests/test_sprint07.py::test_put_entry_without_base_quantity_defaults_to_100 PASSED [ 96%]
tests/test_sprint07.py::test_copy_entry_preserves_base_quantity PASSED   [100%]

======================== 25 passed, 2 warnings in 1.55s ========================
```

## Failure Analysis

All scenarios passed.

The two `[UI — manual]` scenarios have no automated test functions; this is expected per spec — they are labelled `[UI — manual]` and their absence is not treated as MISSING.

Note: The test container's `ATLAS_PG_USER` and `ATLAS_PG_PASSWORD` environment variables were set to empty strings (the `.env` values were not available when the container was started). Tests were run by passing `DATABASE_URL=postgresql://atlas:change-me@atlas-postgres/atlas_test` explicitly via `docker exec -e`. The test stack should be restarted with the correct environment so the container-native credentials are populated.

## Required Action

All backend scenarios pass; the sprint is ready for `/sprint-close` (two `[UI — manual]` scenarios are deferred to manual review by the human gate).
