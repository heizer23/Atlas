# Manual Accuracy Checklist — Speech

Manual only; no tooling. Use ClaudeConsole's server mic button (🎙️).

## 1. Setup
- Write a reference script of about 60-90 s containing: numbers (dates, amounts), proper nouns, product/tool names (Atlas, FastAPI, pytest, Postgres), one deliberate 5 s pause, and one long sentence that will span a 15 s chunk boundary (speak it at normal speed starting around second 12).
- Keep the browser console open (metrics are logged with `console.info("[speech] metrics")`).

## 2. Run matrix
| Device | Pause/resume | Per-request keywords |
|---|---|---|
| Desktop Chrome (HTTPS) | no | on (ClaudeConsole default) |
| Desktop Chrome (HTTPS) | yes | on |
| Android Chrome (HTTPS) | no | on |
| Android Chrome (HTTPS) | yes | off (temporarily clear `SPEECH_VOCABULARY` in ShellEntry or use a build without it) |

## 3. Record per run
- Word error estimate by eye (substitutions + omissions + insertions / total words).
- Vocabulary terms correct out of total.
- Words lost or duplicated at each chunk boundary (around 15 s, 30 s, 45 s ...).
- Metrics: `audio_duration_ms` vs `client_duration_ms` (delta), `stop_to_transcript_ms`, `chunk_count`.

## 4. Pass criteria (draft acceptance)
- `duration_delta_ms` small (within about 1 s) -> no audio lost at chunk boundaries.
- No lost or duplicated words at chunk boundaries.
- Typed text in the input is preserved; transcript inserted at the caret; nothing auto-sent.
- Pause/resume and cancel behave (cancel inserts nothing, mic indicator disappears).

## 5. Results
| Date | Device | Pause | Keywords | WER est. | Vocab ok/total | Boundary issues | delta ms | stop->text ms | chunks | Pass |
|---|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | | |
