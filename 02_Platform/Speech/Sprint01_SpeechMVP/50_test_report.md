# Test Report — Speech — Sprint01_SpeechMVP

**Verdict:** TESTS_PASSING
**Date:** 2026-11-11
**Fix iteration:** 0

## Results

| Scenario | Test | Type | Status | Failure reason |
|----------|------|------|--------|----------------|
| Happy path: chunks reassemble and transcribe | test_happy_path_chunks_reassemble_and_transcribe | backend | PASS | — (asserts valid webm of expected duration, not byte equality; accepted deviation, ffmpeg remux) |
| Out-of-order arrival is reassembled by index | test_out_of_order_arrival_is_reassembled_by_index | backend | PASS | — (same accepted deviation) |
| Duplicate chunk upload is idempotent | test_duplicate_chunk_upload_is_idempotent | backend | PASS | — |
| Gap is rejected and recoverable | test_gap_is_rejected_and_recoverable | backend | PASS | — |
| Cancel discards audio | test_cancel_discards_audio | backend | PASS | — |
| Cancel of an unknown id succeeds | test_cancel_of_unknown_id_succeeds | backend | PASS | — |
| Authentication: missing or wrong token | test_authentication_missing_or_wrong_token | backend | PASS | — |
| Authentication: unconfigured service fails closed | test_authentication_unconfigured_service_fails_closed | backend | PASS | — |
| Health needs no token | test_health_needs_no_token | backend | PASS | — |
| Unsupported audio type | test_unsupported_audio_type | backend | PASS | — |
| Oversized chunk | test_oversized_chunk | backend | PASS | — |
| Too many chunks and too many bytes | test_too_many_chunks_and_too_many_bytes | backend | PASS | — |
| Too many concurrent recordings | test_too_many_concurrent_recordings | backend | PASS | — |
| Over-long recording | test_over_long_recording | backend | PASS | — |
| Undecodable audio | test_undecodable_audio | backend | PASS | — |
| Vocabulary defaults and per-request override | test_vocabulary_defaults_and_per_request_override | backend | PASS | — |
| Fallback model mapping | test_fallback_model_mapping | backend | PASS | — |
| Upstream failure retains audio for retry | test_upstream_failure_retains_audio_for_retry | backend | PASS | — |
| Upstream timeout | test_upstream_timeout | backend | PASS | — |
| Silence yields an empty successful transcript | test_silence_yields_empty_successful_transcript | backend | PASS | — |
| Idle recordings are reaped | test_idle_recordings_are_reaped | backend | PASS | — |
| Startup sweep | test_startup_sweep | backend | PASS | — |
| Secrets never leak | test_secrets_never_leak | backend | PASS | — |
| [UI — manual] Dictate into ClaudeConsole without disturbing typed text | — | manual | MANUAL | Untested, requires human verification |
| [UI — manual] Token prompt on first use and after rejection | — | manual | MANUAL | Untested, requires human verification |
| [UI — manual] Pause, resume and cancel on Android | — | manual | MANUAL | Untested, requires human verification |
| [UI — manual] Mutual exclusion with browser dictation | — | manual | MANUAL | Untested, requires human verification |
| [UI — manual] Empty and error outcomes | — | manual | MANUAL | Untested, requires human verification |

Extra tests beyond spec (all PASS): test_speech_proxy_reaches_backend, test_unset_openai_key_is_speech_not_configured, test_chunk_index_invalid, test_expected_chunks_above_max_is_rejected, test_recording_busy_while_finalizing.

## Test output

```
docker exec atlas-speech-test pytest tests/ -v
collected 28 items
... all 28 tests PASSED ...
======================== 28 passed, 5 warnings in 3.71s ========================
```
Warnings: only deprecations (starlette TestClient/httpx, FastAPI on_event). No tests/ui/ directory; Playwright not run.

## Failure Analysis

All scenarios passed. The test container was already up and was used as instructed (not rebuilt by this run). MANUAL scenarios requiring human verification: the five [UI — manual] scenarios listed above.

## Required Action

Proceed with the pipeline; have a human verify the five manual UI scenarios.
