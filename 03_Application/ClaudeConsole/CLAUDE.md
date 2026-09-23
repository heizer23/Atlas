# CLAUDE.md

This file contains app-local guidance only.
Global architecture and development rules are defined in the repository root CLAUDE.md.

## App
ClaudeConsole controls one headless Claude Code session at a time, scoped to this Atlas repo, from a chat window in Atlas Shell. It spawns the `claude` CLI in print/headless mode (`claude -p --output-format stream-json`) as a subprocess — not tmux, not a TUI.

## Sprint scope
Sprint 1 (`Sprint01_Core`): single active session, permission mode fixed per session (`plan` | `acceptEdits` | `bypassPermissions`, default `acceptEdits`), chat send/receive over WebSocket, message history persisted and returned as Dataset rows. No multi-session, no per-action permission relay, no working-directory picker. Built via plan mode + direct implementation rather than the full sprint design/review pipeline (`sprint_design_application` etc.), by explicit user choice. There is no `10_architecture.json`/`10_scaffolding.json`/`99_sprint_log.md` for this sprint as a result — this is a recorded, deliberate deviation from R-PRO-BP-01, not an incomplete sprint; see `00_Blueprint/Quality/agent_conflic_evidence.md` (`CNF-2026-09-09-001`). See `Sprint01_Core/00_draft.md` for the original scope — its two open questions (Dataset shape for `GET /session` and `GET /session/messages`) are resolved directly in this file's "Pattern references" section and in `backend/routers/session.py`'s module docstring.

## Deliberately accepted exposure — read before touching compose.yml
- The container bind-mounts `~/.claudeconsole-creds/` (a dedicated mirror directory, not the real `~/.claude/`) **read-write** onto `/root/.claude`. Your personal OAuth Claude Code login lives inside this container; anything that can exec into it can read your subscription credentials. Read-write (not read-only) because token refresh rewrites the underlying file. Accepted knowingly for v1, not mitigated further.
  - This is a **directory** mount, not a single-file mount, and the directory contains only a synced copy of `.credentials.json` — never mount `~/.claude/` itself here, it also holds conversation history and session data for every project on this machine, not just Atlas.
  - The mirror is kept current by a host-side systemd user timer (`01_System/ClaudeConsole_CredsSync/`, `sync-claudeconsole-creds.sh` on a 20s tick) that copies `~/.claude/.credentials.json` into the mirror via atomic replace. This exists because a *single-file* bind mount binds to the file's inode, not its path — when the real credentials file is atomically replaced (re-login / OAuth token refresh), a single-file mount keeps the old orphaned inode and the inner `claude` reports "Not logged in" until the container is recreated. A directory-level mount doesn't have this problem (path lookups, not fixed inodes), which is why the sync script writes into a mirror *directory* rather than the container mounting the real file directly. See `01_System/ClaudeConsole_CredsSync/README.md` for full detail; recurred three times (2026-09-10 through 2026-09-23) before this fix.
  - If ClaudeConsole reports logged-out again despite this: check `systemctl --user status claudeconsole-creds-sync.timer` is active first (it depends on an active login session unless lingering is enabled — see the README) before falling back to `make console-reboot` (`01_System/Makefile`).
- The container bind-mounts the real Atlas repo working tree **read-write**, at the same absolute path used for `--cwd`. Unlike every sibling app (build-time code copy only), this is the entire point of the app: the inner Claude session edits real files you actually work in.
- `~/.gitconfig` is mounted read-only for git author identity. SSH keys and push credentials are deliberately NOT mounted — pushing stays a manual, human step outside this app.

## Pattern references
Follow the same patterns as StorageTracker (`03_Application/StorageTracker`):
- FastAPI backend, psycopg2 connection pool, RealDictCursor
- platform_contracts for Dataset responses
- platform_errorhandling for api_error and middleware
- Atlas Shell registration via src/shellConfig.ts — this ALSO requires a `COPY 03_Application/ClaudeConsole/src/ 03_Application/ClaudeConsole/src/` line in `02_Platform/Atlas_Shell/Dockerfile` (each app's `src/` is copied into the shell's build stage individually). This line was missing until the 2026-09-10 smoke test — the shell build failed outright (`Could not resolve "...shellConfig" from main.tsx`) until it was added. `nginx.conf`'s `/api/claudeconsole` and `/api/claudeconsole/ws` location blocks were already correct, but nginx.conf is baked into the shell image at build time (no volume mount) — a `docker cp` of `dist/` alone does not pick up nginx.conf changes; the shell container must be rebuilt.

Novel pieces, not present in any sibling app:
- `backend/claude_process.py` — owns the `claude` subprocess lifecycle (one spawn per turn; `--resume` carries continuity across turns). Verified end-to-end 2026-09-10 against installed CLI v2.1.197 via a live two-turn smoke test (build + docker exec, not a pytest run) — see the module docstring for exact findings. Two real bugs were fixed in that pass: `--cwd` is not a valid flag on this CLI version (removed; `cwd=` on the subprocess call already handles it), and `--output-format stream-json` requires `--verbose` alongside `--print`. A third gap was closed: a fresh container's `~/.claude.json` has this workspace untrusted by default, which silently blocks every turn behind the interactive trust dialog that headless mode never shows — `ensure_workspace_trusted()` now seeds just this repo's trust flag into the container-local config at startup.
- `backend/ws.py` — the only WebSocket route in Atlas; single-connection-at-a-time by design.
- `Dockerfile` — the only container in this repo combining Node.js (for the `claude` CLI) and Python.

## Port
ClaudeConsole backend runs on host port 8025 (container port 8000).

## Schema
claudeconsole schema in the shared Atlas Postgres instance.
Tables: claudeconsole.sessions, claudeconsole.messages
Schema initialized idempotently at startup from schema.sql.
