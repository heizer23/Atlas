#!/usr/bin/env bash
# Mirrors ~/.claude/.credentials.json into ~/.claudeconsole-creds/.credentials.json.
#
# Why this exists: ClaudeConsole bind-mounts a host directory (not the single
# credentials file) into its container so that Docker sees directory-entry
# updates instead of holding a stale inode when the host file is atomically
# replaced (re-login / OAuth token refresh). See
# 03_Application/ClaudeConsole/CLAUDE.md and this directory's README.md.
#
# This script is the host-side half of that fix: it keeps the dedicated
# mirror directory in sync with the real ~/.claude/.credentials.json, so the
# container only ever sees this one file, never the rest of ~/.claude/.
set -euo pipefail

SRC="$HOME/.claude/.credentials.json"
DEST_DIR="$HOME/.claudeconsole-creds"
DEST="$DEST_DIR/.credentials.json"

mkdir -p "$DEST_DIR"
chmod 700 "$DEST_DIR"

if [[ ! -f "$SRC" ]]; then
  exit 0
fi

if [[ ! -f "$DEST" ]] || ! cmp -s "$SRC" "$DEST"; then
  TMP="$DEST_DIR/.credentials.json.tmp.$$"
  cp "$SRC" "$TMP"
  chmod 600 "$TMP"
  mv "$TMP" "$DEST"
fi
