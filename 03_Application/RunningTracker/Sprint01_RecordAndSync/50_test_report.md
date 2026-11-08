# Test Report — RunningTracker — Sprint01_RecordAndSync

**Verdict:** TESTS_PASSING
**Date:** 2026-11-08
**Fix iteration:** 0

## Results

Every automated scenario passed. Matching was by test name and semantics. Scenarios are grouped where several share a test file.

| Scenario | Test | Type | Status | Failure reason |
|----------|------|------|--------|----------------|
| Pairing: create token once, reuse, expired, lockout | test_pairing.py (4 tests) | backend | PASS | — |
| Revoked token, endpoints need token, no power on web, public-path 403 | test_pairing.py (4 tests) | backend | PASS | — |
| Shell proxy hides native routes | test_shell_proxy.py::test_native_routes_are_not_reachable_through_the_public_proxy | backend | PASS | — |
| Prepared run lifecycle, expired hidden | test_native_sync.py (2 tests) | backend | PASS | — |
| Begin idempotent, converts prepared, adopts revoked-device run | test_native_sync.py (3 tests) | backend | PASS | — |
| Sample upload idempotent, no overwrite, batch limit, rejected for complete, resume cursors | test_native_sync.py (5 tests) | backend | PASS | — |
| Finish verifies, gaps, count mismatch, inconsistent times, GPS-only | test_native_sync.py (5 tests) | backend | PASS | — |
| Ownership on every native call | test_native_sync.py::test_ownership_on_every_native_call | backend | PASS | — |
| Metrics golden vectors, pauses, recompute stable | test_metrics.py (9 tests) | backend | PASS | — |
| History list, detail/splits/series, comment PATCH, delete | test_web_api.py (5 tests) | backend | PASS | — |
| Devices/pairing no secrets, logs, schema idempotent | test_web_api.py (3 tests) | backend | PASS | — |
| Native lifecycle transitions (JVM) | RunLifecycleTest (4) | JVM | PASS | — |
| Native metrics match golden vectors (JVM) | RunMetricsTest (6) | JVM | PASS | — |
| Upload resume, ack-after-verified-finish, error handling (JVM) | UploadEngineTest (5), UploadPlannerPureTest (3) | JVM | PASS | — |
| Token storage never plaintext (JVM) | TokenStoreTest (4) | JVM | PASS | — |
| AtlasClient https-only, no leaks (JVM) | AtlasClientTest (8) | JVM | PASS | — |
| Sprint 01 behavior unchanged, v1 DB upgrade (JVM) | CaptureStoreTest (12), CaptureStoreV2Test (2), HeartRateParser/LocationMapper/PermissionLogic/ReconnectPolicy tests | JVM | PASS | — |
| [UI] History list shows sync state | running_web.spec.ts: history list shows sync state; history shows an empty state | UI | PASS | — |
| [UI] Run detail charts, splits, comment edit | running_web.spec.ts: run detail shows charts, splits and comment edit | UI | PASS | — |
| [UI] Pair phone code, QR, expiry | running_web.spec.ts: pair phone shows code, QR and expiry; revoke only on active devices | UI | PASS | — |
| [UI] Prepared runs on the Run page | running_web.spec.ts: prepared runs on the Run page | UI | PASS | — |
| Manual / hardware items (tailnet, TLS, exposure, pairing on phone, outdoor run with Polar H10, offline finish, process kill, TWA, etc.) | — | manual | MANUAL | Not run. UNVERIFIED. |
| [UI — manual] QR scan with Google code scanner | — | manual | MANUAL | Not run. UNVERIFIED. |

## Test output

```
Backend (atlas-runningtracker-test, rebuilt via 03_Application/RunningTracker/compose.yml service runningtracker-test):
======================== 47 passed, 3 warnings in 5.53s ========================
(re-run after rebuild: 47 passed, 3 warnings in 6.46s)

JVM (gradlew :app:assembleDebug :app:testDebugUnitTest; tests re-run with --rerun):
BUILD SUCCESSFUL. 62 tests, 0 skipped, 0 failures, 0 errors across 13 classes.

Playwright (atlas-playwright):
  5 passed (8.3s)
```

## Failure Analysis

All automated scenarios passed. No scenario is MISSING.

The manual / hardware scenarios are UNVERIFIED. They were not run and must not be read as passing:
- Tailnet exposure: `tailscale serve status`, tailnet TLS reachability, and the Cloudflare native 404.
- Physical-phone items: pair, revoke and re-pair; Free Run offline; the 20-minute outdoor Polar H10 run; Bluetooth loss; offline finish then sync; re-send with no duplicates; History with charts; process-kill recovery; TWA, login and notifications unchanged; the optional intent:// spike.
- [UI — manual]: QR scan with the Google code scanner.

## Required Action

Proceed past automated testing; the operator must perform the manual / hardware checklist on the phone and tailnet before treating the sprint as hardware-accepted.
