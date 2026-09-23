#!/usr/bin/env bash
# Installs and starts the ClaudeConsole credentials-sync timer as a user
# systemd unit. Safe to re-run (idempotent).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT_DIR="$HOME/.config/systemd/user"

mkdir -p "$UNIT_DIR"
chmod +x "$SCRIPT_DIR/sync-claudeconsole-creds.sh"
cp "$SCRIPT_DIR/claudeconsole-creds-sync.service" "$UNIT_DIR/"
cp "$SCRIPT_DIR/claudeconsole-creds-sync.timer" "$UNIT_DIR/"

systemctl --user daemon-reload
systemctl --user enable --now claudeconsole-creds-sync.timer

# Seed the mirror immediately so a container started right after install
# already has valid credentials, without waiting for the first timer tick.
"$SCRIPT_DIR/sync-claudeconsole-creds.sh"

echo "Installed and started claudeconsole-creds-sync.timer"
echo
echo "NOTE: user lingering is off for this account, so this timer only runs"
echo "while you have an active login session. If the host is ever accessed"
echo "only via sessions that close (no session left logged in) and you want"
echo "the sync to keep running regardless, run once (requires sudo):"
echo "  sudo loginctl enable-linger \$(whoami)"
