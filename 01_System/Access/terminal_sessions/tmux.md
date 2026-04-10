# tmux — Persistent Terminal Sessions

## Purpose

Persistent CLI sessions for long-running interactive processes (agents, logs, database shells).

Prevents session loss on SSH disconnect.

## Mechanism

One tmux session per tool/role. Standard session names:

| Session | Purpose |
|---------|---------|
| `atlas-claude` | Claude Code / interactive agent |
| `atlas-openclaw` | OpenClaw or secondary agent |
| `atlas-logs` | Log tailing |
| `atlas-db` | Database shell |

## Standard Usage

```bash
# Attach to existing session or create new
tmux attach -t atlas-claude || tmux new -s atlas-claude
```

## Rules

- All long-running interactive agents must run inside a tmux session.
- No direct execution in raw SSH sessions.
- Session names must follow the `atlas-<role>` convention above.

## Non-Scope

- No process supervision — systemd handles service lifecycle.
- No application logic.
- tmux state is operational and ephemeral; it is not durable system state.
