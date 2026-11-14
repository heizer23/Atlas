# CLAUDE.md

App-local guidance only. Global rules: repository root CLAUDE.md.

## Purpose
Speech is a platform component: FastAPI service (no per-user auth; relies on the Atlas perimeter, with spend caps) that receives chunked MediaRecorder audio per recording id, reassembles it into ONE file (byte concatenation in index order, then `ffmpeg -c copy` remux), and transcribes it once at stop via OpenAI. No domain logic. Browser side: `platform-ui/hooks/useRecorder.ts`, `components/RecorderButton.tsx`, `api/speechClient.ts`. First consumer: ClaudeConsole (`ShellEntry.tsx`). Design: `Sprint01_SpeechMVP/`.

## Privacy: audio leaves Atlas
Recorded audio is sent to OpenAI (`api.openai.com/v1/audio/transcriptions`). Audio exists only in the tmpfs `/tmp/speech` and is deleted after transcription, cancel, validity/limit rejection, idle timeout (900 s) and on startup. After an upstream failure the audio is retained (until idle timeout) so the client can retry stop. Transcripts are never persisted or logged.

## Secrets (never print or commit)
- `AtlasSpeech` (dedicated OpenAI key): `01_System/secrets.env`, passed to the container as `SPEECH_OPENAI_KEY`, read only in `app/transcriber.py`.

## Access and spend control
No browser-held credential: Speech sits behind the same Atlas perimeter as every other route (bound to `127.0.0.1`, reached via the shell nginx). Whether the Cloudflare tunnel is gated by Cloudflare Access is unverified from the repo (EssayCards audit M6) — if it is not, anyone reaching the shell can spend OpenAI credit, so the caps below are the real protection. `app/budget.py` refuses to transcribe past `SPEECH_DAILY_AUDIO_S` (default 3600 s of audio per rolling 24 h) or `SPEECH_HOURLY_TRANSCRIPTIONS` (default 30/h) with `BUDGET_EXCEEDED` (429); state persists in the `speech-data` volume. Also set a monthly spend limit in the OpenAI dashboard — that is the hard ceiling.

## Run
- `make -C 01_System speech-build speech-up` (uses config.env + secrets.env). Container `atlas-speech`, host port `127.0.0.1:8070` only.
- Tests: `make -C 01_System test-up` then `docker exec atlas-speech-test pytest tests/ -v` (port 9070; no OpenAI call; `test_shell_proxy.py` needs shell + `atlas-speech` running).
- nginx `/api/speech` lives in `02_Platform/Atlas_Shell/nginx.conf` (baked into the image: rebuild the shell image, `docker cp` of dist is not enough).

## Limits (env, defaults)
chunk 2 MiB, total 20 MiB, 80 chunks, 600 s, 4 active recordings, idle TTL 900 s, upstream timeout 120 s. The client auto-stops 3 s before max duration so timer lag cannot trip the strict server check. `expected_chunks` above max_chunks is rejected (`CHUNK_INDEX_INVALID`).

## Live-API verification (2026-11-11, short ffmpeg tone, not real speech)
- Model `gpt-transcribe` accepts `keywords` and `languages` as REPEATED multipart fields (one part per value): HTTP 200. `keywords[]`/`languages[]` also 200. A JSON-array string (`'["en"]'`) is rejected with 400 `invalid_value`. Code uses repeated fields (`app/vocabulary.py`).
- Invalid primary model id returns 404 `model_not_found` -> fallback triggers (fallback statuses: 400, 404, 422). Fallback `gpt-4o-transcribe` with `prompt` + singular `language` returned 200.
- Caveat: on a pure tone the fallback model echoed the prompt vocabulary ("Atlas."); keep vocabulary prompts short and judge accuracy on real speech (see `docs/Manual_Accuracy_Checklist.md`).
- NOT verified: that Chrome's real MediaRecorder webm (after ffmpeg remux) is accepted, that keywords measurably improve recognition, Android. Do this with the checklist.
- Fallback models `gpt-4o-transcribe` / `whisper-1` are deprecated, shutdown 2027-02-26.

## Testing notes
`Transcriber(settings, transport=...)` is the test seam (`httpx.MockTransport`). Because assembly remuxes, tests assert a valid decodable webm of the expected duration, not byte equality with the original sample.
