# Test Report — Notifications — Sprint01_Immediate_Notify

**Verdict:** TESTS_PASSING
**Date:** 2026-04-15
**Fix iteration:** 1

## Results

| Scenario | Test | Type | Status | Failure reason |
|----------|------|------|--------|----------------|
| Happy path: immediate send succeeds | `test_immediate_send_happy_path` | backend | PASS | — |
| Happy path: explicit source field | `test_immediate_send_explicit_source` | backend | PASS | — |
| Error: no default device registered | `test_immediate_send_no_device` | backend | PASS | — |
| Error: FCM dispatch fails | `test_immediate_send_fcm_failure` | backend | PASS | — |
| Validation: missing required fields | `test_immediate_send_missing_body_field` | backend | PASS | — |

## Test output

```
============================= test session starts ==============================
platform linux -- Python 3.11.15, pytest-9.0.3, pluggy-1.6.0
collected 5 items

tests/test_immediate_send.py::test_immediate_send_happy_path PASSED      [ 20%]
tests/test_immediate_send.py::test_immediate_send_explicit_source PASSED [ 40%]
tests/test_immediate_send.py::test_immediate_send_no_device PASSED       [ 60%]
tests/test_immediate_send.py::test_immediate_send_fcm_failure PASSED     [ 80%]
tests/test_immediate_send.py::test_immediate_send_missing_body_field PASSED [100%]

5 passed in 0.70s
```

## Failure Analysis

All scenarios passed.

## Required Action

Invoke `/sprint-close` to complete the sprint.
