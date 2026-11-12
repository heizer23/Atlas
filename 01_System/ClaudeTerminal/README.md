# ClaudeTerminal (System Access)

## Purpose
Browser terminal (xterm.js, Atlas Shell "Terminal" tab) attached to a **host** tmux session, so the real
interactive `claude` (permission prompts, slash commands, Docker, psql, make) is usable from the phone.
Replaces the limits of the headless `claude -p` chat in the ClaudeConsole container; both coexist.

## Security model (R-OPS-BP-02)
- Bridge (`claudeterm_bridge.py`, systemd user unit `claudeterm.service`) binds **127.0.0.1:8031** only.
  Containers cannot reach host loopback.
- Only entry: `tailscale serve` (tailnet-only, **Funnel off**) at
  `https://atlas-server.taild14f3a.ts.net:8443/claudeterm`. **Never exposed through Cloudflare** — the terminal tab
  only works with Tailscale on; the rest of Atlas stays on Cloudflare.
- Bridge requires header `Tailscale-User-Login` == `CLAUDETERM_ALLOWED_LOGIN` (default `p.remmecke@gmail.com`,
  injected by `tailscale serve`), and WS `Origin` in `CLAUDETERM_ALLOWED_ORIGINS`
  (default `https://workout.linspad.net,https://linspad.net`).
- This is a full host shell as the user. Anything that can act as that tailnet identity owns the host.
  Optional hardening: tailnet ACL limiting who can reach this host on 8443.

## Operator steps
1. `make claudeterm-install` (no sudo; user unit, listens on loopback only)
2. `make claudeterm-tailnet-up` (sudo; adds the `/claudeterm` path next to the RunningTracker mount on 8443)
3. `make runningtracker-tailnet-status` — verify both mounts, **Funnel off**
4. Atlas Shell: nginx unchanged; frontend deploy hook publishes the Terminal tab.

Rollback: `make claudeterm-tailnet-down`, `systemctl --user disable --now claudeterm`.

## Protocol
`GET /claudeterm/sessions` → `[{name, windows, attached}]`.
`WS /claudeterm/ws?session=NAME&cols=&rows=` — binary frames = pty bytes; text frames JSON
`{"type":"resize","cols","rows"}`. Closing the socket kills only the tmux client; the session survives.
Session names: `[A-Za-z0-9_-]{1,32}`; `tmux new-session -A` joins or creates.

## State
No durable state. tmux sessions are owned by tmux; the unit uses `KillMode=process` so restarting the bridge
does not kill a tmux server first started under it.
