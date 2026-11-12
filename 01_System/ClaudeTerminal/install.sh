#!/usr/bin/env bash
# Installs and starts the ClaudeTerminal bridge as a user systemd unit. Idempotent.
# Does NOT touch Tailscale; exposing it is a separate, explicit step: `make claudeterm-tailnet-up`.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT_DIR="$HOME/.config/systemd/user"

mkdir -p "$UNIT_DIR"
chmod +x "$SCRIPT_DIR/claudeterm_bridge.py"
cp "$SCRIPT_DIR/claudeterm.service" "$UNIT_DIR/"

systemctl --user daemon-reload
systemctl --user enable --now claudeterm.service
systemctl --user restart claudeterm.service

echo "Installed and started claudeterm.service (127.0.0.1:8031)"
