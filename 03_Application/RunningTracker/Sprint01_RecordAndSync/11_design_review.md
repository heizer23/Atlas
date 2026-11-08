# Design Review — RunningTracker — Sprint01_RecordAndSync

**Verdict:** APPROVED
**Date:** 2026-11-08
**Reviewer:** sprint_design_reviewer

## Blocking Issues

_(None)_

## Non-Blocking Issues

| # | Location | Observation |
|---|----------|-------------|
| 1 | Input check: `10_architecture.json`, `10_scaffolding.json` | Bash was unavailable in this review session, so the JSON could not be machine-parsed. Both files were read in full: brackets, commas and the escaped quotes in the `KeystoreAesGcmCipher` default argument are well-formed. The implementer should still run `python3 -m json.tool` on both before relying on them. |
| 2 | `10_architecture.json` invariants D1, open_questions Q2 | The tailnet mount is declared as path-limited to `/api/runningtracker/native` proxying to `127.0.0.1:8029`. Depending on the installed Tailscale version, `serve` may strip the mount path before proxying. The backend routes are mounted at the full `/api/runningtracker/native/...`, so the proxy target would then need to carry the path suffix. Q2 assigns this to the implementer and the human runs the command. The manual scenarios in `10_test_spec.md` ("Manual / hardware: Tailnet, TLS and exposure") would catch a wrong mapping. Informational only. |
| 3 | `10_architecture.json` open_questions Q1, Q4, Q5, Q6 (owner: product) | These need product confirmation before or during implementation. Q1 is the CT-log exposure and the HTTPS-certificates prerequisite. Q4 is the new dependencies. Q5 is the 48 h TTL. Q6 is the pair path moving from `/device/pair` (draft §5) to `/native/pair`. All are surfaced with owners, and the design chooses the least-privilege default for each, so none block. The Q6 deviation from the draft is declared in invariant E2. |
| 4 | `10_scaffolding.json` `backend/config.py` `PAIRING_QR_PREFIX` ("single definition") vs `src/pairingPayload.ts` and Kotlin `PairingPayload` | The prefix `ATLASRUN1` is described as having one definition, but the TypeScript and Kotlin sides cannot import a Python constant and must repeat the literal. The authoritative format string `ATLASRUN1\|<base_url>\|<code>` is unambiguous, so the wording is the only issue. The implementer should treat the string as a three-place literal and keep a test for each parser. |
| 5 | `10_test_spec.md` vs `10_architecture.json` failure_modes (`PAYLOAD_TOO_LARGE 413`) | The 413 body-size guard in `native_guard` has no scenario. It is a backstop on a tailnet-only endpoint. The guard checks Content-Length only, so a chunked body is not capped by it. Acceptable for a single-user tailnet, but worth a one-line test or a documented limitation. |
| 6 | `10_architecture.json` S3, internal_flow step 2 | Marking a code used must be an atomic conditional update (`WHERE used_at IS NULL AND locked_at IS NULL AND expires_at > now()`). Otherwise two concurrent redeems of one code could both succeed. This is an implementation detail with an obvious correct reading and the S4 "single use" rule is clear, so it is a note only. |
| 7 | `10_architecture.json` begin branch table | `finish` on a run whose status is still `prepared` (never begun) is not stated. The phone always calls begin first, and the `runs` check constraint requires `started_at` for non-prepared rows. A 404 or 409 is the natural reading. |

Items verified as consistent:
- Layer placement: Application owns the running-domain behaviour. Native code in `01_System/AtlasPhone` is declared and bounded, and there is no domain logic in `02_Platform`.
- Schema vs architecture: tables, columns and constraints match the interfaces, the `contiguous_seq` and `high_seq` cursors, the begin branch table and the per-surface row shapes.
- V1 realizability: `CaptureStore.append` assigns one `next_seq` per capture and shares it across both streams (`CaptureStore.kt`: `PRIMARY KEY (capture_id, seq)`, `next_seq + 1` per stored sample). The claim that the union of seqs equals 1..last_seq holds.
- Sample payload keys (`timestamp`, `accuracyMeters`, `bpm`) in `Samples.kt` match what A1 and `sample_ts` extraction consume.
- Port 8029 is unused. The backend is bound to 127.0.0.1 only, nginx has an explicit 404 for the native prefix placed before the proxy block, and the CF-header guard is a declared backstop.
- Robolectric is already a test dependency in `app/build.gradle.kts`, so the scaffolded Robolectric tests introduce nothing new.
- Native endpoints are exempt from Dataset per the stated machine-to-machine decision. Web read endpoints all return Dataset with R-CON-AL-01 query blocks. PATCH carries explicit omit/value/null semantics and the round trip (U1). Time authority is declared (T1).
- UI coverage: `.tsx` files are in scope and `10_test_spec.md` contains four `[UI]` scenarios plus one `[UI — manual]`.
- Draft §13 open decisions 1–3 are resolved in D1–D3.

## Approval Condition

None — approved as-is.
