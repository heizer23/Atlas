# ClaudeConsole credentials sync

Host-side fix for a recurring ClaudeConsole bug: its container bind-mounts
`~/.claude/.credentials.json` so the inner headless `claude` CLI can
authenticate. Docker single-file bind mounts bind to the file's inode, not
its path. When the host file is atomically replaced (unlink + rename — the
pattern OAuth re-login/token-refresh uses), the container keeps the old,
now-orphaned inode and the inner `claude` starts reporting "Not logged in."
Previously fixed operationally each time via `make console-reboot`
(`01_System/Makefile`).

## The fix

`sync-claudeconsole-creds.sh` mirrors `~/.claude/.credentials.json` into a
dedicated `~/.claudeconsole-creds/` directory (nothing else lives there).
`03_Application/ClaudeConsole/compose.yml` bind-mounts that whole directory
into the container instead of the single file. Directory-level bind mounts
pick up entries by path lookup, so an atomic replace of the mirrored file
(done by this script, itself via tmp-file + `mv`) is seen correctly by the
container — no more stale inode, no more manual reboot.

This keeps container exposure scoped to just the OAuth token, same as
before — it does **not** mount all of `~/.claude/` (which also holds
conversation history and session data for every project on this machine,
not just Atlas). See `03_Application/ClaudeConsole/CLAUDE.md`'s "Deliberately
accepted exposure" section for the full tradeoff.

## Files

- `sync-claudeconsole-creds.sh` — the sync logic; idempotent, safe to run repeatedly
- `claudeconsole-creds-sync.service` / `.timer` — user systemd units that run the sync every 20s
- `install.sh` — installs and enables the timer under `~/.config/systemd/user/`

## Install / reinstall

```
01_System/ClaudeConsole_CredsSync/install.sh
```

## Operational notes

- User lingering is off for this account by default, so the timer only runs
  while a login session is active. Run `sudo loginctl enable-linger $(whoami)`
  once if the host is ever left with no session logged in and the sync
  still needs to run.
- Check status: `systemctl --user status claudeconsole-creds-sync.timer`
- Force an immediate sync: `01_System/ClaudeConsole_CredsSync/sync-claudeconsole-creds.sh`
- The mirror directory (`~/.claudeconsole-creds/`) is derived, disposable
  state — safe to delete; the next timer tick or container start
  regenerates it. Not to be confused with durable state under R-CON-BP-03:
  the real credentials live only in `~/.claude/.credentials.json`.
