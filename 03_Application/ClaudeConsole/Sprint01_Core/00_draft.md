# Sprint 01 — ClaudeConsole Core

## Goal

Control a headless Claude Code session, scoped to this Atlas repo, from a chat window inside Atlas Shell — send prompts, watch the response stream live (including tool calls), and see the tail end of the conversation on reload.

## Component

- Name: ClaudeConsole
- Layer: 03_Application
- New component — no existing baseline

## Tech stack

Follow the same pattern as TaskTracker/StorageTracker in this repo: FastAPI backend, psycopg2 connection pool with RealDictCursor, `platform_contracts` for typed responses, `platform_errorhandling` for `ApiError`/middleware, React frontend registered with Atlas Shell via `src/shellConfig.ts`. Backend bound to `127.0.0.1` only (host-local, no external exposure — R-OPS-BP-02).

## Core mechanism

- Backend controls the `claude` CLI in headless/print mode as a child process — not a TUI, not tmux.
- First message of a session: spawn `claude -p --output-format stream-json --input-format stream-json --permission-mode <mode> --cwd /home/linse/Prod/Atlas`. Capture the `session_id` from the `init` event.
- Every subsequent message: spawn the same command with `--resume <session_id>` added. Claude Code's own on-disk session store is the source of truth for conversation continuity — ClaudeConsole does not reimplement it.
- The chat window is scoped to this repo only. There is no working-directory picker and no way to point a session at any other path.

## Session model (v1 scope)

- Exactly one session can be active at a time. There is no session list/switcher UI in v1.
- Starting a new session ends the current one (its transcript remains in the DB, just not resumable from the UI). Killing/restarting the backend does not lose the Claude-side session — only the live subprocess and any in-flight turn; the next message simply issues a fresh `--resume` call.
- Permission mode is chosen once, when a session starts: `plan` | `acceptEdits` | `bypassPermissions`. Default is `acceptEdits`. Choosing `bypassPermissions` must show an explicit warning in the UI before confirming (R-OPS-BP-02 — least privilege by default, exposure called out, not silently allowed).
- There is no per-action permission-prompt relay in v1 (no "approve this tool call" UI). This is a real capability reduction versus interactive Claude Code and should be stated as such, not hidden.
- A running turn can be interrupted (kill the child process) from the UI.

## Durable state (R-CON-BP-03)

Owned by ClaudeConsole, in its own Postgres schema:
- `sessions` — id, claude_session_id, permission_mode, status (`active` | `ended`), created_at, ended_at
- `messages` — id, session_id, role (`user` | `assistant` | `tool`), content, raw_event (jsonb, for tool-call detail), created_at

The DB copy is authoritative for what the UI renders on reload; Claude Code's own session file is only used to resume the underlying conversation, not read back for history.

## API surface

**Read (must return `Dataset` per R-CON-BP-04, or see the flagged exception below):**
- `GET /session` — current session's id, permission_mode, status
- `GET /session/messages` — full message history for the current session

**Mutations (typed record or `ApiError`, per R-CON-BP-04):**
- `POST /session` — start a new session with a chosen `permission_mode`; ends any existing active session
- `POST /session/interrupt` — kill the in-flight turn, if any
- `POST /session/end` — end the current session without starting a new one

**Streaming (out of scope of the Dataset/mutation contract — see flagged exception):**
- `WS /session/stream` — client sends one prompt per message; server streams back the raw-ish stream-json events (text deltas, tool-call start/end, turn-complete) as they arrive from the `claude` subprocess, and persists them to `messages` as they land.

## Flagged rule interactions (R-OPS-BP-01 — surfaced, not silently resolved)

1. **Streaming is neither a Dataset GET nor a simple mutation.** R-CON-BP-04 defines those two categories for REST responses. A chat turn is a POST-triggered, long-lived, incrementally-delivered exchange. Resolution for this draft: the send-prompt path is a WebSocket, explicitly outside R-CON-BP-04's scope (that rule governs REST response shapes); `GET /session` and `GET /session/messages` remain ordinary REST reads.
2. **`GET /session/messages` may not fit `Dataset` semantics either.** `Dataset` looks tabular/chart-shaped (see `UI_Data_Contract.md`); a chat transcript is a different shape. Precedent exists in this repo (EssayCards' export endpoints return a documented bespoke JSON shape instead of `Dataset`). The designer should decide explicitly — either force message history into `Dataset` rows or document a bespoke-shape exception the same way EssayCards did — and record whichever choice is made, rather than leaving it ambiguous.
3. **No per-action permission relay** is a deliberate v1 reduction versus what interactive Claude Code offers. `bypassPermissions` exists as an opt-in escape hatch, not the default, per R-OPS-BP-02.

## UI views

Register with Atlas Shell as "ClaudeConsole". Single view for v1:
- **Console** — chat-style message list (user prompts, assistant text, collapsible tool-call entries), input box, a permission-mode selector shown only when no session is active, a "new session" action, and a stop/interrupt control while a turn is running.

## Out of scope for this sprint

- Multiple concurrent sessions / session switcher
- Arbitrary working-directory selection
- Per-action permission approve/deny relay
- Any session/project other than this Atlas repo
- Mobile-specific layout

## Open questions for designer to resolve

- `GET /session/messages` shape: force into `Dataset`, or document a bespoke-shape exception (see flagged interaction #2)? No default preference — designer's call, but it must be explicit.
- Reconnect-mid-turn behavior: if the browser refreshes while a turn is streaming, should the WebSocket replay buffered events for the in-flight turn, or should the UI just show "turn in progress" until completion and rely on `GET /session/messages` after it finishes? Prefer the latter for v1 simplicity.
- Exact `messages.raw_event` granularity (store every stream-json event, or only the ones the UI renders)? Prefer: store every event for debuggability; UI renders a filtered subset.
