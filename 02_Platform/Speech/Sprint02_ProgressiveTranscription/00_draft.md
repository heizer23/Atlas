# Sprint Draft — Progressive Transcription (Sprint 2)

STATUS: DEFINED ONLY — NOT AUTHORIZED. Do not implement until Sprint 1 latency/quality measurements exist.

## Goal
Reduce the time between Stop and the complete transcript.

## Scope
- Upload chunks during recording (Sprint 1 already does this).
- Start the first transcription once 30 s of audio is available.
- Reassemble subsequent audio into independently valid transcription windows with small overlaps.
- Supply earlier transcript text as context (prompt).
- Merge results without duplicated or missing words.
- Keep full-recording transcription as fallback.

## Test
Record the same 60–90 s message; compare full-file vs progressive transcription (latency, word errors, boundary duplicates/omissions, Atlas vocabulary).
