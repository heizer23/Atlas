#!/usr/bin/env bash
# PreToolUse guard for atlas_code_reviewer: Write/Edit only under 00_Blueprint/Quality/.
ROOT="${CLAUDE_PROJECT_DIR:-/home/linse/Prod/Atlas}"
f="$(jq -r '.tool_input.file_path // empty')"
case "$f" in
  "$ROOT"/00_Blueprint/Quality/*) exit 0 ;;
  *) echo "atlas_code_reviewer is read-only on code: Write/Edit allowed only under 00_Blueprint/Quality/ (got: $f)" >&2; exit 2 ;;
esac
