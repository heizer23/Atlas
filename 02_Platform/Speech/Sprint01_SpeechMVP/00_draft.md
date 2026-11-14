# Sprint Draft — Speech Platform MVP (Sprint 1)

## Goal
High-quality, reusable speech-to-text across Atlas. First consumer: ClaudeConsole.

## Classification (to be confirmed by design phase)
- New platform component `02_Platform/Speech/` (backend service, no domain logic).
- Shared recorder UI primitive in Atlas_Shell `platform-ui/` (reusable hook + component).
- ClaudeConsole integration in `03_Application/ClaudeConsole/src/ShellEntry.tsx` (replaces/complements the browser Web Speech dictation already there).

## Scope
- Shared recording component: continuous `MediaRecorder`, chunk emission ~every 15 s via `timeslice`, recording is never stopped to cut chunks.
- Pause, resume, cancel supported; cancel discards audio server-side.
- Speech API (FastAPI): authenticated; OpenAI credentials live only in the backend (`WhisperKey` in `01_System/secrets.env` already exists).
- Backend accepts chunks per recording id, reassembles them into ONE valid audio file (chunks from one MediaRecorder stream are fragments of one container, not independent files — concatenate in order, verify by index, reject gaps).
- Full-file transcription at Stop. Model configurable via env (default `gpt-transcribe` per user; verify the exact model id against the OpenAI API at implementation time and fall back to a documented alternative if rejected).
- Configurable vocabulary: `prompt`, `keywords`, `languages`. OpenAI's transcription endpoint has `prompt` and `language` only; `keywords` are folded into the prompt text server-side. Defaults stored in config, overridable per request.
- ClaudeConsole: transcript is inserted into the input box at the caret/end, editable, NEVER auto-submitted; existing typed text is preserved.
- Instrumentation (log + return in response): stop→transcript latency, upload time, API time, audio duration, chunk count. Accuracy / vocabulary / boundary metrics are measured manually against a reference script (provide a small checklist doc, not tooling).

## Acceptance criteria
- Works on Android phone and desktop over HTTPS.
- Handles pauses and cancellations.
- No audio lost at chunk boundaries (reassembled duration ≈ recorded duration).
- Returns transcript without disturbing existing typed text.

## Security (R-OPS-BP-02)
- No new host port beyond `127.0.0.1`; reachable only through the shell nginx route (`/api/speech`).
- Atlas has no app-level auth today: design phase must state what "authenticated" means here (e.g. shared bearer token issued by backend config, vs. relying on tailnet/Cloudflare Access) and surface it as a conflict/decision if it is not satisfiable with existing structure.
- Enforce max upload size, max recording duration, and chunk-count limits; temp audio deleted after transcription or on cancel/timeout.
- Audio is sent to OpenAI: note this in the component CLAUDE.md.
- OpenAI key never reaches the frontend or logs.

## Out of scope
- Progressive/windowed transcription, overlap merge, context feeding (Sprint 2).
- Auto-submit, other app integrations, streaming/realtime API.

## Open questions
1. Authentication mechanism (see Security).
2. Exact transcription model id.
