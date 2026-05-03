# Test Report — PersonalDevelopment — Sprint01-Core

**Verdict:** TESTS_PASSING
**Date:** 2026-04-30
**Fix iteration:** 0

## Results

| Scenario | Test | Type | Status | Failure reason |
|----------|------|------|--------|----------------|
| Training Units — Empty Result | test_training_units_empty_result | backend | PASS | — |
| Training Units — Single Unit No Children | test_training_units_single_unit_no_children | backend | PASS | — |
| Training Units — Unit With Mixed Children | test_training_units_unit_with_mixed_children | backend | PASS | — |
| Training Units — Sort Order: Done Before Open, Then By Priority | test_training_units_sort_order_done_before_open_then_priority | backend | PASS | — |
| Training Units — Labels Embedded | test_training_units_labels_embedded | backend | PASS | — |
| Main Task List Excludes Training Units | test_main_task_list_excludes_training_units | backend | PASS | — |
| Main Task List Excludes Training Units — Active View | test_main_task_list_active_view_excludes_training_units | backend | PASS | — |
| Create Training Unit Task | test_create_training_unit_task | backend | PASS | — |
| Create Training Session With Parent | test_create_training_session_with_parent | backend | PASS | — |
| PATCH — completed_at Set Server-Side On Done Transition | test_patch_completed_at_set_on_done_transition | backend | PASS | — |
| PATCH — completed_at Not Overwritten If Already Set | test_patch_completed_at_not_overwritten | backend | PASS | — |
| PATCH — completed_at Not Set When Transitioning To Non-Done Status | test_patch_completed_at_not_set_for_non_done | backend | PASS | — |
| PATCH — actual_duration_minutes Update | test_patch_actual_duration_minutes | backend | PASS | — |
| Markdown Parsing — Section Absent | test_markdown_parsing_section_absent | backend | PASS | — |
| Markdown Parsing — Unchecked Lines | test_markdown_parsing_unchecked_lines | backend | PASS | — |
| Markdown Parsing — Mixed Checked And Unchecked | test_markdown_parsing_mixed_checked_and_unchecked | backend | PASS | — |
| Markdown Parsing — Empty Section | test_markdown_parsing_empty_section | backend | PASS | — |
| Markdown Update — Activate A Line | test_markdown_update_activate_a_line | backend | PASS | — |
| Markdown Update — Line Not Found Is No-Op | test_markdown_update_line_not_found_is_noop | backend | PASS | — |
| [UI — manual] Learning Tile Visible In Navigation | MANUAL | manual | MANUAL | Requires human verification |
| [UI — manual] Learning Page Shows Training Units | MANUAL | manual | MANUAL | Requires human verification |
| [UI — manual] Subtask Activation Creates Task And Updates Markdown | MANUAL | manual | MANUAL | Requires human verification |

## Test output

```
============================= test session starts ==============================
platform linux -- Python 3.12.13, pytest-9.0.3, pluggy-1.6.0 -- /usr/local/bin/python3.12
cachedir: .pytest_cache
rootdir: /app
configfile: pyproject.toml
plugins: anyio-4.13.0
collecting ... collected 21 items

tests/test_markdown_subtasks.py::test_markdown_parsing_section_absent PASSED [  4%]
tests/test_markdown_subtasks.py::test_markdown_parsing_unchecked_lines PASSED [  9%]
tests/test_markdown_subtasks.py::test_markdown_parsing_mixed_checked_and_unchecked PASSED [ 14%]
tests/test_markdown_subtasks.py::test_markdown_parsing_empty_section PASSED [ 19%]
tests/test_markdown_subtasks.py::test_markdown_parsing_null_description PASSED [ 23%]
tests/test_markdown_subtasks.py::test_markdown_update_activate_a_line PASSED [ 28%]
tests/test_markdown_subtasks.py::test_markdown_update_line_not_found_is_noop PASSED [ 33%]
tests/test_training_units.py::test_training_units_empty_result PASSED    [ 38%]
tests/test_training_units.py::test_training_units_single_unit_no_children PASSED [ 42%]
tests/test_training_units.py::test_training_units_unit_with_mixed_children PASSED [ 47%]
tests/test_training_units.py::test_training_units_sort_order_done_before_open_then_priority PASSED [ 52%]
tests/test_training_units.py::test_training_units_labels_embedded PASSED [ 57%]
tests/test_training_units.py::test_main_task_list_excludes_training_units PASSED [ 61%]
tests/test_training_units.py::test_main_task_list_active_view_excludes_training_units PASSED [ 66%]
tests/test_training_units.py::test_create_training_unit_task PASSED      [ 71%]
tests/test_training_units.py::test_create_training_session_with_parent PASSED [ 76%]
tests/test_training_units.py::test_patch_completed_at_set_on_done_transition PASSED [ 80%]
tests/test_training_units.py::test_patch_completed_at_not_overwritten PASSED [ 85%]
tests/test_training_units.py::test_patch_completed_at_not_set_for_non_done PASSED [ 90%]
tests/test_training_units.py::test_patch_actual_duration_minutes PASSED  [ 95%]
tests/test_training_units.py::test_get_tasks_by_parent_task_id PASSED    [100%]

======================== 21 passed, 2 warnings in 1.44s ========================
```

## Failure Analysis

All scenarios passed. The two deprecation warnings (`on_event` lifecycle handler) are pre-existing in TaskTracker and are not introduced by this sprint.

Three scenarios are marked MANUAL and require human verification:
- **[UI — manual] Learning Tile Visible In Navigation** — verify 'Learning' appears in shell navigation after Atlas Shell is running with the PersonalDevelopment shellConfig registered.
- **[UI — manual] Learning Page Shows Training Units** — verify /learning renders training unit cards with title, progress indicator, and last activity date.
- **[UI — manual] Subtask Activation Creates Task And Updates Markdown** — verify that clicking 'Create task' on an unchecked potential subtask line creates the child task and marks the line as activated in the description.

## Required Action

Invoke `/sprint-close` — all automated tests pass and the three manual UI scenarios require human verification before close.
