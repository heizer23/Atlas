# Design Review — Speech — Sprint01_SpeechMVP

**Verdict:** APPROVED
**Date:** 2026-11-11
**Reviewer:** sprint_design_reviewer

## Blocking Issues

_(None)_

## Non-Blocking Issues

| # | Location | Observation |
|---|----------|-------------|
| 1 | nginx shadowing check (requested): `02_Platform/Atlas_Shell/nginx.conf` vs `10_scaffolding.json` nginx_conf entry | No shadowing. The existing file uses only prefix locations plus `location ^~ /api/runningtracker/native { return 404; }` (line 203) and no regex locations. `/api/speech` is a disjoint prefix, so it cannot match `/api/runningtracker/native` and does not weaken that rule. Placing it with the other platform blocks is safe. The `^~` rule is untouched. |
| 2 | Auth coherence (requested): `10_architecture.json` open_questions[0], risks[0..1], `10_scaffolding.json` auth.py, speechClient.ts, compose.yml | Coherent. The header name `X-Atlas-Speech-Token` and env `SPEECH_API_TOKEN` are identical in all artifacts. Fail-closed, constant-time compare and no-header-logging are specified. `/health` is host-local and not proxied. `apiFetch` merges `options.headers`, so the token header and Content-Type override are feasible without modifying `client.ts`. Token entry is only reachable after the secure-context check, so the token is not typed over plain HTTP. The conflict with the draft (a new secret in `01_System/secrets.env`, first browser-held credential, perimeter unchanged) is surfaced per R-OPS-BP-01 and assigned to product. Rejecting ATLAS_SERVICE_TOKEN is correct. Residual risks are explicit; there is no token brute-force throttle, which is acceptable for a bearer token with the stated caps and is already listed in deferred_decisions. **Auth decision accepted.** |
| 3 | `10_architecture.json` internal_flow step 5/12 vs scaffold useRecorder "Auto-stop at limits.max_duration_s" | The hook auto-stops at the advertised max duration, while the server rejects `client_duration_ms` strictly above max (and measured duration above max) and deletes audio. Timer latency makes an auto-stopped full-length recording likely to be rejected as RECORDING_TOO_LONG. The implementer should apply a small tolerance on the server check or an earlier client auto-stop. Not blocking: it only affects the 10-minute edge. |
| 4 | `10_test_spec.md` vs `10_architecture.json` deferrals.reviewer ("every error code covered") | CHUNK_INDEX_INVALID, RECORDING_BUSY, and SPEECH_NOT_CONFIGURED via unset WhisperKey (step 2) have no scenario. CHUNK_INDEX_INVALID is also missing from architecture failure_modes, though it is in the scaffold enum and step 3, so the authoritative field is unambiguous. |
| 5 | `10_test_spec.md` fallback / timeout / vocab-folding scenarios vs scaffold conftest | These scenarios need the real `Transcriber` against a fake HTTP upstream, but conftest only describes a fake `Transcriber` that replaces it wholesale. `Transcriber.__init__` declares no transport seam. The implementer must choose one, for example `httpx.MockTransport` via monkeypatch. The "server error for both models" wording is also looser than step 8, where fallback is attempted only on a client error. |
| 6 | `10_scaffolding.json` StopRequest.expected_chunks (>= 1, no upper bound) | MISSING_CHUNKS lists missing indices, so an authenticated caller can request an enormous range. Cap `expected_chunks` at `max_chunks`. This is authenticated-only, hence not blocking. |
| 7 | `10_architecture.json` step 11 reap_idle / begin_finalize | It is not stated that finalizing recordings are skipped by the reaper, and `last_activity` is not touched at begin_finalize. The worst-case finalize is about 300 s against a 900 s TTL, so it is safe by margin. |
| 8 | nginx `proxy_read_timeout 150s` vs `upstream_timeout_s 120` + `ffmpeg_timeout_s 60` | The worst case (fallback attempt at 120 s plus a slow ffmpeg) exceeds 150 s. The retained-recording retry covers it, and the risk is already listed. Consider setting the nginx timeout above the sum. |
| 9 | Draft verification | Ports 8070 and 9070 are unused in compose, yml and env files (grep). The ShellEntry import pattern (`@platform-ui/...` path imports, default exports) matches the design (R-CON-BP-06). The test spec includes `[UI — manual]` scenarios, which satisfies the `.tsx` rule. Layer placement is correct: no domain logic in the backend, and insertion and no-auto-submit stay in the ClaudeConsole consumer. The edit to ShellEntry.tsx inside a platform sprint is in the draft scope. |

## Approval Condition

None — approved as-is.
