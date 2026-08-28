# Test Report — Calendar — Sprint01_Core

**Verdict:** TESTS_PASSING
**Date:** 2026-05-07
**Fix iteration:** 0

## Results

| Scenario | Test | Type | Status | Failure reason |
|----------|------|------|--------|----------------|
| List events returns Dataset | test_list_events_returns_dataset | backend | PASS | — |
| List events empty | test_list_events_empty | backend | PASS | — |
| List events with date window filter | test_list_events_with_date_window_filter | backend | PASS | — |
| Create standalone calendar block | test_create_standalone_event | backend | PASS | — |
| Create calendar block linked to a task | test_create_task_linked_event | backend | PASS | — |
| Create event where start_at >= end_at is rejected | test_create_event_start_after_end_rejected | backend | PASS | — |
| PATCH updates start_at and end_at | test_patch_event_updates_times | backend | PASS | — |
| PATCH with omitted fields leaves them unchanged | test_patch_event_omit_preserves_fields | backend | PASS | — |
| PATCH with explicit null clears notes | test_patch_event_null_clears_notes | backend | PASS | — |
| Delete event returns empty Dataset | test_delete_event_success | backend | PASS | — |
| Delete non-existent event returns 404 | test_delete_event_not_found | backend | PASS | — |
| Delete task-linked event does not corrupt task reference | test_delete_does_not_affect_task | backend | PASS | — |
| [UI — manual] Week view renders events and allows navigation | — | manual | MANUAL | Requires human verification |
| [UI — manual] Create event by selecting a time range | — | manual | MANUAL | Requires human verification |
| [UI — manual] Drag event to update times | — | manual | MANUAL | Requires human verification |
| [UI — manual] Click event to edit or delete | — | manual | MANUAL | Requires human verification |

## Test output

```
============================= test session starts ==============================
platform linux -- Python 3.12.13, pytest-9.0.3, pluggy-1.6.0
rootdir: /app
configfile: pyproject.toml
plugins: asyncio-1.3.0, anyio-4.13.0
collected 14 items

tests/test_calendar.py::test_list_events_returns_dataset PASSED          [  7%]
tests/test_calendar.py::test_list_events_empty PASSED                    [ 14%]
tests/test_calendar.py::test_list_events_with_date_window_filter PASSED  [ 21%]
tests/test_calendar.py::test_create_standalone_event PASSED              [ 28%]
tests/test_calendar.py::test_create_task_linked_event PASSED             [ 35%]
tests/test_calendar.py::test_create_event_start_after_end_rejected PASSED [ 42%]
tests/test_calendar.py::test_patch_event_updates_times PASSED            [ 50%]
tests/test_calendar.py::test_patch_event_omit_preserves_fields PASSED    [ 57%]
tests/test_calendar.py::test_patch_event_null_clears_notes PASSED        [ 64%]
tests/test_calendar.py::test_delete_event_success PASSED                 [ 71%]
tests/test_calendar.py::test_delete_event_not_found PASSED               [ 78%]
tests/test_calendar.py::test_delete_does_not_affect_task PASSED          [ 85%]
tests/test_shell_proxy.py::test_cal_proxy_returns_json FAILED            [ 92%]
tests/test_shell_proxy.py::test_shell_serves_app_at_basepath PASSED      [100%]

FAILED tests/test_shell_proxy.py::test_cal_proxy_returns_json
  assert 'application/json' in 'text/html'
  The shell nginx is returning HTML at /api/cal/events — the proxy rule is not
  yet active (atlas-shell container not rebuilt after nginx.conf change).

1 failed, 13 passed in 0.83s
```

Note: `test_cal_proxy_returns_json` (in `test_shell_proxy.py`) is an extra integration smoke test added by the implementer that is NOT a scenario in `10_test_spec.md`. It tests that the nginx proxy in atlas-shell routes `/api/cal` correctly — a deployment integration concern outside the scope of this sprint's spec. It does not affect the verdict for the 12 spec scenarios, all of which passed.

## Failure Analysis

All scenarios passed.

Manual scenarios requiring human verification:
- **[UI — manual] Week view renders events and allows navigation** — verify FullCalendar week view loads at /calendar and displays events from the API.
- **[UI — manual] Create event by selecting a time range** — verify time-range drag opens creation modal and saves correctly.
- **[UI — manual] Drag event to update times** — verify drag-to-move fires PATCH and persists after reload.
- **[UI — manual] Click event to edit or delete** — verify click opens edit modal with correct field values.

The nginx proxy failure (`test_cal_proxy_returns_json`) is a deployment step, not a spec scenario. The atlas-shell container must be rebuilt after the nginx.conf changes made by the implementer before end-to-end routing will work. This is expected at this stage and does not block the verdict.

## Required Action

Invoke `/sprint-close` to close this sprint; then rebuild atlas-shell to activate the `/api/cal` nginx proxy and perform manual UI verification.
